package com.tanue.parus.data.database

import androidx.room.Dao
import androidx.room.Query
import androidx.room.SkipQueryVerification
import androidx.room.Transaction
import com.tanue.parus.data.model.WordWithDetails

@Dao
interface WordDao {

    // 俄语搜索路径：FTS5 前缀匹配 + 变格精确匹配
    @Transaction
    @SkipQueryVerification
    @Query("""
        SELECT w.* FROM words w
        WHERE w.id IN (
            SELECT rowid FROM words_fts WHERE words_fts MATCH :queryMatch
            UNION
            SELECT word_id FROM inflections WHERE form = :queryClean
        )
        ORDER BY
            CASE
                WHEN w.lemma = :queryClean THEN 1
                WHEN w.lemma GLOB :queryPrefix THEN 2
                ELSE 3
            END ASC,
            length(w.lemma) ASC
        LIMIT 50
    """)
    fun searchRussianWords(queryClean: String, queryPrefix: String, queryMatch: String): List<WordWithDetails>

    // 中文搜索路径：FTS5 精确匹配 + BKRS 释义相关性排序
    @Transaction
    @SkipQueryVerification
    @Query("""
        SELECT w.* FROM words w
        JOIN definitions d ON w.id = d.word_id
        WHERE d.id IN (
            SELECT rowid FROM definitions_fts WHERE definitions_fts MATCH :queryClean
        )
        GROUP BY w.id
        ORDER BY
            MIN(CASE
                WHEN d.definition GLOB :pinyinGlob THEN 1
                WHEN instr(d.definition, :queryClean) <= 20 THEN 2
                ELSE 3
            END) ASC,
            MIN(length(d.definition)) ASC
        LIMIT 50
    """)
    fun searchChineseWords(queryClean: String, pinyinGlob: String): List<WordWithDetails>

    // 降级方案：LIKE 搜索（FTS5 不可用时使用）
    @Transaction
    @Query("""
        SELECT w.* FROM words w
        WHERE w.lemma = :queryClean
           OR w.lemma LIKE :queryLike
           OR w.id IN (SELECT word_id FROM inflections WHERE form = :queryClean)
        ORDER BY
            CASE
                WHEN w.lemma = :queryClean THEN 1
                WHEN w.lemma LIKE :queryLike THEN 2
                ELSE 3
            END ASC,
            length(w.lemma) ASC
        LIMIT 50
    """)
    fun searchFallbackRussian(queryClean: String, queryLike: String): List<WordWithDetails>

    @Transaction
    @Query("""
        SELECT w.* FROM words w
        WHERE w.id IN (
            SELECT word_id FROM definitions WHERE definition LIKE :queryLike
        )
        ORDER BY length(w.lemma) ASC
        LIMIT 50
    """)
    fun searchFallbackChinese(queryLike: String): List<WordWithDetails>
}
