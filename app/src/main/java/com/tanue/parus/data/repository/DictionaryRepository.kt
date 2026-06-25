package com.tanue.parus.data.repository

import com.tanue.parus.data.database.WordDao
import com.tanue.parus.data.model.WordWithDetails
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class DictionaryRepository(private val wordDao: WordDao) {
    suspend fun search(query: String): List<WordWithDetails> = withContext(Dispatchers.IO) {
        val queryClean = query.trim().lowercase()
        if (queryClean.isEmpty()) return@withContext emptyList()

        // 检测输入是俄语（含西里尔字母）还是中文
        val isRussian = queryClean.any { it in '\u0400'..'\u04FF' }

        if (isRussian) {
            // 俄语路径：FTS5 前缀匹配 + 变格搜索
            val queryPrefix = "$queryClean*"
            val queryMatch = "$queryClean*"
            wordDao.searchRussianWords(queryClean, queryPrefix, queryMatch)
        } else {
            // 中文路径：FTS5 精确匹配 + BKRS 释义相关性排序
            // GLOB 模式匹配搜索词后跟拼音注音（核心词义信号）
            val pinyinGlob = "*$queryClean [a-z]*"
            wordDao.searchChineseWords(queryClean, pinyinGlob)
        }
    }
}
