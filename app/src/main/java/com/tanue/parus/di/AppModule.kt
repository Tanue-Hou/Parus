package com.tanue.parus.di

import androidx.room.Room
import com.tanue.parus.data.database.AppDatabase
import com.tanue.parus.data.repository.DictionaryRepository
import com.tanue.parus.presentation.search.SearchViewModel
import org.koin.android.ext.koin.androidContext
import org.koin.androidx.viewmodel.dsl.viewModel
import org.koin.dsl.module

val appModule = module {
    // 注入 Room 数据库，预填充来自 assets/database/dict.db
    single {
        Room.databaseBuilder(
            androidContext(),
            AppDatabase::class.java,
            "dict.db"
        )
        .createFromAsset("database/dict.db")
        .fallbackToDestructiveMigration()
        .addCallback(object : androidx.room.RoomDatabase.Callback() {
            override fun onOpen(db: androidx.sqlite.db.SupportSQLiteDatabase) {
                super.onOpen(db)
                try {
                    db.execSQL("CREATE VIRTUAL TABLE IF NOT EXISTS `words_fts` USING fts5(lemma, lemma_stressed, content='words', content_rowid='id')")
                    db.execSQL("CREATE VIRTUAL TABLE IF NOT EXISTS `definitions_fts` USING fts5(definition, content='definitions', content_rowid='id')")
                    val wordsCount = db.query("SELECT COUNT(*) FROM words_fts").use {
                        it.moveToFirst(); it.getInt(0)
                    }
                    if (wordsCount == 0) {
                        android.util.Log.i("ParusDB", "FTS5 words_fts 为空，开始填充 25万行...")
                        db.execSQL("INSERT INTO words_fts(rowid, lemma, lemma_stressed) SELECT id, lemma, lemma_stressed FROM words")
                        android.util.Log.i("ParusDB", "words_fts 填充完成")
                    }
                    val defsCount = db.query("SELECT COUNT(*) FROM definitions_fts").use {
                        it.moveToFirst(); it.getInt(0)
                    }
                    if (defsCount == 0) {
                        android.util.Log.i("ParusDB", "FTS5 definitions_fts 为空，开始填充 25万行...")
                        db.execSQL("INSERT INTO definitions_fts(rowid, definition) SELECT id, definition FROM definitions")
                        android.util.Log.i("ParusDB", "definitions_fts 填充完成")
                    }
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
