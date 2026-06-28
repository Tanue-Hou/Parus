package com.tanue.parus.data.repository

import android.util.Log
import java.text.Normalizer
import com.tanue.parus.data.database.WordDao
import com.tanue.parus.data.model.WordWithDetails
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class DictionaryRepository(private val wordDao: WordDao) {
    suspend fun search(query: String): List<WordWithDetails> = withContext(Dispatchers.IO) {
        val queryClean = normalizeQuery(query)
        if (queryClean.isEmpty()) return@withContext emptyList()

        val isRussian = queryClean.any { it in '\u0400'..'\u04FF' }

        try {
            // 优先使用 FTS5 高速搜索
            if (isRussian) {
                val queryPrefix = "$queryClean*"
                val queryMatch = "$queryClean*"
                wordDao.searchRussianWords(queryClean, queryPrefix, queryMatch)
            } else {
                // 中文搜索：LIKE 全量匹配 + GLOB 拼音识别排序
                // pattern1a: 释义以 "1) 水 [pinyin]" 开头（第一个义项+拼音）
                // pattern1b: 释义以 "水 [pinyin]" 开头（无编号前缀+拼音）
                // pinyinGlob: 任意位置出现 "水 [pinyin]"
                val queryLike = "%$queryClean%"
                val pattern1a = "1) $queryClean [a-z]*"
                val pattern1b = "$queryClean [a-z]*"
                val pinyinGlob = "*$queryClean [a-z]*"
                wordDao.searchChineseWords(queryClean, queryLike, pattern1a, pattern1b, pinyinGlob)
            }
        } catch (e: Exception) {
            // FTS5 失败时降级到 LIKE 搜索
            Log.e("ParusSearch", "FTS5 搜索失败，降级到 LIKE: ${e.message}", e)
            try {
                if (isRussian) {
                    wordDao.searchFallbackRussian(queryClean, "$queryClean%")
                } else {
                    wordDao.searchFallbackChinese("%$queryClean%")
                }
            } catch (e2: Exception) {
                Log.e("ParusSearch", "降级搜索也失败: ${e2.message}", e2)
                emptyList()
            }
        }
    }

    private fun normalizeQuery(query: String): String {
        val nfc = Normalizer.normalize(query, Normalizer.Form.NFC)
        return nfc.trim().lowercase()
            .replace("\u0301", "") // COMBINING ACUTE ACCENT
            .replace("\u0300", "") // COMBINING GRAVE ACCENT
            .replace("'", "")
            .replace("`", "")
    }
}
