
# 搜索算法优化记录（2026-06-25）

## 执行者：思远（Siyuan）

## 瓶颈分析（基于 dict.db 实测）

| 查询 | 旧耗时 | 新耗时 | 提速 |
|------|--------|--------|------|
| вода（俄语精确） | 5297ms | 26ms | 204x |
| 水（中文搜索） | ~5000ms | 15ms | 333x |
| воду（变格→原型） | ~5000ms | 2.5ms | 2000x |

## 三个根因

1. `LIKE '%xxx%'` 全表扫描 25万行 words 表（886ms）
2. `LEFT JOIN` words×inflections×definitions 笛卡尔积膨胀到100万+行（3762ms）
3. 排序只按 `length(lemma)` 无语义相关性 → 搜"水"排第1的是介词"в"

## 三个修复

### 1. FTS5 倒排索引替代 LIKE
- `build_bkrs_db.py` 创建 `words_fts` + `definitions_fts` 虚拟表
- DAO 用 `MATCH` 替代 `LIKE '%xxx%'`
- 效果：886ms → 4.5ms

### 2. 子查询 IN 替代 LEFT JOIN
- `WHERE w.id IN (SELECT ... UNION SELECT ...)` 替代 `LEFT JOIN ... OR ...`
- 效果：3762ms → 26ms

### 3. 俄语/中文双路径分流 + BKRS释义相关性排序

**俄语路径**（输入含西里尔字母）:
- FTS5 MATCH 前缀 + 变格精确匹配
- 排序：精确匹配 > 前缀匹配 > 变格匹配

**中文路径**（输入不含西里尔字母）:
- FTS5 MATCH 精确 token + GROUP BY 去重
- 排序：`GLOB '*词 [a-z]*'` 匹配拼音注音(核心词义) > 释义前20字符出现 > 其他
- 利用 BKRS 格式特征：核心词义后跟拼音（如 "水 shuǐ"、"书 shū"）

## 改动文件

| 文件 | 改动 |
|------|------|
| WordDao.kt | searchWords → searchRussianWords + searchChineseWords |
| DictionaryRepository.kt | 西里尔字母检测(\u0400-\u04FF)自动分流 |
| build_bkrs_db.py | hash 检查增加 FTS5 表存在性验证 |

## 给其他智能体的注意事项

1. `WordDao.searchWords` 已不存在，改用 `searchRussianWords` 或 `searchChineseWords`
2. `DictionaryRepository.search()` 内部自动分流，外部接口不变
3. dict.db 的 FTS5 表(words_fts, definitions_fts)不在 Room @Entity 中定义，Room 不跟踪其 schema 变更
4. `build_bkrs_db.py` 的 hash 检查现在会额外验证 FTS5 表存在性
5. `@SkipQueryVerification` 是必须的，因为 Room 不认识 FTS5 虚拟表
