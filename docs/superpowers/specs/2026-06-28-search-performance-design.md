# Parus 搜索逻辑与冷启动性能优化设计方案

本方案旨在解决 Parus 词库近期引入的两个核心性能与搜索逻辑缺陷：
1. **冷启动卡死问题**：由于每次 `onOpen` 时在 App 运行时全量重建 30.5 万条 FTS5 倒排索引，造成冷启动卡顿数秒。
2. **变格反查失效问题**：由于变格表（`inflections`）中的 `form` 包含重音符号，与用户输入的纯净字符用等号 `=` 严格匹配时，导致变格搜索无法命中原型。

---

## 一、技术方案选择

### 1. 冷启动性能优化
* **选定方案：完全离线生成 FTS5 表，App 只读不建**
  * **实现细节**：
    1. 在 `phase3_build_db.py` 中，执行 Room DDL 建表完毕后，立即建好 `words_fts` 和 `definitions_fts` 表，并使用 `INSERT INTO` 预先灌入 30.5 万行数据。
    2. 使用与 App 一致的 `tokenize='unicode61 remove_diacritics 0'`，确保 `й` 不被归一化。
    3. 在 App 端的 `AppModule.kt` 中，彻底移除 `onOpen` 里重建 FTS5 表的 SQL 执行逻辑。
  * **收益**：冷启动时间由 5~30s 降至 **< 10ms**。

### 2. 变格与重音符号匹配优化
* **选定方案：离线标准化变格表 + App 端清洗输入**
  * **实现细节**：
    1. 数据库 `inflections` 表新增一列 `form_normalized TEXT`，存储全小写且剔除重音符号（`\u0301`, `\u0300`, `'`）的纯净变格词。
    2. 对该列创建普通数据库索引，加速 `=` 检索。
    3. 在 App 端的 `DictionaryRepository.kt` 中，将用户输入归一化：小写并去除所有重音符号。
    4. 将 `WordDao.kt` 里的变格联合查询修改为对 `form_normalized` 的等值查询。
  * **收益**：变格反查命中率从接近 0% 提升至 **> 98%**，且保持毫秒级响应。

---

## 二、具体设计细节

### 1. 数据库 Schema 变动 (`dict_v2.db`)
* **`inflections` 表结构修改**：
  ```sql
  CREATE TABLE `inflections` (
      `id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
      `word_id` INTEGER NOT NULL,
      `form` TEXT NOT NULL,
      `form_normalized` TEXT NOT NULL,  -- 新增列：去重音小写
      `grammar_tag` TEXT NOT NULL,
      FOREIGN KEY(`word_id`) REFERENCES `words`(`id`) ON UPDATE NO ACTION ON DELETE CASCADE
  );
  CREATE INDEX IF NOT EXISTS `index_inflections_form_normalized` ON `inflections` (`form_normalized`);
  ```

### 2. Python 构建脚本变动 (`pipeline/phase3_build_db.py`)
- 在提取 Room 骨架和合并 entries 时，计算变格词的 normalized 形式。
- 去除重音符号辅助函数：
  ```python
  def normalize_russian(text):
      if not text:
          return ""
      # 去除 Unicode 组合重音符号和常见的 ASCII 引号重音
      text = text.replace('\u0301', '')
      text = text.replace('\u0300', '')
      text = text.replace("'", "")
      text = text.replace("`", "")
      return text.lower().strip()
  ```
- 构建数据库时直接运行 `CREATE VIRTUAL TABLE ...` 和插入 FTS5 数据，生成已预装索引的 `dict_v2.db`。

### 3. Kotlin 代码层变动
* **`AppModule.kt`**：
  * 去除 `addCallback` 里 `onOpen` 的重建逻辑，只保留数据库的获取。
* **`WordDao.kt`**：
  * 修改 `searchRussianWords` 和 `searchFallbackRussian` 中的变格匹配：
  ```sql
  -- 原逻辑：
  SELECT word_id FROM inflections WHERE form = :queryClean
  -- 新逻辑：
  SELECT word_id FROM inflections WHERE form_normalized = :queryClean
  ```
* **`DictionaryRepository.kt`**：
  * 引入 `cleanAccent` 工具函数剥离用户可能带入的重音符号：
  ```kotlin
  private fun normalizeQuery(query: String): String {
      return query.trim().lowercase()
          .replace("\u0301", "")
          .replace("\u0300", "")
          .replace("'", "")
          .replace("`", "")
  }
  ```

---

## 三、验证与验收方案

### 1. 冷启动时间验证
- 清空应用数据，重复冷启动 5 次，监控 Logcat 中的 `ParusDB` 加载日志及搜索框呈现耗时。

### 2. 核心搜索用例验证
1. **输入原型无重音**：输入 `красивый`，应能直接命中原型 `красивый`，首位展示。
2. **输入变格无重音**：输入 `красивого`，应能反查到原型 `красивый`，并在列表里正常展示变格信息。
3. **输入带重音符号**：输入 `краси́вого`（含 `\u0301`），App 应能正确过滤重音，搜到 `красивый`。
4. **新闻例句字段排查**：确认新闻抓取的句子排除了异常的 JSON/转义字符，显示正常。
