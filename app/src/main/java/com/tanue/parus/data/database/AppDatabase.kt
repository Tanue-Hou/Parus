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
    version = 2,
    exportSchema = false
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun wordDao(): WordDao

    companion object {
        val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                // 1. Alter existing tables
                db.execSQL("ALTER TABLE `words` ADD COLUMN `frequency` INTEGER")
                db.execSQL("ALTER TABLE `words` ADD COLUMN `conjugation_type` INTEGER")
                db.execSQL("ALTER TABLE `definitions` ADD COLUMN `confidence` INTEGER NOT NULL DEFAULT 0")

                // 2. Create new tables
                db.execSQL("CREATE TABLE IF NOT EXISTS `examples` (`id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, `word_id` INTEGER NOT NULL, `sentence_ru` TEXT NOT NULL, `sentence_zh` TEXT NOT NULL, `source` TEXT NOT NULL, FOREIGN KEY(`word_id`) REFERENCES `words`(`id`) ON UPDATE NO ACTION ON DELETE CASCADE )")
                db.execSQL("CREATE INDEX IF NOT EXISTS `index_examples_word_id` ON `examples` (`word_id`)")

                db.execSQL("CREATE TABLE IF NOT EXISTS `word_stats` (`word_id` INTEGER NOT NULL, `frequency_rank` INTEGER, `difficulty_level` TEXT, PRIMARY KEY(`word_id`), FOREIGN KEY(`word_id`) REFERENCES `words`(`id`) ON UPDATE NO ACTION ON DELETE CASCADE )")
            }
        }
    }
}
