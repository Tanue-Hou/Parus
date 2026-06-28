"""
Phase 2c — Kaikki-only 词条翻译脚本
=====================================
从 fused.jsonl 提取 Kaikki-only 词条（有英文释义无中文），
调用 DeepSeek API 批量翻译为中文辞书格式。
按词频由高到低分批处理，先跑前 2 万个高频词。
"""

import json, os, sys, time, re, urllib.request, urllib.error, threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# 从.env读取API key
def get_api_key():
    env_path = os.path.expanduser('~/.hermes/.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith('DEEPSEEK_API_KEY='):
                    return line.strip().split('=', 1)[1]
    return os.environ.get('DEEPSEEK_API_KEY', '')

API_KEY = get_api_key()
API_URL = 'https://api.deepseek.com/chat/completions'
MODEL = 'deepseek-chat'

OUTPUT = '/mnt/d/Android/Parus/pipeline/output/ai_translated.json'
FUSED_JSONL = '/mnt/d/Android/Parus/pipeline/output/fused.jsonl'
BATCH_SIZE = 100
MAX_WORKERS = 10
MAX_LEMMAS = 50000  # 先翻到5万条

def get_kaikki_only_words():
    """从fused.jsonl提取Kaikki-only词条（有英文释义无中文）"""
    words = []
    # 跳过垃圾词和组合形式
    JUNK_POS = {"punct", "symbol", "character", "suffix", "prefix", "combining_form"}
    VALID_SINGLE_CHARS = {"а", "и", "в", "к", "с", "у", "о", "б", "я"}
    # 只提取有意义的词类
    VALID_POS = {"noun", "verb", "adj", "adv", "name", "pron", "num", "prep", "conj", "intj", "part", "phrase", "proverb"}
    
    with open(FUSED_JSONL, 'r', encoding='utf-8') as f:
        for line in f:
            entry = json.loads(line)
            has_bkrs = entry.get('has_bkrs', False)
            if not has_bkrs:
                lemma = entry.get('lemma', '')
                pos = entry.get('pos', '')
                
                # 只提取有意义的词类
                if pos not in VALID_POS:
                    continue
                if len(lemma) <= 1 and lemma not in VALID_SINGLE_CHARS:
                    continue
                if lemma.startswith('"') or ('"' in lemma and lemma.count('"') >= 2):
                    continue
                if lemma and not any('\u0400' <= c <= '\u04ff' for c in lemma):
                    continue
                
                # Kaikki-only词条的definition为None，释义在translations_en或kaikki_glosses_en
                def_en = entry.get('translations_en') or entry.get('kaikki_glosses_en') or ''
                if isinstance(def_en, list):
                    def_en = '; '.join(def_en)
                if lemma and def_en:
                    words.append((lemma, def_en, pos))
    return words

def call_deepseek(prompt):
    """调用DeepSeek API"""
    data = json.dumps({
        'model': MODEL,
        'messages': [
            {'role': 'system', 'content': '你是一个俄汉词典编纂专家。将俄语单词的英文释义翻译为规范的中文辞书格式。只输出JSON数组，不要其他内容。'},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 0.3,
        'max_tokens': 4000
    }).encode('utf-8')
    
    req = urllib.request.Request(API_URL, data=data, method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Authorization', f'Bearer {API_KEY}')
    
    for attempt in range(3):
        try:
            resp = urllib.request.urlopen(req, timeout=60)
            result = json.loads(resp.read().decode('utf-8'))
            content = result['choices'][0]['message']['content']
            # 提取JSON（匹配最外层[]）
            start = content.find('[')
            end = content.rfind(']')
            if start != -1 and end != -1 and end > start:
                json_str = content[start:end+1]
                return json.loads(json_str)
            return []
        except Exception as e:
            if attempt < 2:
                time.sleep(2)
            else:
                return []

def translate_batch(batch):
    """翻译一批词条"""
    lines = []
    for lemma, def_en, pos in batch:
        lines.append(f"{lemma} ({pos}): {def_en}")
    
    prompt = f"""Translate the following Russian word definitions from English to Chinese dictionary format.
Each word has an English definition that needs to be translated to Chinese.
Output as JSON array: [["lemma", "chinese_definition", "pos"]]

Rules:
- Chinese definition should be concise and dictionary-style
- Keep technical terms accurate
- For verbs, include aspect marker 【未完成】/【完成】 if known
- For nouns, include gender if known
- Do NOT include English text in the Chinese definition

Words:
{chr(10).join(lines)}"""
    
    results = call_deepseek(prompt)
    if not results:
        return {}
    
    translated = {}
    for item in results:
        if len(item) >= 2:
            lemma = item[0].strip()
            zh_def = item[1].strip()
            pos = item[2] if len(item) >= 3 else ''
            if lemma and zh_def and not re.search(r'[a-zA-Z]', zh_def):
                translated[lemma] = {'definition': zh_def, 'pos': pos}
    
    return translated

def main():
    if not API_KEY:
        print("ERROR: DEEPSEEK_API_KEY not set")
        sys.exit(1)
    
    print("Loading Kaikki-only words...")
    words = get_kaikki_only_words()
    print(f"Total Kaikki-only words: {len(words)}")
    
    # 取前N个
    words = words[:MAX_LEMMAS]
    print(f"Processing first {len(words)} words")
    
    # 分批
    batches = [words[i:i+BATCH_SIZE] for i in range(0, len(words), BATCH_SIZE)]
    print(f"Batches: {len(batches)}")
    
    all_translated = {}
    save_lock = threading.Lock()
    
    # 加载已有结果
    if os.path.exists(OUTPUT):
        with open(OUTPUT, 'r', encoding='utf-8') as f:
            all_translated = json.load(f)
        print(f"Loaded existing: {len(all_translated)} lemmas")
    
    def save_progress():
        with save_lock:
            with open(OUTPUT, 'w', encoding='utf-8') as f:
                json.dump(all_translated, f, ensure_ascii=False)
    
    # 并行处理
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(translate_batch, batch): i for i, batch in enumerate(batches)}
        completed = 0
        for future in as_completed(futures):
            batch_idx = futures[future]
            try:
                results = future.result()
                for lemma, data in results.items():
                    all_translated[lemma] = data
                completed += 1
                if completed % 10 == 0 or completed == len(batches):
                    save_progress()
                    print(f"  [{completed}/{len(batches)}] Total: {len(all_translated)} lemmas translated")
            except Exception as e:
                print(f"  [WARN] Batch {batch_idx} failed: {e}")
    
    # 最终保存
    save_progress()
    
    print(f"\n=== Done ===")
    print(f"Lemmas translated: {len(all_translated)}")
    print(f"Saved: {OUTPUT}")

if __name__ == '__main__':
    main()
