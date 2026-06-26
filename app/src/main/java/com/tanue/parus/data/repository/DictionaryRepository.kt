package com.tanue.parus.data.repository

import android.util.Log
import com.tanue.parus.data.database.WordDao
import com.tanue.parus.data.model.WordWithDetails
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class DictionaryRepository(private val wordDao: WordDao) {
    suspend fun search(query: String): List<WordWithDetails> = withContext(Dispatchers.IO) {
        val queryClean = query.trim().lowercase()
        if (queryClean.isEmpty()) return@withContext emptyList()

        val isRussian = queryClean.any { it in '\u0400'..'\u04FF' }

        try {
            // 优先使用 FTS5 高速搜索
            if (isRussian) {
                val queryPrefix = "$queryClean*"
                val queryMatch = "$queryClean*"
                wordDao.searchRussianWords(queryClean, queryPrefix, queryMatch)
            } else {
                val pinyinGlob = "*$queryClean [a-z]*"
                wordDao.searchChineseWords(queryClean, pinyinGlob)
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
}
