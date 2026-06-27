"""
Phase 2b — 例句增强脚本
========================
读取 fused.jsonl，对现有例句做：
1. strip所有重音标记
2. 去重（基于ru文本）
3. 每词5-10条
4. 输出更新后的 fused.jsonl

注意：不重新解析definition，不重新提取例句，只处理已有的examples字段。
"""

import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import FUSED_JSONL

STRESS_PATTERN = re.compile(r"[\u0301'`\u2019\u2018]")

def strip_stress(text):
    if not text:
        return text
    return STRESS_PATTERN.sub("", text)

def main():
    print("=" * 60)
    print("Phase 2b: 例句清洗")
    print("=" * 60)

    entries = []
    with open(FUSED_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    print(f"  Total entries: {len(entries)}")

    total_before = sum(len(e.get("examples", [])) for e in entries)
    total_after = 0
    words_with_examples = 0

    for entry in entries:
        examples = entry.get("examples", [])
        if not examples:
            continue

        # strip重音 + 去重
        seen = set()
        cleaned = []
        for ex in examples:
            ru = strip_stress(ex.get("ru", ""))
            zh = strip_stress(ex.get("zh", ""))
            source = ex.get("source", "unknown")

            if not ru:
                continue
            if ru in seen:
                continue
            seen.add(ru)

            cleaned.append({
                "ru": ru,
                "zh": zh,
                "source": source
            })

        # 限制5-10条
        if len(cleaned) > 10:
            cleaned = cleaned[:10]

        entry["examples"] = cleaned
        total_after += len(cleaned)
        if cleaned:
            words_with_examples += 1

    # 写回
    with open(FUSED_JSONL, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"\n  Before: {total_before} examples")
    print(f"  After:  {total_after} examples (strip stress + dedup)")
    print(f"  Words with examples: {words_with_examples}")
    print(f"\n  Output: {FUSED_JSONL}")
    print("=" * 60)

if __name__ == "__main__":
    main()
