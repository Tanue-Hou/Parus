import json
import sqlite3
import urllib.request
import os
import unicodedata
import sys

# 目标数据库路径：直接输出到 Android 项目的 assets 目录中
DB_DIR = os.path.join("app", "src", "main", "assets", "database")
DB_NAME = os.path.join(DB_DIR, "dict.db")
JSONL_URL = "https://kaikki.org/dictionary/Russian/kaikki.org-dictionary-Russian.jsonl"
LOCAL_JSONL_NAME = "kaikki.org-dictionary-Russian.jsonl"

def clean_stress(text):
    """
    去除俄语单词中的重音符号 (Combining Acute Accent, \u0301) 并转为小写。
    这是为了保证用户在输入无重音单词时能以最高速度进行匹配。
    """
    if not text:
        return ""
    # 去除重音符号
    text = text.replace('\u0301', '')
    # 进一步进行 Unicode 规范化，去除所有 Mark Nonspacing 字符
    normalized = unicodedata.normalize('NFD', text)
    cleaned = "".join(c for c in normalized if unicodedata.category(c) != 'Mn')
    return cleaned.lower().strip()

def download_file(url, filename):
    """
    流式下载大文件并显示进度
    """
    print(f"正在从 {url} 下载词库数据...")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response, open(filename, 'wb') as out_file:
            meta = response.info()
            file_size = int(meta.get("Content-Length", 0))
            print(f"文件大小: {file_size / (1024 * 1024):.2f} MB")
            
            downloaded = 0
            block_size = 8192
            while True:
                buffer = response.read(block_size)
                if not buffer:
                    break
                downloaded += len(buffer)
                out_file.write(buffer)
                if file_size > 0:
                    percent = downloaded * 100 / file_size
                    status = f"\r下载进度: {percent:.2f}% [{downloaded / (1024*1024):.2f}MB / {file_size / (1024*1024):.2f}MB]"
                    sys.stdout.write(status)
                    sys.stdout.flush()
            print("\n下载完成！")
    except Exception as e:
        print(f"\n下载失败: {e}")
        print("建议：如果在运行中遇到网络超时，您可以尝试在浏览器中手动打开链接下载，并把文件重命名为 'kaikki.org-dictionary-Russian.jsonl' 放在本脚本同级目录下。")
        sys.exit(1)

def init_db(conn):
    """
    初始化 SQLite 数据库表和索引
    """
    cursor = conn.cursor()
    # 1. 词条表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS words (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lemma TEXT NOT NULL,
        lemma_stressed TEXT NOT NULL,
        pos TEXT
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_words_lemma ON words(lemma);")
    
    # 2. 释义表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS definitions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        word_id INTEGER NOT NULL,
        source TEXT NOT NULL,
        definition TEXT NOT NULL,
        FOREIGN KEY(word_id) REFERENCES words(id) ON DELETE CASCADE
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_definitions_word_id ON definitions(word_id);")

    # 3. 词形变化表 (变格变位)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inflections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        word_id INTEGER NOT NULL,
        form TEXT NOT NULL,
        grammar_tag TEXT,
        FOREIGN KEY(word_id) REFERENCES words(id) ON DELETE CASCADE
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inflections_form ON inflections(form);")
    conn.commit()

def parse_and_build():
    # 检查并下载文件
    downloads_path = os.path.expanduser(os.path.join("~", "Downloads", "kaikki.org-dictionary-Russian.jsonl"))
    source_file = LOCAL_JSONL_NAME
    
    if os.path.exists(LOCAL_JSONL_NAME):
        print(f"检测到本地目录已存在词库备份 '{LOCAL_JSONL_NAME}'。")
    elif os.path.exists(downloads_path):
        print(f"检测到系统下载目录已存在词库文件 '{downloads_path}'。")
        source_file = downloads_path
    else:
        download_file(JSONL_URL, LOCAL_JSONL_NAME)

    # 确保输出目录存在
    os.makedirs(DB_DIR, exist_ok=True)
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)

    print("正在连接 SQLite 数据库，建立结构...")
    conn = sqlite3.connect(DB_NAME)
    init_db(conn)
    cursor = conn.cursor()

    print("开始清洗并解析词条...")
    
    words_count = 0
    definitions_count = 0
    inflections_count = 0

    with open(source_file, "r", encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)
            word_stressed = entry.get("word", "").strip()
            if not word_stressed:
                continue
            
            word_clean = clean_stress(word_stressed)
            pos = entry.get("pos", "")
            senses = entry.get("senses", [])

            # 1. 过滤并提取中文翻译
            zh_definitions = []
            for sense in senses:
                # 遍历翻译字段
                translations = sense.get("translations", [])
                for trans in translations:
                    if trans.get("code") == "zh" or trans.get("lang") in ["Chinese", "Mandarin", "Mandarin Chinese"]:
                        translation_text = trans.get("word", "").strip()
                        if translation_text:
                            # 附带英文语境释义帮助理解词义
                            glosses = sense.get("glosses", [])
                            context = f"({glosses[0]}) " if glosses else ""
                            zh_definitions.append(f"{context}{translation_text}")

            # 如果该词条没有任何中文翻译，在第一版中跳过（缩小包体积，只保留俄汉词条）
            if not zh_definitions:
                continue

            # 2. 插入主词条表
            cursor.execute(
                "INSERT INTO words (lemma, lemma_stressed, pos) VALUES (?, ?, ?)",
                (word_clean, word_stressed, pos)
            )
            word_id = cursor.lastrowid
            words_count += 1

            # 3. 插入中文释义表
            for def_text in zh_definitions:
                cursor.execute(
                    "INSERT INTO definitions (word_id, source, definition) VALUES (?, ?, ?)",
                    (word_id, "Wiktionary", def_text)
                )
                definitions_count += 1

            # 4. 提取并插入词形变化 (变格变位)
            forms_list = entry.get("forms", [])
            inserted_forms = set()  # 去重
            for form_entry in forms_list:
                raw_form = form_entry.get("form", "").strip()
                if raw_form:
                    clean_form = clean_stress(raw_form)
                    # 避免插入重复的变格形式或与原形相同的词形
                    if clean_form and clean_form != word_clean and clean_form not in inserted_forms:
                        inserted_forms.add(clean_form)
                        tags = ",".join(form_entry.get("tags", []))
                        cursor.execute(
                            "INSERT INTO inflections (word_id, form, grammar_tag) VALUES (?, ?, ?)",
                            (word_id, clean_form, tags)
                        )
                        inflections_count += 1

            # 没 1000 个词条提交一次事务，防止内存占用过高并提高写入速度
            if words_count % 1000 == 0:
                conn.commit()
                print(f"已处理 {words_count} 个有效词条...", end="\r")

    conn.commit()
    conn.close()

    print("\n" + "="*40)
    print("数据库编译成功！")
    print(f"主词条数 (有中文释义): {words_count}")
    print(f"释义条数: {definitions_count}")
    print(f"变格变位关联数: {inflections_count}")
    print(f"目标文件输出至: {DB_NAME}")
    print("="*40)

if __name__ == "__main__":
    parse_and_build()
