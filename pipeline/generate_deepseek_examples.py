"""
DeepSeek 俄汉双语例句生成脚本
==============================
从 fused.jsonl 前 N 个高频词中，为每词生成俄汉双语例句。
输出到 pipeline/output/deepseek_examples.json (lemma索引格式)

用法:
  python3 pipeline/generate_deepseek_examples.py [--limit 20000] [--batch 100] [--workers 10]
"""

import json, os, sys, re, time, argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import FUSED_JSONL, OUTPUT_DIR

import requests

# API 配置
API_URL = "https://ark.cn-beijing.volces.com/api/plan/v3/chat/completions"
API_MODEL = "ark-code-latest"

# 重音标记
STRESS_PATTERN = re.compile(r"[\u0301'`\u2019\u2018]")

def strip_stress(text):
    if not text:
        return text
    return STRESS_PATTERN.sub("", text)

def get_api_key():
    key = os.environ.get("VOLC_AGENT_KEY")
    if not key:
        print("❌ 环境变量 VOLC_AGENT_KEY 未设置！", file=sys.stderr)
        sys.exit(1)
    return key

SYSTEM_PROMPT = """你是一个俄汉双语例句生成器。你的任务是为给定的俄语单词生成自然、口语化的俄汉双语例句。

要求:
1. 每个词生成 8 条不同的例句
2. 例句必须包含目标词（用其原形或变体形式均可）
3. 俄语句子要自然、日常、口语化
4. 中文翻译要准确、自然
5. 每条例句 15-50 字（俄语部分）
6. 例句要覆盖不同的使用场景和语法形式
7. 不要加任何重音符号
8. 不要加编号或额外说明

输出格式: 纯JSON数组，每项包含 "ru" 和 "zh" 字段
示例: [{"ru": "Я каждый день читаю книги.", "zh": "我每天读书。"}, ...]"""

def call_llm(api_key, lemmas_batch):
    """调用 API 为一批词生成例句"""
    lemmas_str = ", ".join(lemmas_batch)
    user_prompt = f"""请为以下俄语单词各生成 8 条日常俄汉双语例句：

{lemmas_str}

每个词生成 8 条不同的例句，覆盖不同用法。
输出格式为JSON对象，key是单词本身，value是例句数组。
示例: {{"читать": [{{"ru": "Я каждый день читаю книги.", "zh": "我每天读书。"}}, ...]}}"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": API_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 8192,
    }

    for attempt in range(3):
        try:
            resp = requests.post(API_URL, headers=headers, json=payload, timeout=120)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return parse_response(content, lemmas_batch)
            elif resp.status_code == 429:
                print(f"  [Rate limited, waiting 10s...]")
                time.sleep(10)
                continue
            else:
                print(f"  [HTTP {resp.status_code}] {resp.text[:200]}")
                time.sleep(5)
        except Exception as e:
            print(f"  [Error] {e}")
            time.sleep(5)
    return {}

def parse_response(content, expected_lemmas):
    """解析 API 返回的 JSON"""
    # Try to extract JSON from the response
    # First, try to find a JSON object in the content
    json_match = re.search(r'\{.*\}', content, re.DOTALL)
    if not json_match:
        # Try to find array
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
    
    # Try to parse the whole content as JSON
    for attempt in range(2):
        try:
            if attempt == 0:
                result = json.loads(content)
            elif json_match:
                result = json.loads(json_match.group(0))
            else:
                return {}
            if isinstance(result, dict):
                # Validate and clean
                cleaned = {}
                for lemma, examples in result.items():
                    if lemma in expected_lemmas and isinstance(examples, list):
                        valid_examples = []
                        for ex in examples:
                            if isinstance(ex, dict) and "ru" in ex and "zh" in ex:
                                ru = strip_stress(ex["ru"].strip())
                                zh = strip_stress(ex["zh"].strip())
                                if ru and zh and 10 <= len(ru) <= 80:
                                    valid_examples.append({"ru": ru, "zh": zh})
                        if valid_examples:
                            cleaned[lemma] = valid_examples[:8]
                return cleaned
            elif isinstance(result, list):
                # Flat list format - try to group by lemma
                # This shouldn't happen with our prompt, but handle gracefully
                return {}
        except:
            if attempt == 0 and json_match:
                content = json_match.group(0)
                continue
            break
    return {}

def load_existing_index():
    """加载已有的 DeepSeek 例句索引"""
    path = os.path.join(OUTPUT_DIR, "deepseek_examples.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def get_target_lemmas(limit=20000):
    """从 fused.jsonl 获取前 N 个高频词（有 BKRS 释义的）"""
    lemmas = []
    with open(FUSED_JSONL, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= limit:
                break
            entry = json.loads(line.strip())
            if entry.get("has_bkrs"):
                lemmas.append(entry.get("lemma", ""))
    return lemmas

def main():
    parser = argparse.ArgumentParser(description="DeepSeek 俄汉例句生成")
    parser.add_argument("--limit", type=int, default=20000, help="处理前 N 个高频词")
    parser.add_argument("--batch", type=int, default=100, help="每批词数")
    parser.add_argument("--workers", type=int, default=10, help="并发数")
    parser.add_argument("--resume", action="store_true", default=True, help="断点续传")
    args = parser.parse_args()

    print("=" * 60)
    print("DeepSeek 俄汉双语例句生成")
    print("=" * 60)

    api_key = get_api_key()
    
    # 获取目标词
    all_lemmas = get_target_lemmas(args.limit)
    print(f"目标词: {len(all_lemmas)} 个")
    
    # 加载已有索引
    existing = load_existing_index() if args.resume else {}
    print(f"已有例句: {len(existing)} 个词")
    
    # 过滤已完成的词
    lemmas_to_process = [l for l in all_lemmas if l not in existing or len(existing[l]) < 8]
    print(f"需要生成: {len(lemmas_to_process)} 个词")
    
    if not lemmas_to_process:
        print("所有词已完成！")
        return
    
    # 分批处理
    batches = [lemmas_to_process[i:i+args.batch] for i in range(0, len(lemmas_to_process), args.batch)]
    print(f"共 {len(batches)} 批，每批 {args.batch} 词")
    
    total_generated = sum(len(v) for v in existing.values())
    total_new = 0
    batch_num = 0
    
    for batch in batches:
        batch_num += 1
        print(f"\n--- 第 {batch_num}/{len(batches)} 批 ({len(batch)} 词) ---")
        
        # 并发请求
        results = {}
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            # Split batch into smaller sub-batches for the API
            sub_batches = [batch[i:i+10] for i in range(0, len(batch), 10)]
            futures = {executor.submit(call_llm, api_key, sb): sb for sb in sub_batches}
            
            for future in as_completed(futures):
                sb = futures[future]
                try:
                    result = future.result()
                    results.update(result)
                    print(f"  +{len(result)} lemmas from sub-batch", end="", flush=True)
                except Exception as e:
                    print(f"  [FAIL] sub-batch: {e}")
        
        # 合并结果
        for lemma, examples in results.items():
            if lemma not in existing:
                existing[lemma] = []
            # Deduplicate
            seen_ru = set()
            for ex in examples:
                if ex["ru"][:80] not in seen_ru:
                    seen_ru.add(ex["ru"][:80])
                    existing[lemma].append(ex)
            # Limit to 8
            existing[lemma] = existing[lemma][:8]
        
        batch_new = sum(len(v) for v in results.values())
        total_new += batch_new
        total_generated = sum(len(v) for v in existing.values())
        
        print(f"\n  本批新增: {batch_new} 条, 累计: {total_generated} 条, 覆盖: {len(existing)} 词")
        
        # 每批保存
        output_path = os.path.join(OUTPUT_DIR, "deepseek_examples.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False)
        print(f"  已保存: {output_path}")
        
        # 间隔
        if batch_num < len(batches):
            time.sleep(2)
    
    print(f"\n{'=' * 60}")
    print(f"完成!")
    print(f"覆盖词数: {len(existing)}")
    print(f"总例句数: {total_generated}")
    print(f"输出: {os.path.join(OUTPUT_DIR, 'deepseek_examples.json')}")
    print(f"{'=' * 60}")

if __name__ == "__main__":
    main()
