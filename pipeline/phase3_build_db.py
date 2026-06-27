"""
Phase 3 — 数据库构建脚本 (多源语义融合版)
===========================================
1. 从 AppDatabase_Impl.java 动态提取 Room Schema DDL 语句和 Master Hash，确保 Schema 100% 合规。
2. 读取 fused.jsonl，同时加载 llm_cache.json。
3. 如果词条已在 llm_cache.json 中，则使用 LLM 融合后的释义（体和接格前置），并标记 source='AI-Fused', confidence=3。
4. 构建 dict_v2.db 并生成 FTS5 全文检索索引。
"""

import json
import os
import sqlite3
import sys
import time
import re

# 添加项目根到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline import config
from pipeline.utils import get_difficulty_level

# ============================================================
# 工具函数
# ============================================================

def strip_stress(text):
    """去除重音标记"""
    if not text:
        return ""
    text = text.replace('\u0301', '')
    text = text.replace('`', '')
    text = text.replace('\'', '')
    return text

# ============================================================
# 配置
# ============================================================
FUSED_JSONL = config.FUSED_JSONL
LLM_CACHE_JSON = config.LLM_CACHE_JSON
NEW_DB_PATH = config.NEW_DB_PATH
BATCH_SIZE = config.BATCH_SIZE  # 5000

# 确保输出目录存在
os.makedirs(os.path.dirname(NEW_DB_PATH), exist_ok=True)

def extract_room_statements():
    """从 Room 生成的 AppDatabase_Impl.java 中动态提取所有 SQL DDL 语句 (包括建表、索引、room_master_table 等)"""
    impl_path = os.path.join(
        config.PROJECT_ROOT, 
        "app", "build", "generated", "ksp", "debug", "java", 
        "com", "tanue", "parus", "data", "database", "AppDatabase_Impl.java"
    )
    if not os.path.exists(impl_path):
        print(f"\n[ERROR] Room implementation file not found at: {impl_path}")
        print("Please compile the Android project first using compileDebugKotlin!")
        sys.exit(1)
        
    with open(impl_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    match = re.search(r"public void createAllTables\(@NonNull final SupportSQLiteDatabase db\) \{(.*?)\}", content, re.DOTALL)
    if not match:
        print("[ERROR] Could not find createAllTables method in AppDatabase_Impl.java")
        sys.exit(1)
        
    body = match.group(1)
    statements = []
    for line in body.split('\n'):
        line = line.strip()
        sql_match = re.search(r'db\.execSQL\("(.*?)"\);', line)
        if sql_match:
            statements.append(sql_match.group(1))
            
    return statements

def load_llm_cache():
    """加载 LLM 融合缓存"""
    if os.path.exists(LLM_CACHE_JSON):
        try:
            with open(LLM_CACHE_JSON, "r", encoding="utf-8") as f:
                cache = json.load(f)
            print(f"  [LLM Cache] Loaded {len(cache)} fused definitions.")
            return cache
        except Exception as e:
            print(f"  [LLM Cache] Warning: Failed to load cache ({e}), bypassing LLM results.")
            return {}
    else:
        print("  [LLM Cache] Cache not found, bypassing LLM results.")
        return {}

def build_database():
    """主流程：读取 fused.jsonl + llm_cache.json → 批量插入 → FTS5 → 校验报告"""
    start_time = time.time()

    # 1. 提取 Room DDL 语句
    print("  Extracting Room DDL statements and Master Hash...")
    ddl_statements = extract_room_statements()
    print(f"  Extracted {len(ddl_statements)} SQL statements.")

    # 2. 加载 LLM 缓存
    llm_cache = load_llm_cache()
    
    # 2b. 加载 AI 翻译缓存（P1-1: Kaikki-only词条翻译）
    ai_translated = {}
    ai_translated_path = os.path.join(os.path.dirname(FUSED_JSONL), "ai_translated.json")
    if os.path.exists(ai_translated_path):
        try:
            with open(ai_translated_path, "r", encoding="utf-8") as f:
                ai_translated = json.load(f)
            print(f"  [AI Translated] Loaded {len(ai_translated)} translated definitions.")
        except Exception as e:
            print(f"  [AI Translated] Warning: Failed to load ({e})")

    # 3. 初始化数据库
    if os.path.exists(NEW_DB_PATH):
        os.remove(NEW_DB_PATH)
        print(f"  Removed old database: {NEW_DB_PATH}")

    print(f"  Connecting to database: {NEW_DB_PATH}")
    conn = sqlite3.connect(NEW_DB_PATH, isolation_level=None)
    conn.execute("PRAGMA journal_mode=DELETE;")
    conn.execute("PRAGMA synchronous=OFF;")  # 批量插入加速
    conn.execute("PRAGMA cache_size=-80000;")  # 80MB 缓存
    conn.execute("PRAGMA foreign_keys=ON;")

    # 4. 创建 Room 表结构和插入 Master Hash
    print("  Creating Room core tables and inserting Master Hash...")
    conn.execute("PRAGMA foreign_keys = OFF;")
    for ddl in ddl_statements:
        conn.execute(ddl)
    conn.execute("PRAGMA foreign_keys = ON;")

    # 5. 创建 FTS5 虚拟表 (content-sync 模式)
    print("  Creating FTS5 virtual tables...")
    conn.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS `words_fts` USING fts5(
        lemma, lemma_stressed,
        content='words',
        content_rowid='id'
    );""")
    conn.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS `definitions_fts` USING fts5(
        definition,
        content='definitions',
        content_rowid='id'
    );""")

    # 6. 数据统计与插入
    total_lines = 0
    word_count = 0
    def_count = 0
    infl_count = 0
    ex_count = 0
    llm_fused_count = 0
    bkrs_count = 0
    pos_counts = {}
    skipped_no_def = 0
    skipped_kaikki_only = 0
    skipped_junk = 0  # P0-4
    infl_dedup_count = 0  # P0-2
    ex_etymology_filtered = 0  # P0-3

    # 数据库自增 ID 计数器
    word_id_counter = 1
    def_id_counter = 1
    infl_id_counter = 1

    # 批量缓冲区
    words_batch = []
    defs_batch = []
    inflections_batch = []
    examples_batch = []
    stats_batch = []

    rank_counter = 0

    print(f"  Reading {FUSED_JSONL} and inserting entities...")
    with open(FUSED_JSONL, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            total_lines += 1

            try:
                entry = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"  [WARN] Line {line_num} JSON decode error: {e}")
                continue

            lemma = entry.get("lemma", "")
            lemma_stressed = entry.get("lemma_stressed", lemma)
            pos = entry.get("pos")
            # 中文词性→英文标准标签
            POS_MAP = {
                "名词": "noun", "名": "noun", "名词，阳性": "noun",
                "动词": "verb", "动": "verb",
                "形容词": "adj", "形": "adj",
                "副词": "adv",
                "专有名词": "name",
                "感叹词": "intj", "叹词": "intj",
                "数词": "num",
                "谚语": "proverb",
                "连词": "conj",
                "短语": "phrase",
            }
            if pos in POS_MAP:
                pos = POS_MAP[pos]
            definition_text = entry.get("definition")
            has_bkrs = entry.get("has_bkrs", False)

            # 跳过没有 BKRS 释义的词条（Kaikki-only），减小数据库体积
            # P1-1: 如果有 AI 翻译则入库
            if not has_bkrs:
                if lemma in ai_translated:
                    # 使用 AI 翻译的释义
                    trans = ai_translated[lemma]
                    definition_text = trans.get("definition", definition_text)
                    # 翻译的pos是中文，需要映射
                    trans_pos = trans.get("pos", "")
                    if trans_pos in POS_MAP:
                        pos = POS_MAP[trans_pos]
                    elif trans_pos:
                        pos = trans_pos
                    # source 和 confidence 在下面统一设置
                else:
                    skipped_kaikki_only += 1
                    continue

            # P0-4: 垃圾词过滤
            JUNK_POS = {"punct", "symbol", "character"}
            VALID_SINGLE_CHARS = {"а", "и", "в", "к", "с", "у", "о", "б", "я"}
            if pos in JUNK_POS:
                skipped_junk += 1
                continue
            if len(lemma) <= 1 and lemma not in VALID_SINGLE_CHARS:
                skipped_junk += 1
                continue
            if lemma.startswith('"') or ('"' in lemma and lemma.count('"') >= 2):
                skipped_junk += 1
                continue
            # 过滤非西里尔词条（bts, gac trumpchi, c-moll, 200, 300 等）
            if lemma and not any('\u0400' <= c <= '\u04ff' for c in lemma):
                skipped_junk += 1
                continue

            # 插入 words
            word_id = word_id_counter
            word_id_counter += 1
            rank_counter += 1

            words_batch.append((
                word_id,
                lemma,
                lemma_stressed,
                pos,
                entry.get("or_frequency"),    # frequency (from OpenRussian)
                entry.get("conjugation_type", 0),  # conjugation_type (inferred)
            ))

            if pos:
                pos_counts[pos] = pos_counts.get(pos, 0) + 1

            # 7. LLM 语义融合释义处理
            # 先重置source，但保留AI-Translated
            if has_bkrs:
                source = "BKRS"
                confidence = 100
            elif lemma in ai_translated:
                source = "AI-Translated"
                confidence = 2
            else:
                source = "BKRS"
                confidence = 100
            
            # P1-1: AI-Translated 跳过LLM融合
            if has_bkrs:
                # 优先从 llm_cache 中获取融合释义
                if lemma in llm_cache:
                    cache_entry = llm_cache[lemma]
                    fused_def = cache_entry.get("definition")
                    if fused_def:
                        definition_text = fused_def.strip()
                        gov = cache_entry.get("government")
                        asp = cache_entry.get("aspect")
                        notes = []
                        if gov and gov not in ("null", "None"):
                            notes.append(f"【接格】{gov}")
                        if asp and asp not in ("null", "None"):
                            notes.append(f"【体】{asp}")
                        if notes:
                            definition_text = " / ".join(notes) + "\n" + definition_text
                        
                        source = "AI-Fused"
                        confidence = 3
                        llm_fused_count += 1
                
                if source == "BKRS" and definition_text:
                    bkrs_count += 1

            # 插入 definitions
            if definition_text and definition_text.strip():
                # P2-3: HTML标签清理
                import html
                definition_text = html.unescape(definition_text)
                definition_text = re.sub(r'<[^>]+>', '', definition_text)
                definition_text = re.sub(r'\s+', ' ', definition_text).strip()
                
                # P2-4: 极短释义/参见释义降权
                short_def = len(definition_text) < 4 or definition_text.startswith('см.') or 'см.' in definition_text[:10]
                if short_def:
                    confidence = 0
                
                defs_batch.append((
                    def_id_counter,
                    word_id,
                    source,
                    definition_text.strip(),
                    confidence,
                ))
                def_id_counter += 1
                def_count += 1
            else:
                skipped_no_def += 1

            # 插入 inflections
            inflections = entry.get("inflections", [])
            seen_infl = set()  # P0-2: per-word级别去重
            for infl in inflections:
                if len(infl) >= 2:
                    form = infl[0]
                    grammar_tag = infl[1]
                    # P0-2: 去重键 = (去重音小写词形, grammar_tag)
                    dedup_key = (
                        form.replace("'", "").replace("\u0301", "").lower(),
                        grammar_tag
                    )
                    if dedup_key in seen_infl:
                        infl_dedup_count += 1
                        continue
                    seen_infl.add(dedup_key)
                    # P1-2: 统一重音格式：ASCII单引号 → Unicode组合重音
                    form = re.sub(r"'(?=[а-яё])", "\u0301", form)
                    inflections_batch.append((
                        infl_id_counter,
                        word_id,
                        form,
                        grammar_tag,
                    ))
                    infl_id_counter += 1
                    infl_count += 1

            # 插入 examples
            examples = entry.get("examples", [])
            for ex in examples:
                ru_text = ex.get("ru", "")
                zh_text = ex.get("zh", "")
                ex_source = ex.get("source", "unknown")

                # P0-3: 过滤词源分析冒充例句（含→箭头 或 超过3个括号）
                if '\u2192' in ru_text or '\u27f6' in ru_text or ru_text.count('(') > 3:
                    ex_etymology_filtered += 1
                    continue
                # P0-3: 过滤过短“例句”（少与5个字符）
                if len(ru_text.strip()) < 5:
                    ex_etymology_filtered += 1
                    continue

                # Strip all stress marks from example text
                ru_text = strip_stress(ru_text)
                zh_text = strip_stress(zh_text)

                # BKRS-embedded: keep all examples (no filtering)
                if ex_source == "BKRS-embedded":
                    if ru_text.strip():
                        examples_batch.append((
                            word_id,
                            ru_text.strip(),
                            zh_text.strip(),
                            ex_source,
                        ))
                        ex_count += 1
                    continue

                # Other sources: only filter empty ru (allow empty zh for News)
                if not ru_text.strip():
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
                print(f"  -> Processed {word_count} lemmas ({elapsed:.1f}s)", end="\r")

    # 刷新剩余批次
    _flush_batch(conn, words_batch, defs_batch, inflections_batch,
                 examples_batch, stats_batch)
    print(f"\n  [OK] All data inserted ({word_count} lemmas)")

    # 7b. 用 frequency_rank 反向填充 words.frequency (rank 1=最高频 → frequency 最大)
    print("  Backfilling words.frequency from word_stats.frequency_rank...")
    conn.execute("""
        UPDATE words SET frequency = (
            SELECT MAX(frequency_rank) FROM word_stats
        ) - (
            SELECT frequency_rank FROM word_stats WHERE word_stats.word_id = words.id
        ) + 1
    """)
    populated = conn.execute("SELECT COUNT(*) FROM words WHERE frequency > 0").fetchone()[0]
    print(f"  [OK] frequency populated for {populated} words")

    # 8. 重建 FTS5 索引
    print("  Rebuilding FTS5 indexes...")
    conn.execute("INSERT INTO words_fts(words_fts) VALUES('rebuild');")
    conn.execute("INSERT INTO definitions_fts(definitions_fts) VALUES('rebuild');")

    print("  Running ANALYZE...")
    conn.execute("ANALYZE;")

    # 设置 Room 数据库版本号 (必须匹配 @Database(version = 2))
    print("  Setting PRAGMA user_version = 2")
    conn.execute("PRAGMA user_version = 2;")

    conn.commit()
    conn.close()

    elapsed = time.time() - start_time

    # ============================================================
    # 质量报告
    # ============================================================
    print("\n" + "=" * 60)
    print("  Database Integrity Report (Phase 3)")
    print("=" * 60)
    print(f"  JSONL Total Lines: {total_lines}")
    print(f"  Total Words:       {word_count}")
    print(f"  Total Definitions: {def_count}")
    print(f"    + AI-Fused:      {llm_fused_count} ({llm_fused_count/def_count*100:.2f}%)")
    print(f"    + BKRS:          {bkrs_count} ({bkrs_count/def_count*100:.2f}%)")
    print(f"  Total Inflections: {infl_count}")
    print(f"  Total Examples:    {ex_count}")
    print(f"  No Definition:     {skipped_no_def}")
    print(f"  Kaikki-only skip:  {skipped_kaikki_only}")
    print(f"  Junk words skip:   {skipped_junk}")
    print(f"  Infl dedup drop:   {infl_dedup_count}")
    print(f"  Etymology ex filt: {ex_etymology_filtered}")

    print(f"\n  POS Distribution:")
    sorted_pos = sorted(pos_counts.items(), key=lambda x: -x[1])
    for p, c in sorted_pos:
        print(f"    {p:>12}: {c:>6} ({c/word_count*100:5.1f}%)")

    # 文件大小
    db_size = os.path.getsize(NEW_DB_PATH)
    print(f"\n  File Size:         {db_size / 1024 / 1024:.2f} MB")
    print(f"  Total Time:        {elapsed:.1f}s")
    print(f"  Output Path:       {NEW_DB_PATH}")
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
        print(f"\n  [WARN] Batch insert failed: {e}")
        raise

    # 清空缓冲区
    words_batch.clear()
    defs_batch.clear()
    inflections_batch.clear()
    examples_batch.clear()
    stats_batch.clear()


if __name__ == "__main__":
    print("=" * 60)
    print("  Phase 3: Database Construction (Compliance & LLM Cache Merge)")
    print("=" * 60)
    build_database()
