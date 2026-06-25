import gzip
import json
import os
import re
import sqlite3
import unicodedata
import sys

# Paths
DB_DIR = os.path.join("app", "src", "main", "assets", "database")
DB_PATH = os.path.join(DB_DIR, "dict.db")
BKRS_GZ = r"C:\Users\Tanue Hou\.gemini\antigravity\brain\c6799849-977e-4cbd-94b1-ea495082674e\scratch\dabruks_260625.gz"
KAIKKI_JSONL = r"C:\Users\Tanue Hou\Downloads\kaikki.org-dictionary-Russian.jsonl"
IMPL_PATH = r"app\build\generated\ksp\debug\java\com\tanue\parus\data\database\AppDatabase_Impl.java"

def clean_stress(text):
    """
    Remove Russian stress marks (Combining Acute Accent, \u0301) and lowercase the text.
    """
    if not text:
        return ""
    text = text.replace('\u0301', '')
    normalized = unicodedata.normalize('NFD', text)
    cleaned = "".join(c for c in normalized if unicodedata.category(c) != 'Mn')
    return cleaned.lower().strip()

def clean_dsl_text(text):
    """
    Clean ABBYY Lingvo/DSL markup tags to produce clean human-readable text.
    """
    if not text:
        return ""
    # 1. Replace escaped brackets with temporary placeholders
    text = text.replace(r'\[', '\u0001').replace(r'\]', '\u0002')
    # 2. Replace ending tags [/m], [/*] with newline to separate definitions and examples
    text = text.replace('[/m]', '\n').replace('[/*]', '\n')
    # 3. Replace tag [*] with bullet point
    text = text.replace('[*]', '• ')
    # 4. Remove all remaining DSL tags like [m1], [i], etc.
    text = re.sub(r'\[.*?\]', '', text)
    # 5. Restore literal brackets
    text = text.replace('\u0001', '[').replace('\u0002', ']')
    # 6. Clean up line spaces and consecutive newlines
    lines = [line.strip() for line in text.split('\n')]
    # Filter out empty lines
    lines = [line for line in lines if line]
    return '\n'.join(lines)

def extract_room_statements():
    """
    Dynamically extract table and index creation statements from Room's generated implementation class.
    """
    if not os.path.exists(IMPL_PATH):
        print(f"\n[ERROR] Room implementation file not found at: {IMPL_PATH}")
        print("==========================================================================")
        print("请先在 Android Studio 中编译或 Make Project，然后再运行本脚本！")
        print("编译后，Room 会自动生成 AppDatabase_Impl.java 文件以供脚本读取其内部结构。")
        print("==========================================================================\n")
        sys.exit(1)
        
    with open(IMPL_PATH, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Find the body of createAllTables method
    match = re.search(r"public void createAllTables\(@NonNull final SupportSQLiteDatabase db\) \{(.*?)\}", content, re.DOTALL)
    if not match:
        print("[ERROR] Could not find createAllTables method in AppDatabase_Impl.java")
        sys.exit(1)
        
    body = match.group(1)
    
    # Extract all db.execSQL statements
    statements = []
    for line in body.split('\n'):
        line = line.strip()
        sql_match = re.search(r'db\.execSQL\("(.*?)"\);', line)
        if sql_match:
            statements.append(sql_match.group(1))
            
    if not statements:
        print("[ERROR] No SQL statements found in createAllTables")
        sys.exit(1)
        
    return statements

def build_database():
    print("Step 1: Checking schema and validating hash...")
    statements = extract_room_statements()
    
    # Extract identity hash
    current_hash = None
    for stmt in statements:
        match = re.search(r"VALUES\(42,\s*'(.*?)'\)", stmt)
        if match:
            current_hash = match.group(1)
            break
            
    # Check if DB already exists and has the same hash AND FTS5 tables
    if current_hash and os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            existing_hash = cursor.execute("SELECT identity_hash FROM room_master_table LIMIT 1").fetchone()[0]
            # FTS5 表存在性检查 — Room hash 不跟踪 FTS5 虚拟表
            fts_exists = cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='words_fts'").fetchone()
            conn.close()
            if existing_hash == current_hash and fts_exists:
                print(f"[INFO] Database is up-to-date (hash: {current_hash}). Skipping compilation.")
                print("==================================================")
                print("数据库结构未改变且 FTS5 索引已存在，已跳过编译，节省时间！")
                print("==================================================")
                return
            elif existing_hash == current_hash and not fts_exists:
                print("[INFO] Room schema unchanged but FTS5 tables missing. Rebuilding FTS5 index...")
        except Exception:
            pass

    print("Step 2: Parsing BKRS Russian-Chinese dictionary...")
    if not os.path.exists(BKRS_GZ):
        print(f"Error: BKRS database file not found at: {BKRS_GZ}")
        sys.exit(1)
        
    bkrs_entries = {}  # clean_lemma -> {"stressed": original_lemma, "definitions": list, "pos": str}
    
    with gzip.open(BKRS_GZ, "rt", encoding="utf-8-sig", errors="replace") as f:
        current_word = None
        current_def_lines = []
        
        for line in f:
            line = line.strip('\r\n')
            if not line:
                continue
            if line.startswith('#'):
                continue
            
            if line.startswith(' ') or line.startswith('\t'):
                if current_word:
                    current_def_lines.append(line)
            else:
                if current_word:
                    raw_def = "\n".join(current_def_lines)
                    clean_def = clean_dsl_text(raw_def)
                    if clean_def:
                        clean_word = clean_stress(current_word)
                        # We merge definitions if the word already exists
                        if clean_word in bkrs_entries:
                            bkrs_entries[clean_word]["definitions"].append(clean_def)
                        else:
                            bkrs_entries[clean_word] = {
                                "stressed": current_word,
                                "definitions": [clean_def],
                                "pos": None
                            }
                current_word = line.strip()
                current_def_lines = []
                
        # Handle the last word
        if current_word and current_def_lines:
            raw_def = "\n".join(current_def_lines)
            clean_def = clean_dsl_text(raw_def)
            if clean_def:
                clean_word = clean_stress(current_word)
                if clean_word in bkrs_entries:
                    bkrs_entries[clean_word]["definitions"].append(clean_def)
                else:
                    bkrs_entries[clean_word] = {
                        "stressed": current_word,
                        "definitions": [clean_def],
                        "pos": None
                    }
                    
    print(f"Parsed {len(bkrs_entries)} unique BKRS lemmas.")
    
    # Step 3: Extracting inflections from Wiktionary if available
    inflections_map = {}  # clean_lemma -> set of (clean_form, tag)
    if os.path.exists(KAIKKI_JSONL):
        print("Step 3: Wiktionary file detected. Parsing inflections...")
        try:
            with open(KAIKKI_JSONL, "r", encoding="utf-8") as f:
                count = 0
                for line in f:
                    count += 1
                    if count % 100000 == 0:
                        print(f"Processed {count} Wiktionary lines...", end="\r")
                    
                    entry = json.loads(line)
                    word_stressed = entry.get("word", "").strip()
                    if not word_stressed:
                        continue
                    
                    clean_lemma = clean_stress(word_stressed)
                    if clean_lemma in bkrs_entries:
                        # Extract part of speech if we don't have it yet
                        pos = entry.get("pos", "")
                        if pos and bkrs_entries[clean_lemma]["pos"] is None:
                            bkrs_entries[clean_lemma]["pos"] = pos
                            
                        # Extract forms
                        forms_list = entry.get("forms", [])
                        for form_entry in forms_list:
                            raw_form = form_entry.get("form", "").strip()
                            if raw_form:
                                clean_form = clean_stress(raw_form)
                                if clean_form and clean_form != clean_lemma:
                                    tags = ",".join(form_entry.get("tags", []))
                                    if clean_lemma not in inflections_map:
                                        inflections_map[clean_lemma] = set()
                                    inflections_map[clean_lemma].add((clean_form, tags))
            print(f"\nExtracted inflections for {len(inflections_map)} lemmas.")
        except Exception as e:
            print(f"\nWarning: Failed to parse Wiktionary inflections: {e}. Skipping inflections.")
    else:
        print("Step 3: Wiktionary file not found. Skipping inflections parsing.")
        
    # Step 4: Write to SQLite database
    print("Step 4: Compiling SQLite database...")
    os.makedirs(DB_DIR, exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Initialize DB schemas extracted from Room
    for stmt in statements:
        cursor.execute(stmt)
        
    # Create FTS5 virtual tables for high-performance fuzzy and full-text search
    cursor.execute("CREATE VIRTUAL TABLE IF NOT EXISTS `words_fts` USING fts5(lemma, lemma_stressed, content='words', content_rowid='id');")
    cursor.execute("CREATE VIRTUAL TABLE IF NOT EXISTS `definitions_fts` USING fts5(definition, content='definitions', content_rowid='id');")
    conn.commit()
    
    words_count = 0
    definitions_count = 0
    inflections_count = 0
    
    # Disable journal and sync for fast insertion
    cursor.execute("PRAGMA journal_mode = OFF;")
    cursor.execute("PRAGMA synchronous = OFF;")
    
    word_id_counter = 1
    def_id_counter = 1
    inf_id_counter = 1
    
    for clean_lemma, data in bkrs_entries.items():
        # Insert into words
        cursor.execute(
            "INSERT INTO words (id, lemma, lemma_stressed, pos) VALUES (?, ?, ?, ?)",
            (word_id_counter, clean_lemma, data["stressed"], data["pos"])
        )
        current_word_id = word_id_counter
        word_id_counter += 1
        words_count += 1
        
        # Insert definitions
        for definition in data["definitions"]:
            cursor.execute(
                "INSERT INTO definitions (id, word_id, source, definition) VALUES (?, ?, ?, ?)",
                (def_id_counter, current_word_id, "BKRS", definition)
            )
            def_id_counter += 1
            definitions_count += 1
            
        # Insert inflections
        if clean_lemma in inflections_map:
            for clean_form, tags in inflections_map[clean_lemma]:
                cursor.execute(
                    "INSERT INTO inflections (id, word_id, form, grammar_tag) VALUES (?, ?, ?, ?)",
                    (inf_id_counter, current_word_id, clean_form, tags)
                )
                inf_id_counter += 1
                inflections_count += 1
                
        if words_count % 10000 == 0:
            print(f"Inserted {words_count} words into DB...", end="\r")
            
    print("\nStep 5: Populating FTS5 virtual tables...")
    cursor.execute("INSERT INTO words_fts(rowid, lemma, lemma_stressed) SELECT id, lemma, lemma_stressed FROM words;")
    cursor.execute("INSERT INTO definitions_fts(rowid, definition) SELECT id, definition FROM definitions;")
    conn.commit()
    conn.close()
    
    print("\n" + "="*50)
    print("Database built successfully!")
    print(f"Total Words: {words_count}")
    print(f"Total Definitions: {definitions_count}")
    print(f"Total Inflections: {inflections_count}")
    print(f"Output Database: {DB_PATH}")
    print("="*50)

if __name__ == "__main__":
    build_database()
