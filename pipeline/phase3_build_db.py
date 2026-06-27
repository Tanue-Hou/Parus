"""
Phase 3 — 数据库构建脚本
=========================
读取 fused.jsonl，构建 dict_v2.db（Room schema，FTS5 全文搜索）。
不覆盖现有 dict.db。
"""

import json
import os
import sqlite3
import sys
import time

# 添加项目根到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline import config
from pipeline.utils import get_difficulty_level

# ============================================================
# 配置
# ============================================================
FUSED_JSONL = config.FUSED_JSONL
NEW_DB_PATH = config.NEW_DB_PATH
BATCH_SIZE = config.BATCH_SIZE  # 5000

# 确保输出目录存在
os.makedirs(os.path.dirname(NEW_DB_PATH), exist_ok=True)

# ============================================================
# 建表 DDL（与 Room 生成的 schema 一致）
# ============================================================

DDL_STATEMENTS = [
    # words: id 是 INTEGER NOT NULL（非 AUTOINCREMENT），需手动分配
    """CREATE TABLE IF NOT EXISTS `words` (
        `id` INTEGER NOT NULL,
        `lemma` TEXT NOT NULL,
        `lemma_stressed` TEXT NOT NULL,
        `pos` TEXT,
        `frequency` INTEGER,
        `conjugation_type` INTEGER,
        PRIMARY KEY(`id`)
    );""",
    "CREATE INDEX IF NOT EXISTS `index_words_lemma` ON `words` (`lemma`);",

    # definitions: id 是 INTEGER NOT NULL（非 AUTOINCREMENT），需手动分配
    """CREATE TABLE IF NOT EXISTS `definitions` (
        `id` INTEGER NOT NULL,
        `word_id` INTEGER NOT NULL,
        `source` TEXT NOT NULL,
        `definition` TEXT NOT NULL,
        `confidence` INTEGER NOT NULL,
        PRIMARY KEY(`id`),
        FOREIGN KEY(`word_id`) REFERENCES `words`(`id`) ON UPDATE NO ACTION ON DELETE CASCADE
    );""",
    "CREATE INDEX IF NOT EXISTS `index_definitions_word_id` ON `definitions` (`word_id`);",

    # inflections: id 是 INTEGER NOT NULL（非 AUTOINCREMENT），需手动分配
    """CREATE TABLE IF NOT EXISTS `inflections` (
        `id` INTEGER NOT NULL,
        `word_id` INTEGER NOT NULL,
        `form` TEXT NOT NULL,
        `grammar_tag` TEXT,
        PRIMARY KEY(`id`),
        FOREIGN KEY(`word_id`) REFERENCES `words`(`id`) ON UPDATE NO ACTION ON DELETE CASCADE
    );""",
    "CREATE INDEX IF NOT EXISTS `index_inflections_word_id` ON `inflections` (`word_id`);",
    "CREATE INDEX IF NOT EXISTS `index_inflections_form` ON `inflections` (`form`);",

    # examples: id 是 AUTOINCREMENT
    """CREATE TABLE IF NOT EXISTS `examples` (
        `id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
        `word_id` INTEGER NOT NULL,
        `sentence_ru` TEXT NOT NULL,
        `sentence_zh` TEXT NOT NULL,
        `source` TEXT NOT NULL,
        FOREIGN KEY(`word_id`) REFERENCES `words`(`id`) ON UPDATE NO ACTION ON DELETE CASCADE
    );""",
    "CREATE INDEX IF NOT EXISTS `index_examples_word_id` ON `examples` (`word_id`);",

    # word_stats
    """CREATE TABLE IF NOT EXISTS `word_stats` (
        `word_id` INTEGER NOT NULL,
        `frequency_rank` INTEGER,
        `difficulty_level` TEXT,
        PRIMARY KEY(`word_id`),
        FOREIGN KEY(`word_id`) REFERENCES `words`(`id`) ON UPDATE NO ACTION ON DELETE CASCADE
    );""",

    # FTS5 虚拟表（content-sync 模式，数据存储在 words/definitions 中）
    """CREATE VIRTUAL TABLE IF NOT EXISTS `words_fts` USING fts5(
        lemma, lemma_stressed,
        content='words',
        content_rowid='id'
    );""",
    """CREATE VIRTUAL TABLE IF NOT EXISTS `definitions_fts` USING fts5(
        definition,
        content='definitions',
        content_rowid='id'
    );""",
]


def create_schema(conn):
    """创建所有表、索引和 FTS5 虚拟表"""
    conn.executescript("PRAGMA foreign_keys = OFF;")  # 建表时关外键
    for ddl in DDL_STATEMENTS:
        conn.execute(ddl)
    conn.executescript("PRAGMA foreign_keys = ON;")


def rebuild_fts(conn):
    """重建 FTS5 索引（从 content 表同步数据）"""
    print("  → 重建 words_fts 索引...")
    conn.execute("INSERT INTO words_fts(words_fts) VALUES('rebuild');")
    print("  → 重建 definitions_fts 索引...")
    conn.execute("INSERT INTO definitions_fts(definitions_fts) VALUES('rebuild');")


def build_database():
    """主流程：读取 fused.jsonl → 批量插入 → FTS5 → 质量报告"""
    start_time = time.time()

    # 统计
    total_lines = 0
    word_count = 0
    def_count = 0
    infl_count = 0
    ex_count = 0
    pos_counts = {}
    skipped_no_def = 0

    # 如果已存在，删除重建
    if os.path.exists(NEW_DB_PATH):
        os.remove(NEW_DB_PATH)
        print(f"  删除已有数据库: {NEW_DB_PATH}")

    print(f"  连接数据库: {NEW_DB_PATH}")
    conn = sqlite3.connect(NEW_DB_PATH)
    conn.execute("PRAGMA journal_mode=DELETE;")
    conn.execute("PRAGMA synchronous=OFF;")  # 批量插入加速
    conn.execute("PRAGMA cache_size=-80000;")  # 80MB 缓存
    conn.execute("PRAGMA foreign_keys=ON;")

    print("  创建表结构...")
    create_schema(conn)

    # 计数器
    word_id_counter = 1
    def_id_counter = 1
    infl_id_counter = 1

    # 批量缓冲区
    words_batch = []
    defs_batch = []
    inflections_batch = []
    examples_batch = []
    stats_batch = []

    # 词频排名（按 fused.jsonl 顺序 = BKRS 排名顺序）
    rank_counter = 0

    print(f"  读取 {FUSED_JSONL} ...")
    with open(FUSED_JSONL, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            total_lines += 1

            try:
                entry = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"  ⚠ 第 {line_num} 行 JSON 解析失败: {e}")
                continue

            lemma = entry.get("lemma", "")
            lemma_stressed = entry.get("lemma_stressed", lemma)
            pos = entry.get("pos")
            definition_text = entry.get("definition")
            has_bkrs = entry.get("has_bkrs", False)

            # 跳过没有释义的词条（除非有 LLM 融合结果？这里按 BKRS 判定）
            # 但为了数据库完整性，我们仍插入 words 行，只跳过 definitions
            # 不过 fused.jsonl 中很多 punctuation 没有释义，跳过它们以节省空间
            # 策略：没有 definition 且没有 examples 且没有 inflections 的跳过
            inflections = entry.get("inflections", [])
            examples = entry.get("examples", [])

            # 插入 words
            word_id = word_id_counter
            word_id_counter += 1
            rank_counter += 1

            words_batch.append((
                word_id,
                lemma,
                lemma_stressed,
                pos,
                None,  # frequency
                None,  # conjugation_type
            ))

            # POS 统计
            if pos:
                pos_counts[pos] = pos_counts.get(pos, 0) + 1

            # 插入 definitions
            source = "BKRS" if has_bkrs else "Kaikki"
            if definition_text and definition_text.strip():
                defs_batch.append((
                    def_id_counter,
                    word_id,
                    source,
                    definition_text.strip(),
                    100,  # confidence
                ))
                def_id_counter += 1
                def_count += 1
            else:
                skipped_no_def += 1

            # 插入 inflections
            for infl in inflections:
                if len(infl) >= 2:
                    form = infl[0]
                    grammar_tag = infl[1]
                    inflections_batch.append((
                        infl_id_counter,
                        word_id,
                        form,
                        grammar_tag,
                    ))
                    infl_id_counter += 1
                    infl_count += 1

            # 插入 examples
            for ex in examples:
                ru_text = ex.get("ru", "")
                zh_text = ex.get("zh", "")
                ex_source = ex.get("source", "unknown")
                # 跳过空例句
                if not ru_text.strip() and not zh_text.strip():
                    continue
                examples_batch.append((
                    word_id,
                    ru_text.strip(),
                    zh_text.strip(),
                    ex_source,
                ))
                ex_count += 1

            # 插入 word_stats
            difficulty = get_difficulty_level(rank_counter)
            stats_batch.append((
                word_id,
                rank_counter,
                difficulty,
            ))

            word_count += 1

            # 批量写入
            if word_count % BATCH_SIZE == 0:
                _flush_batch(conn, words_batch, defs_batch, inflections_batch,
                             examples_batch, stats_batch)
                elapsed = time.time() - start_time
                print(f"  → 已处理 {word_count} 词条 ({elapsed:.1f}s)", end="\r")

    # 刷新剩余批次
    _flush_batch(conn, words_batch, defs_batch, inflections_batch,
                 examples_batch, stats_batch)
    print(f"\n  ✓ 所有数据插入完成 ({word_count} 词条)")

    # 重建 FTS5 索引
    print("  重建 FTS5 索引...")
    rebuild_fts(conn)

    # ANALYZE
    print("  运行 ANALYZE...")
    conn.execute("ANALYZE;")

    conn.commit()
    conn.close()

    elapsed = time.time() - start_time

    # ============================================================
    # 质量报告
    # ============================================================
    print("\n" + "=" * 60)
    print("  质量报告")
    print("=" * 60)
    print(f"  JSONL 总行数:     {total_lines}")
    print(f"  词条总数:         {word_count}")
    print(f"  释义总数:         {def_count}")
    print(f"  变格总数:         {infl_count}")
    print(f"  例句总数:         {ex_count}")
    print(f"  无释义跳过:       {skipped_no_def}")

    print(f"\n  POS 覆盖率:")
    sorted_pos = sorted(pos_counts.items(), key=lambda x: -x[1])
    for p, c in sorted_pos:
        print(f"    {p:>12}: {c:>6} ({c/word_count*100:5.1f}%)")

    # 文件大小
    db_size = os.path.getsize(NEW_DB_PATH)
    if db_size > 1024 * 1024:
        print(f"\n  文件大小:          {db_size / 1024 / 1024:.1f} MB")
    else:
        print(f"\n  文件大小:          {db_size / 1024:.1f} KB")

    # 搜索测试
    print(f"\n  搜索测试 (\"вода\"):")
    conn2 = sqlite3.connect(NEW_DB_PATH)
    try:
        cursor = conn2.execute(
            "SELECT w.lemma, w.lemma_stressed, w.pos, d.definition "
            "FROM words_fts f "
            "JOIN words w ON w.id = f.rowid "
            "LEFT JOIN definitions d ON d.word_id = w.id "
            "WHERE words_fts MATCH ? "
            "LIMIT 5",
            ("вода",),
        )
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                print(f"    lemma={row[0]}, stressed={row[1]}, pos={row[2]}")
                if row[3]:
                    print(f"      def: {row[3][:80]}...")
        else:
            print("    (无结果)")
    except Exception as e:
        print(f"    FTS5 搜索失败: {e}")

    # 也试试 definitions_fts
    try:
        cursor = conn2.execute(
            "SELECT w.lemma, substr(d.definition, 1, 60) "
            "FROM definitions_fts f "
            "JOIN definitions d ON d.id = f.rowid "
            "JOIN words w ON w.id = d.word_id "
            "WHERE definitions_fts MATCH ? "
            "LIMIT 3",
            ("вода",),
        )
        rows = cursor.fetchall()
        if rows:
            print(f"  definitions_fts 搜索 \"вода\":")
            for row in rows:
                print(f"    {row[0]}: {row[1]}")
    except Exception as e:
        print(f"    definitions_fts 搜索失败: {e}")

    conn2.close()

    print(f"\n  总耗时:           {elapsed:.1f}s")
    print(f"  输出路径:         {NEW_DB_PATH}")
    print("=" * 60)


def _flush_batch(conn, words_batch, defs_batch, inflections_batch,
                 examples_batch, stats_batch):
    """将缓冲区中的数据批量写入数据库"""
    if not words_batch:
        return

    conn.execute("BEGIN TRANSACTION;")
    try:
        conn.executemany(
            "INSERT OR IGNORE INTO words (id, lemma, lemma_stressed, pos, frequency, conjugation_type) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            words_batch,
        )
        if defs_batch:
            conn.executemany(
                "INSERT INTO definitions (id, word_id, source, definition, confidence) "
                "VALUES (?, ?, ?, ?, ?)",
                defs_batch,
            )
        if inflections_batch:
            conn.executemany(
                "INSERT INTO inflections (id, word_id, form, grammar_tag) "
                "VALUES (?, ?, ?, ?)",
                inflections_batch,
            )
        if examples_batch:
            conn.executemany(
                "INSERT INTO examples (word_id, sentence_ru, sentence_zh, source) "
                "VALUES (?, ?, ?, ?)",
                examples_batch,
            )
        if stats_batch:
            conn.executemany(
                "INSERT OR REPLACE INTO word_stats (word_id, frequency_rank, difficulty_level) "
                "VALUES (?, ?, ?)",
                stats_batch,
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"\n  ⚠ 批量插入失败: {e}")
        raise

    # 清空缓冲区
    words_batch.clear()
    defs_batch.clear()
    inflections_batch.clear()
    examples_batch.clear()
    stats_batch.clear()


if __name__ == "__main__":
    print("=" * 60)
    print("  Phase 3: 数据库构建")
    print("=" * 60)
    build_database()
