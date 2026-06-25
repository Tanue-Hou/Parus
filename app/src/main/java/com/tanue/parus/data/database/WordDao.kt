package com.tanue.parus.data.database

import androidx.room.Dao
import androidx.room.Query
import androidx.room.Transaction
import com.tanue.parus.data.model.WordWithDetails

@Dao
interface WordDao {
    @Transaction
    @Query("""
        SELECT DISTINCT w.* FROM words w
        LEFT JOIN inflections i ON w.id = i.word_id
        LEFT JOIN definitions d ON w.id = d.word_id
        WHERE w.lemma LIKE :queryFuzzy 
           OR i.form = :queryClean
           OR d.definition LIKE :queryFuzzy
        ORDER BY 
          CASE 
            WHEN w.lemma = :queryClean THEN 1
            WHEN w.lemma LIKE :queryPrefix THEN 2
            WHEN i.form = :queryClean THEN 3
            WHEN w.lemma LIKE :queryFuzzy THEN 4
            ELSE 5
          END ASC,
          length(w.lemma) ASC
        LIMIT 50
    """)
    fun searchWords(queryClean: String, queryPrefix: String, queryFuzzy: String): List<WordWithDetails>
}
