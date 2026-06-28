package com.tanue.parus.data.model

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "inflections",
    indices = [
        Index(value = ["word_id"]),
        Index(value = ["form_normalized"])
    ],
    foreignKeys = [
        ForeignKey(
            entity = WordEntity::class,
            parentColumns = ["id"],
            childColumns = ["word_id"],
            onDelete = ForeignKey.CASCADE
        )
    ]
)
data class InflectionEntity(
    @PrimaryKey @ColumnInfo(name = "id") val id: Int = 0,
    @ColumnInfo(name = "word_id") val wordId: Int,
    @ColumnInfo(name = "form") val form: String,
    @ColumnInfo(name = "form_normalized") val formNormalized: String,
    @ColumnInfo(name = "grammar_tag") val grammarTag: String?
)
