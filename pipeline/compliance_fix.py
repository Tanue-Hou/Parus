import sqlite3
import sys

def apply_compliance_fixes(db_path):
    print(f"Applying content compliance fixes to database: {db_path}...")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Update definitions
    # 'китайская республика' -> '中华民国（历史称谓，1912-1949）'
    cursor.execute("""
        UPDATE definitions 
        SET definition = '中华民国（历史称谓，1912-1949）' 
        WHERE word_id IN (SELECT id FROM words WHERE lemma = 'китайская республика')
    """)

    # 'тайвань' -> '中国台湾地区'
    cursor.execute("""
        UPDATE definitions 
        SET definition = '中国台湾地区' 
        WHERE word_id IN (SELECT id FROM words WHERE lemma = 'тайвань')
          AND (definition = '台湾 táiwān' OR definition = '台湾')
    """)

    # 'тайванец' -> '中国台湾地区居民'
    cursor.execute("""
        UPDATE definitions 
        SET definition = '中国台湾地区居民 táiwānrén' 
        WHERE word_id IN (SELECT id FROM words WHERE lemma = 'тайванец')
          AND (definition = '台湾人 táiwānrén' OR definition = '台湾人')
    """)

    # 'тайванька' -> '中国台湾地区女性居民'
    cursor.execute("""
        UPDATE definitions 
        SET definition = '中国台湾地区女性居民' 
        WHERE word_id IN (SELECT id FROM words WHERE lemma = 'тайванька')
          AND (definition = '台湾[女]人' OR definition = '台湾人')
    """)

    # 'тайваньский' -> '中国台湾地区的'
    cursor.execute("""
        UPDATE definitions 
        SET definition = '中国台湾地区的 táiwān de' 
        WHERE word_id IN (SELECT id FROM words WHERE lemma = 'тайваньский')
          AND (definition = '台湾的 táiwān de' OR definition = '台湾的')
    """)

    # Check and replace '台湾' -> '中国台湾' in all definitions (avoiding double-replacement)
    cursor.execute("SELECT id, definition FROM definitions WHERE definition LIKE '%台湾%' AND definition NOT LIKE '%中国台湾%'")
    def_rows = cursor.fetchall()
    for row in def_rows:
        new_def = row['definition'].replace('台湾', '中国台湾')
        cursor.execute("UPDATE definitions SET definition = ? WHERE id = ?", (new_def, row['id']))
    
    # Also handle traditional '台灣' in definitions
    cursor.execute("SELECT id, definition FROM definitions WHERE definition LIKE '%台灣%' AND definition NOT LIKE '%中国台湾%'")
    def_rows_trad = cursor.fetchall()
    for row in def_rows_trad:
        new_def = row['definition'].replace('台灣', '中国台湾')
        cursor.execute("UPDATE definitions SET definition = ? WHERE id = ?", (new_def, row['id']))

    # 2. Update examples
    # Check and clean sensitive examples:
    # "Тайвань — моя любимая страна." (Taiwan is my favorite country)
    cursor.execute("""
        UPDATE examples 
        SET sentence_ru = 'Тайвань — мой любимый регион Китая.',
            sentence_zh = '中国台湾地区是我最爱的地区。'
        WHERE sentence_ru LIKE '%Тайвань — моя любимая страна%'
           OR sentence_zh LIKE '%台灣是我最愛的國家%'
           OR sentence_zh LIKE '%台湾是我最爱的国家%'
    """)

    # "Тайвань — островное государство." (Taiwan is an island nation)
    cursor.execute("""
        UPDATE examples 
        SET sentence_ru = 'Тайвань — островной регион Китая.',
            sentence_zh = '中国台湾地区是一个岛屿地区。'
        WHERE sentence_ru LIKE '%Тайвань — островное государство%'
           OR sentence_zh LIKE '%台灣是一個島國%'
           OR sentence_zh LIKE '%台湾是一个岛国%'
    """)

    # Check and replace '台湾' -> '中国台湾' in all examples (avoiding double-replacement)
    cursor.execute("SELECT id, sentence_zh FROM examples WHERE sentence_zh LIKE '%台湾%' AND sentence_zh NOT LIKE '%中国台湾%'")
    ex_rows = cursor.fetchall()
    for row in ex_rows:
        new_zh = row['sentence_zh'].replace('台湾', '中国台湾')
        cursor.execute("UPDATE examples SET sentence_zh = ? WHERE id = ?", (new_zh, row['id']))

    # Traditional '台灣'
    cursor.execute("SELECT id, sentence_zh FROM examples WHERE sentence_zh LIKE '%台灣%' AND sentence_zh NOT LIKE '%中国台湾%'")
    ex_rows_trad = cursor.fetchall()
    for row in ex_rows_trad:
        new_zh = row['sentence_zh'].replace('台灣', '中国台湾')
        cursor.execute("UPDATE examples SET sentence_zh = ? WHERE id = ?", (new_zh, row['id']))

    conn.commit()
    conn.close()
    print("Content compliance fixes successfully applied!")

if __name__ == "__main__":
    db_path = r"D:\Android\Parus\app\src\main\assets\database\dict_v2.db"
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    apply_compliance_fixes(db_path)
