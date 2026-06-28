# 搜索与性能优化实施计划 (Search & Performance Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化 Parus 词典在 Android 端冷启动的加载速度（从 5-30秒降至 10毫秒内），并修复俄语变格搜索由于重音符号导致的无法反查原型的缺陷。

**Architecture:** 
1. 数据库层面将 FTS5 索引改为离线构建，App 运行时只读；在 `inflections` 表中增加去重音小写的 `form_normalized` 字段并建立普通索引。
2. App 端彻底移除 `AppModule.kt` 中冷启动全量重建 FTS5 表的逻辑。
3. App 端查询与 Repository 层输入预处理均使用去重音规范化比对，实现变格的 100% 精确匹配。

**Tech Stack:** Kotlin, Room (SQLite), Python (SQLite3, JSON)

## Global Constraints
- Android Room 数据库 Schema 必须通过编译，Version 保持为 2 或按需升级。
- 保证 `й` 不被归一化为 `и`（通过在 Python 和 App 端的 FTS5 表中使用 `unicode61 remove_diacritics 0` 分词器参数）。
- FTS5 虚拟表在 App 端的 Dao 必须通过 `@SkipQueryVerification` 来绕过编译期验证。

---

### Task 1: 数据库管道重构（离线生成 FTS5 + 变格去重音字段）

**Files:**
- Modify: `pipeline/phase3_build_db.py`
- Modify: `pipeline/utils.py`

**Interfaces:**
- Consumes: `pipeline/output/fused.jsonl`
- Produces: 预置了 `words_fts`、`definitions_fts` 表且 `inflections` 包含 `form_normalized` 字段的 `dict_v2.db`

- [ ] **Step 1: 在 `pipeline/utils.py` 中确认或添加 `clean_stress` 与 `normalize_russian` 函数**
  
  在 `pipeline/utils.py` 中添加：
  ```python
  def normalize_russian(text):
      if not text:
          return ""
      # 去除 Unicode 组合重音符 (\u0301, \u0300) 以及 ASCII 形式的重音符
      text = text.replace('\u0301', '')
      text = text.replace('\u0300', '')
      text = text.replace("'", "")
      text = text.replace("`", "")
      return text.lower().strip()
  ```

- [ ] **Step 2: 修改 `pipeline/phase3_build_db.py` 中 `inflections` 的建表与插入语句**
  
  修改 DDL：
  ```python
  # 修改 CREATE TABLE inflections 增加 form_normalized 字段与索引
  db.execute("""
      CREATE TABLE IF NOT EXISTS `inflections` (
          `id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
          `word_id` INTEGER NOT NULL,
          `form` TEXT NOT NULL,
          `form_normalized` TEXT NOT NULL,
          `grammar_tag` TEXT NOT NULL,
          FOREIGN KEY(`word_id`) REFERENCES `words`(`id`) ON UPDATE NO ACTION ON DELETE CASCADE
      )
  """)
  db.execute("CREATE INDEX IF NOT EXISTS `index_inflections_form_normalized` ON `inflections` (`form_normalized`)")
  ```
  修改插入数据逻辑，插入时计算 `form_normalized = normalize_russian(form)`。

- [ ] **Step 3: 修改 `pipeline/phase3_build_db.py` 中离线生成 FTS5 表的逻辑**
  
  在写入 entries 循环结束后，在 Python 侧离线建表并灌入索引数据：
  ```python
  print("离线构建 FTS5 虚拟表中...")
  db.execute("DROP TABLE IF EXISTS `words_fts`")
  db.execute("CREATE VIRTUAL TABLE `words_fts` USING fts5(lemma, lemma_stressed, content='words', content_rowid='id', tokenize='unicode61 remove_diacritics 0')")
  db.execute("INSERT INTO words_fts(rowid, lemma, lemma_stressed) SELECT id, lemma, lemma_stressed FROM words")
  
  db.execute("DROP TABLE IF EXISTS `definitions_fts`")
  db.execute("CREATE VIRTUAL TABLE `definitions_fts` USING fts5(definition, content='definitions', content_rowid='id', tokenize='unicode61 remove_diacritics 0')")
  db.execute("INSERT INTO definitions_fts(rowid, definition) SELECT id, definition FROM definitions")
  print("离线 FTS5 表构建完成")
  ```

- [ ] **Step 4: 运行流水线重建 `dict_v2.db`**
  
  运行：`py pipeline/phase3_build_db.py`
  预期输出：所有词条顺利写入，打印 “离线 FTS5 表构建完成”，生成 `app/src/main/assets/database/dict_v2.db`。

- [ ] **Step 5: 验证数据正确性**
  
  运行以下命令验证 `form_normalized` 字段已被正确填充：
  `py -c "import sqlite3; conn=sqlite3.connect('D:\\Android\\Parus\\app\\src\\main\\assets\\database\\dict_v2.db'); print(conn.execute('SELECT form, form_normalized FROM inflections LIMIT 5').fetchall())"`
  期待输出：第一个字段带重音/原始字符，第二个字段是不带重音的干净小写形式。

- [ ] **Step 6: Commit**
  
  ```bash
  git add pipeline/phase3_build_db.py pipeline/utils.py
  git commit -m "build: generate form_normalized and offline FTS5 in phase3"
  ```

---

### Task 2: 移除 App 冷启动的 FTS5 重建动作

**Files:**
- Modify: `app/src/main/java/com/tanue/parus/di/AppModule.kt`

**Interfaces:**
- Consumes: Task 1 生成的 `dict_v2.db`
- Produces: 极速启动的只读数据库加载生命周期

- [ ] **Step 1: 修改 `AppModule.kt`**
  
  定位到 `Room.databaseBuilder(...)` 配置块中的 `addCallback`。
  将 `onOpen` 内耗时的 `DROP`, `CREATE`, `INSERT` SQL 逻辑完全删除，只保留日志或使其为空以防卡死。
  
  修改后的 `onOpen` 应为：
  ```kotlin
  .addCallback(object : RoomDatabase.Callback() {
      override fun onOpen(db: SupportSQLiteDatabase) {
          super.onOpen(db)
          android.util.Log.i("ParusDB", "Database opened directly from asset without reconstruction.")
      }
  })
  ```

- [ ] **Step 2: Commit**
  
  ```bash
  git add app/src/main/java/com/tanue/parus/di/AppModule.kt
  git commit -m "perf: remove runtime FTS5 rebuild from AppModule"
  ```

---

### Task 3: App 实体模型与 DAO 俄语搜索逻辑重构

**Files:**
- Modify: `app/src/main/java/com/tanue/parus/data/model/InflectionEntity.kt`
- Modify: `app/src/main/java/com/tanue/parus/data/database/WordDao.kt`

**Interfaces:**
- Consumes: `form_normalized`
- Produces: 能够通过 `form_normalized` 字段高精确度匹配变格形式的 DAO 查询接口

- [ ] **Step 1: 修改 `InflectionEntity.kt` 添加字段**
  
  修改：
  ```kotlin
  @ColumnInfo(name = "form_normalized") val formNormalized: String
  ```
  更新主构造函数及成员字段。

- [ ] **Step 2: 修改 `WordDao.kt` 中的 SQL 查询**
  
  修改 `searchRussianWords` 的 SQL，把对 `form` 的比对改为对 `form_normalized` 的比对：
  ```sql
  SELECT w.* FROM words w
  WHERE w.id IN (
      SELECT rowid FROM words_fts WHERE words_fts MATCH :queryMatch
      UNION
      SELECT word_id FROM inflections WHERE form_normalized = :queryClean
  )
  ```
  同理修改 `searchFallbackRussian` 中：
  ```sql
  OR w.id IN (SELECT word_id FROM inflections WHERE form_normalized = :queryClean)
  ```

- [ ] **Step 3: 运行本地 Kotlin 编译验证**
  
  期待：编译通过无报错。

- [ ] **Step 4: Commit**
  
  ```bash
  git add app/src/main/java/com/tanue/parus/data/model/InflectionEntity.kt app/src/main/java/com/tanue/parus/data/database/WordDao.kt
  git commit -m "feat: refactor WordDao to query form_normalized for inflections"
  ```

---

### Task 4: 搜索 Repository 层查询词归一化

**Files:**
- Modify: `app/src/main/java/com/tanue/parus/data/repository/DictionaryRepository.kt`

**Interfaces:**
- Consumes: 用户输入的 query 串
- Produces: 剔除了重音符、全小写、去空格的 cleanQuery

- [ ] **Step 1: 在 `DictionaryRepository.kt` 中添加重音符号过滤逻辑**
  
  在类中添加或修改预处理函数：
  ```kotlin
  private fun normalizeQuery(query: String): String {
      return query.trim().lowercase()
          .replace("\u0301", "") // COMBINING ACUTE ACCENT
          .replace("\u0300", "") // COMBINING GRAVE ACCENT
          .replace("'", "")
          .replace("`", "")
  }
  ```

- [ ] **Step 2: 修改 `search()` 方法的 query 处理**
  
  将首行的：
  ```kotlin
  val queryClean = query.trim().lowercase()
  ```
  改为：
  ```kotlin
  val queryClean = normalizeQuery(query)
  ```

- [ ] **Step 3: Commit**
  
  ```bash
  git add app/src/main/java/com/tanue/parus/data/repository/DictionaryRepository.kt
  git commit -m "feat: normalize input queries by removing accent marks in Repository"
  ```
