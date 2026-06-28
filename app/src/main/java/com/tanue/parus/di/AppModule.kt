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
        .fallbackToDestructiveMigration()
        .addCallback(object : androidx.room.RoomDatabase.Callback() {
            override fun onOpen(db: androidx.sqlite.db.SupportSQLiteDatabase) {
                super.onOpen(db)
                android.util.Log.i("ParusDB", "Database opened directly from asset without reconstruction.")
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
