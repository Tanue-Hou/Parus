package com.tanue.parus.data.model

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "examples",
    indices = [Index(value = ["word_id"])],
    foreignKeys = [
        ForeignKey(
            entity = WordEntity::class,
            parentColumns = ["id"],
            childColumns = ["word_id"],
            onDelete = ForeignKey.CASCADE
        )
    ]
)
data class ExampleEntity(
    @PrimaryKey(autoGenerate = true) @ColumnInfo(name = "id") val id: Int = 0,
    @ColumnInfo(name = "word_id") val wordId: Int,
    @ColumnInfo(name = "sentence_ru") val sentenceRu: String,
    @ColumnInfo(name = "sentence_zh") val sentenceZh: String,
    @ColumnInfo(name = "source") val source: String
)
