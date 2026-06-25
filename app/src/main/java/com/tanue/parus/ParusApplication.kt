package com.tanue.parus

import android.app.Application
import com.tanue.parus.di.appModule
import org.koin.android.ext.koin.androidContext
import org.koin.android.ext.koin.androidLogger
import org.koin.core.context.startKoin

class ParusApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        startKoin {
            androidLogger()
            androidContext(this@ParusApplication)
            modules(appModule)
        }
    }
}
