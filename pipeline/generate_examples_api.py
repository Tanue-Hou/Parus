"""
用DeepSeek API批量生成俄汉双语例句
====================================
对A1-B2高频词（前20,000词）每词补到8条。
每批处理50词，并发请求。
"""

import json, os, sys, time, re
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request, urllib.error

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

OUTPUT = '/mnt/d/Android/Parus/pipeline/output/deepseek_examples.json'
FUSED_JSONL = '/mnt/d/Android/Parus/pipeline/output/fused.jsonl'

def count_examples(lemma):
    """从fused.jsonl统计当前例句数"""
    count = 0
    with open(FUSED_JSONL, 'r') as f:
        for line in f:
            entry = json.loads(line)
            if entry.get('lemma') == lemma:
                return len(entry.get('examples', []))
    return 0

def get_words_needing_examples(min_count=8):
    """找出需要补例句的词"""
    words = []
    with open(FUSED_JSONL, 'r') as f:
        for line in f:
            entry = json.loads(line)
            lemma = entry.get('lemma', '')
            examples = entry.get('examples', [])
            if lemma and len(examples) < min_count:
                words.append((lemma, len(examples)))
    return words

def call_deepseek(prompt):
    """调用DeepSeek API"""
    data = json.dumps({
        'model': MODEL,
        'messages': [
            {'role': 'system', 'content': '你是一个俄汉双语词典助手。生成俄语例句和中文翻译。只输出JSON数组，不要其他内容。'},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 0.7,
        'max_tokens': 4000
    }).encode('utf-8')
    
    req = urllib.request.Request(API_URL, data=data, method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Authorization', f'Bearer {API_KEY}')
    
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        result = json.loads(resp.read().decode('utf-8'))
        content = result['choices'][0]['message']['content']
        # 提取JSON
        json_match = re.search(r'\[.*?\]', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        return []
    except Exception as e:
        print(f"  API error: {e}")
        return []

def generate_batch(words_batch):
    """生成一批词的例句"""
    prompt_lines = []
    for lemma, current_count in words_batch:
        need = 8 - current_count
        if need > 0:
            prompt_lines.append(f"{lemma}: need {need} examples")
    
    prompt = f"""Generate Russian example sentences with Chinese translations for the following words.
Each word needs the specified number of examples.
Rules:
- Each example: Russian sentence (15-50 chars) | Chinese translation
- Natural, everyday language
- Cover different contexts/meanings
- Output as JSON array: [["word", "Russian sentence", "Chinese translation"], ...]

Words:
{chr(10).join(prompt_lines)}"""
    
    results = call_deepseek(prompt)
    if not results:
        return {}
    
    lemma_examples = {}
    for item in results:
        if len(item) >= 3:
            word = item[0].strip()
            ru = item[1].strip()
            zh = item[2].strip()
            if word and ru and zh and 10 < len(ru) < 150:
                if word not in lemma_examples:
                    lemma_examples[word] = []
                lemma_examples[word].append([ru, zh, 'AI-Generated'])
    
    return lemma_examples

def main():
    if not API_KEY:
        print("ERROR: DEEPSEEK_API_KEY not set")
        sys.exit(1)
    
    print("Finding words needing examples...")
    words = get_words_needing_examples(8)
    print(f"Total words needing examples: {len(words)}")
    
    # 只处理前2000词（先试水）
    words = words[:2000]
    
    # 分批，每批50词
    batch_size = 50
    batches = [words[i:i+batch_size] for i in range(0, len(words), batch_size)]
    print(f"Batches: {len(batches)}")
    
    all_examples = {}
    
    # 加载已有结果
    if os.path.exists(OUTPUT):
        with open(OUTPUT, 'r') as f:
            all_examples = json.load(f)
        print(f"Loaded existing: {len(all_examples)} lemmas")
    
    for i, batch in enumerate(batches):
        print(f"\nBatch {i+1}/{len(batches)} ({len(batch)} words)...")
        results = generate_batch(batch)
        for lemma, examples in results.items():
            if lemma not in all_examples:
                all_examples[lemma] = []
            all_examples[lemma].extend(examples)
        
        # 每批保存
        with open(OUTPUT, 'w') as f:
            json.dump(all_examples, f, ensure_ascii=False)
        
        total = sum(len(v) for v in all_examples.values())
        print(f"  Total: {len(all_examples)} lemmas, {total} examples")
        time.sleep(1)  # 限速
    
    print(f"\n=== Done ===")
    print(f"Lemmas: {len(all_examples)}")
    total = sum(len(v) for v in all_examples.values())
    print(f"Total examples: {total}")
    print(f"Saved: {OUTPUT}")

if __name__ == '__main__':
    main()
