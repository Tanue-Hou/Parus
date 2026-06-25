package com.tanue.parus.data.model

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "words",
    indices = [Index(value = ["lemma"])]
)
data class WordEntity(
    @PrimaryKey @ColumnInfo(name = "id") val id: Int = 0,
    @ColumnInfo(name = "lemma") val lemma: String,
    @ColumnInfo(name = "lemma_stressed") val lemmaStressed: String,
    @ColumnInfo(name = "pos") val pos: String?
)
