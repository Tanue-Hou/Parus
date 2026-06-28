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
            SELECT word_id FROM inflections WHERE form_normalized = :queryClean
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

    // 中文搜索路径：LIKE 全量匹配 + GLOB 拼音识别 + 智能相关性排序
    // 排序优先级：
    //   1) 释义以 "1) 水 [pinyin]" 或 "水 [pinyin]" 开头（"水"是第一个义项+有拼音）→ 最精确
    //   2) "水 [pinyin]" 出现在前5字符内（有拼音但不在最前面）
    //   3) "水" 出现在前5字符内（无拼音，但位置靠前）
    //   4) "水 [pinyin]" 出现在前20字符内
    //   5) "水" 出现在前20字符内
    //   6) 其他
    // 二级排序：instr 位置（越前越好），三级排序：lemma 长度（越短越基础）
    @Transaction
    @SkipQueryVerification
    @Query("""
        SELECT w.* FROM words w
        JOIN definitions d ON w.id = d.word_id
        WHERE d.definition LIKE :queryLike
        GROUP BY w.id
        ORDER BY
            MIN(CASE
                WHEN d.definition GLOB :pattern1a OR d.definition GLOB :pattern1b THEN 1
                WHEN d.definition GLOB :pinyinGlob AND instr(d.definition, :queryClean) <= 5 THEN 2
                WHEN instr(d.definition, :queryClean) <= 5 THEN 3
                WHEN d.definition GLOB :pinyinGlob AND instr(d.definition, :queryClean) <= 20 THEN 4
                WHEN instr(d.definition, :queryClean) <= 20 THEN 5
                ELSE 6
            END) ASC,
            MIN(instr(d.definition, :queryClean)) ASC,
            length(w.lemma) ASC
        LIMIT 50
    """)
    fun searchChineseWords(
        queryClean: String,
        queryLike: String,
        pattern1a: String,
        pattern1b: String,
        pinyinGlob: String
    ): List<WordWithDetails>

    // 降级方案：LIKE 搜索（FTS5 不可用时使用）
    @Transaction
    @Query("""
        SELECT w.* FROM words w
        WHERE w.lemma = :queryClean
           OR w.lemma LIKE :queryLike
           OR w.id IN (SELECT word_id FROM inflections WHERE form_normalized = :queryClean)
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
