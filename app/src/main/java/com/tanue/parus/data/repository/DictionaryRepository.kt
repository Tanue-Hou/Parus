package com.tanue.parus.data.repository

import com.tanue.parus.data.database.WordDao
import com.tanue.parus.data.model.WordWithDetails
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class DictionaryRepository(private val wordDao: WordDao) {
    suspend fun search(query: String): List<WordWithDetails> = withContext(Dispatchers.IO) {
        val queryClean = query.trim().lowercase()
        if (queryClean.isEmpty()) return@withContext emptyList()
        val queryPrefix = "$queryClean%"
        val queryFuzzy = "%$queryClean%"
        wordDao.searchWords(queryClean, queryPrefix, queryFuzzy)
    }
}
