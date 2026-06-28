"""
Phase 2d — AI 多源语义融合（前8500高频词）
============================================
从 fused.jsonl 提取前8500高频词（有BKRS+Kaikki+OpenRussian多源数据），
调用 DeepSeek API 生成结构化释义（含接格、体标注、例句）。
输出到 llm_cache.json，phase3_build_db.py 自动使用。

高并发：10 workers × 50 words/batch
"""

import json, os, sys, time, re, urllib.request, urllib.error, threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# 读取API key
API_KEY = None
env_path = os.path.expanduser("~/.hermes/.env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if line.startswith("DEEPSEEK_API_KEY="):
                API_KEY = line.split("=", 1)[1].strip().strip("'\"")
                break

if not API_KEY:
    print("ERROR: DEEPSEEK_API_KEY not set")
    sys.exit(1)

API_URL = "https://api.deepseek.com/v1/chat/completions"
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "llm_cache.json")
FUSED_JSONL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "fused.jsonl")
BATCH_SIZE = 50
MAX_WORKERS = 10
MAX_LEMMAS = 8500

SYSTEM_PROMPT = """你是一位精通中俄双语的资深辞书编纂专家。你的任务是将俄语单词的多个词典源（BKRS、Kaikki/Wiktionary、OpenRussian）的释义融合为一条结构化中文释义。

输入格式：
{
  "lemma": "俄语单词",
  "bkrs": "BKRS释义（俄汉双语，可能含短语）",
  "kaikki": "Kaikki英文释义",
  "openrussian": "OpenRussian释义（俄英双语）",
  "pos": "词性"
}

输出格式（只输出JSON，不要其他内容）：
{
  "lemma": "俄语单词",
  "definition": "融合后的中文释义（规范、简洁、完整）",
  "government": "接格关系（如要求名词第二格，没有则写null）",
  "aspect": "体（完成体/未完成体/双体，没有则写null）",
  "examples": ["例句1", "例句2"]  // 从各源提取1-2个最佳例句
}

规则：
1. 以BKRS释义为主，Kaikki/OpenRussian为补充
2. 如果BKRS有中文释义，优先使用并优化
3. 如果BKRS只有俄语释义，用Kaikki英文释义翻译为中文
4. 释义要规范、简洁，符合辞书格式
5. 接格关系从BKRS或OpenRussian中提取
6. 体标注从Kaikki或OpenRussian中提取
7. 例句从各源中提取最清晰、最完整的1-2条
8. 如果某字段无数据，写null不要空字符串"""

def get_top_words():
    """从fused.jsonl提取前N个高频词（有BKRS释义）"""
    words = []
    with open(FUSED_JSONL, 'r', encoding='utf-8') as f:
        for line in f:
            entry = json.loads(line)
            if entry.get("has_bkrs", False) and entry.get("definition"):
                lemma = entry.get("lemma", "")
                if lemma and len(lemma) >= 2:
                    words.append(entry)
    
    # 按or_frequency排序（如果有）
    words.sort(key=lambda w: w.get("or_frequency", 0) or 0, reverse=True)
    return words[:MAX_LEMMAS]

def build_prompt(words_batch):
    """构建一批词的prompt"""
    items = []
    for w in words_batch:
        item = {
            "lemma": w.get("lemma", ""),
            "bkrs": w.get("definition", ""),
            "kaikki": w.get("translations_en", "") or w.get("kaikki_glosses_en", ""),
            "openrussian": w.get("openrussian_definition", ""),
            "pos": w.get("pos", "")
        }
        items.append(item)
    return json.dumps(items, ensure_ascii=False)

def call_deepseek(prompt):
    """调用DeepSeek API"""
    data = json.dumps({
        'model': 'deepseek-chat',
        'messages': [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 0.3,
        'max_tokens': 8000
    }).encode('utf-8')
    
    req = urllib.request.Request(API_URL, data=data, method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Authorization', f'Bearer {API_KEY}')
    
    for attempt in range(3):
        try:
            resp = urllib.request.urlopen(req, timeout=120)
            result = json.loads(resp.read().decode('utf-8'))
            content = result['choices'][0]['message']['content']
            # 提取JSON
            start = content.find('[')
            end = content.rfind(']')
            if start != -1 and end != -1 and end > start:
                return json.loads(content[start:end+1])
            # 尝试解析单个对象
            start = content.find('{')
            end = content.rfind('}')
            if start != -1 and end != -1 and end > start:
                return [json.loads(content[start:end+1])]
            return []
        except Exception as e:
            if attempt < 2:
                time.sleep(2)
            else:
                return []

def translate_batch(batch):
    """翻译一批词"""
    prompt = build_prompt(batch)
    results = call_deepseek(prompt)
    
    translated = {}
    for item in results:
        lemma = item.get("lemma", "")
        if lemma and item.get("definition"):
            translated[lemma] = {
                "definition": item["definition"],
                "government": item.get("government"),
                "aspect": item.get("aspect"),
                "examples": item.get("examples", [])
            }
    return translated

def main():
    print("Loading top words...")
    words = get_top_words()
    print(f"Total words: {len(words)}")
    
    # 分批
    batches = [words[i:i+BATCH_SIZE] for i in range(0, len(words), BATCH_SIZE)]
    print(f"Batches: {len(batches)}")
    
    cache = {}
    save_lock = threading.Lock()
    
    # 加载已有缓存
    if os.path.exists(OUTPUT):
        with open(OUTPUT, 'r', encoding='utf-8') as f:
            cache = json.load(f)
        print(f"Loaded existing cache: {len(cache)} lemmas")
    
    def save_progress():
        with save_lock:
            with open(OUTPUT, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False)
    
    # 并行处理
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(translate_batch, batch): i for i, batch in enumerate(batches)}
        completed = 0
        for future in as_completed(futures):
            batch_idx = futures[future]
            try:
                results = future.result()
                for lemma, data in results.items():
                    cache[lemma] = data
                completed += 1
                if completed % 5 == 0 or completed == len(batches):
                    save_progress()
                    print(f"  [{completed}/{len(batches)}] Total: {len(cache)} lemmas fused")
            except Exception as e:
                print(f"  [WARN] Batch {batch_idx} failed: {e}")
    
    save_progress()
    print(f"\n=== Done ===")
    print(f"Lemmas fused: {len(cache)}")
    print(f"Saved: {OUTPUT}")

if __name__ == '__main__':
    main()
