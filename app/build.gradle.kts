plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.ksp)
}

android {
    namespace = "com.tanue.parus"
    compileSdk {
        version = release(36) {
            minorApiLevel = 1
        }
    }

    defaultConfig {
        applicationId = "com.tanue.parus"
        minSdk = 24
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        release {
            optimization {
                enable = false
            }
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
    buildFeatures {
        compose = true
    }
}

dependencies {
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    testImplementation(libs.junit)
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.compose.ui.test.junit4)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(libs.androidx.junit)
    debugImplementation(libs.androidx.compose.ui.test.manifest)
    debugImplementation(libs.androidx.compose.ui.tooling)

    // Room Database
    implementation(libs.androidx.room.runtime)
    implementation(libs.androidx.room.ktx)
    ksp(libs.androidx.room.compiler)

    // Koin Dependency Injection
    implementation(libs.koin.android)
    implementation(libs.koin.compose)

    // Navigation Compose
    implementation(libs.androidx.navigation.compose)

    // Material Icons (Spotlight Clear and Search icons)
    implementation("androidx.compose.material:material-icons-extended")
}

// 自动编译/检验本地 SQLite 词典数据库的 Gradle 自定义任务
tasks.register<Exec>("runDbCompiler") {
    val osName = System.getProperty("os.name").lowercase()
    val isWindows = osName.contains("win")
    if (isWindows) {
        commandLine("cmd", "/c", "py", "${project.rootDir}/pipeline/phase3_build_db.py")
    } else {
        commandLine("python3", "${project.rootDir}/pipeline/phase3_build_db.py")
    }
    workingDir = project.rootDir
}

// 确保在 KSP 编译器生成 Room 数据映射类 (AppDatabase_Impl) 之后再运行数据库编译器
tasks.named("runDbCompiler") {
    dependsOn(tasks.matching { it.name.startsWith("ksp") && it.name.endsWith("Kotlin") })
}

// 在合并 assets 资源打包进 APK 之前，自动运行我们的数据库编译器检查
tasks.whenTaskAdded {
    if (name.startsWith("merge") && name.endsWith("Assets")) {
        dependsOn("runDbCompiler")
    }
}