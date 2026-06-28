package com.tanue.parus.di

import androidx.room.Room
import com.tanue.parus.data.database.AppDatabase
import com.tanue.parus.data.repository.DictionaryRepository
import com.tanue.parus.presentation.search.SearchViewModel
import org.koin.android.ext.koin.androidContext
import org.koin.androidx.viewmodel.dsl.viewModel
import org.koin.dsl.module

val appModule = module {
    // 注入 Room 数据库，预填充来自 assets/database/dict_v2.db
    single {
        Room.databaseBuilder(
            androidContext(),
            AppDatabase::class.java,
            "dict.db"
        )
        .createFromAsset("database/dict_v2.db")
        .addMigrations(AppDatabase.MIGRATION_1_2)
        .fallbackToDestructiveMigration()
        .addCallback(object : androidx.room.RoomDatabase.Callback() {
            override fun onOpen(db: androidx.sqlite.db.SupportSQLiteDatabase) {
                super.onOpen(db)
                try {
                    // 重建 FTS5 索引（确保与DB数据一致）
                    // 使用 unicode61 tokenizer，关闭变音符号移除，避免 й→и 归一化
                    db.execSQL("DROP TABLE IF EXISTS `words_fts`")
                    db.execSQL("CREATE VIRTUAL TABLE `words_fts` USING fts5(lemma, lemma_stressed, content='words', content_rowid='id', tokenize='unicode61 remove_diacritics 0')")
                    db.execSQL("INSERT INTO words_fts(rowid, lemma, lemma_stressed) SELECT id, lemma, lemma_stressed FROM words")
                    android.util.Log.i("ParusDB", "words_fts 重建完成")
                    db.execSQL("DROP TABLE IF EXISTS `definitions_fts`")
                    db.execSQL("CREATE VIRTUAL TABLE `definitions_fts` USING fts5(definition, content='definitions', content_rowid='id', tokenize='unicode61 remove_diacritics 0')")
                    db.execSQL("INSERT INTO definitions_fts(rowid, definition) SELECT id, definition FROM definitions")
                    android.util.Log.i("ParusDB", "definitions_fts 重建完成")
                } catch (e: Exception) {
                    android.util.Log.e("ParusDB", "FTS5 初始化失败，将使用 LIKE 降级搜索", e)
                }
            }
        })
        .build()
    }
    
    // 注入 DAO
    single { get<AppDatabase>().wordDao() }
    
    // 注入 Repository
    single { DictionaryRepository(get()) }
    
    // 注入 ViewModel
    viewModel { SearchViewModel(get()) }
}
