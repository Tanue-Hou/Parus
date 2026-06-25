package com.tanue.parus.data.model

import androidx.room.Embedded
import androidx.room.Relation

data class WordWithDetails(
    @Embedded val word: WordEntity,
    
    @Relation(
        parentColumn = "id",
        entityColumn = "word_id"
    )
    val definitions: List<DefinitionEntity>,
    
    @Relation(
        parentColumn = "id",
        entityColumn = "word_id"
    )
    val inflections: List<InflectionEntity>
)
