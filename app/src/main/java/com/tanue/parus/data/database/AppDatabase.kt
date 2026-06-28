package com.tanue.parus.data.database

import androidx.room.Database
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase
import com.tanue.parus.data.model.WordEntity
import com.tanue.parus.data.model.DefinitionEntity
import com.tanue.parus.data.model.InflectionEntity
import com.tanue.parus.data.model.ExampleEntity
import com.tanue.parus.data.model.WordStatsEntity

@Database(
    entities = [
        WordEntity::class,
        DefinitionEntity::class,
        InflectionEntity::class,
        ExampleEntity::class,
        WordStatsEntity::class
    ],
    version = 3,
    exportSchema = false
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun wordDao(): WordDao
}
