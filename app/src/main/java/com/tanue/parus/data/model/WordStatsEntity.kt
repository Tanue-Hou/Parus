package com.tanue.parus.data.model

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.PrimaryKey

@Entity(
    tableName = "word_stats",
    foreignKeys = [
        ForeignKey(
            entity = WordEntity::class,
            parentColumns = ["id"],
            childColumns = ["word_id"],
            onDelete = ForeignKey.CASCADE
        )
    ]
)
data class WordStatsEntity(
    @PrimaryKey @ColumnInfo(name = "word_id") val wordId: Int,
    @ColumnInfo(name = "frequency_rank") val frequencyRank: Int?,
    @ColumnInfo(name = "difficulty_level") val difficultyLevel: String?
)
