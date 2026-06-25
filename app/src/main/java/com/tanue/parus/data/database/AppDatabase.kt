package com.tanue.parus.data.database

import androidx.room.Database
import androidx.room.RoomDatabase
import com.tanue.parus.data.model.WordEntity
import com.tanue.parus.data.model.DefinitionEntity
import com.tanue.parus.data.model.InflectionEntity

@Database(
    entities = [
        WordEntity::class,
        DefinitionEntity::class,
        InflectionEntity::class
    ],
    version = 1,
    exportSchema = false
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun wordDao(): WordDao
}
