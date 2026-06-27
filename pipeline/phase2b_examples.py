"""
Phase 2b — 例句增强脚本 (v3)
==============================
读取 fused.jsonl，从以下来源合并例句：
1. BKRS-embedded: 从 definition 字段提取 • 标记短语
2. News: 从 news_index.json 加载新闻例句
3. Tatoeba: 从 tatoeba_index.json 加载Tatoeba例句
4. Kaikki: 已有的 Kaikki 例句

每词 5-15 条，去重，按来源排序
输出更新后的 fused.jsonl
"""
import json, os, re, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import FUSED_JSONL, OUTPUT_DIR

STRESS_PATTERN = re.compile(r"[\u0301'`\u2019\u2018]")

def strip_stress(text):
    if not text:
        return text
    return STRESS_PATTERN.sub("", text)

def extract_bullet_phrases(definition_text):
    if not definition_text:
        return []
    phrases = []
    for line in definition_text.split('\n'):
        line = line.strip()
        if line.startswith('•'):
            line = line[1:].strip()
            # Split on — or -
            parts = re.split(r'\s*[—–-]\s*', line, maxsplit=1)
            if len(parts) == 2:
                ru = parts[0].strip()
                zh = parts[1].strip()
                if ru and zh and len(ru) > 1:
                    phrases.append((ru, zh))
            elif len(parts) == 1:
                ru = parts[0].strip()
                if ru and len(ru) > 1:
                    phrases.append((ru, ""))
        elif line.startswith('→'):
            line = line[1:].strip()
            parts = re.split(r'\s*[—–-]\s*', line, maxsplit=1)
            if len(parts) == 2:
                ru = parts[0].strip()
                zh = parts[1].strip()
                if ru and zh and len(ru) > 1:
                    phrases.append((ru, zh))
    return phrases

def load_index(path, name):
    if not os.path.exists(path):
        print(f"  [{name}] index not found, skipping")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        idx = json.load(f)
    total = sum(len(v) for v in idx.values())
    print(f"  [{name}] {len(idx)} lemmas, {total} sentences")
    return idx

def source_priority(source):
    order = {"BKRS-embedded": 0, "News": 1, "Tatoeba": 2, "Kaikki": 3}
    return order.get(source, 99)

def main():
    print("=" * 60)
    print("Phase 2b: 例句增强 (v3)")
    print("=" * 60)

    # Load indexes
    news_index = load_index(os.path.join(OUTPUT_DIR, "news_index.json"), "News")
    tatoeba_index = load_index(os.path.join(OUTPUT_DIR, "tatoeba_index.json"), "Tatoeba")

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
    source_counts = defaultdict(int)
    bullet_phrases_added = 0
    news_examples_added = 0
    tatoeba_examples_added = 0

    for entry in entries:
        lemma = entry.get("lemma", "")
        examples = entry.get("examples", [])
        definition = entry.get("definition", "")

        # Step 1: Extract bullet phrases from definition
        bullet_phrases = extract_bullet_phrases(definition)
        bullet_examples = []
        for ru, zh in bullet_phrases:
            bullet_examples.append({
                "ru": strip_stress(ru),
                "zh": strip_stress(zh),
                "source": "BKRS-embedded"
            })

        # Step 2: Get news examples
        news_examples_for_lemma = []
        if lemma in news_index:
            for item in news_index[lemma]:
                if isinstance(item, list) and len(item) >= 2:
                    ru_text = item[0]
                    news_examples_for_lemma.append({
                        "ru": strip_stress(ru_text),
                        "zh": "",
                        "source": "News"
                    })

        # Step 3: Get Tatoeba examples
        tatoeba_examples_for_lemma = []
        if lemma in tatoeba_index:
            for item in tatoeba_index[lemma]:
                if isinstance(item, list) and len(item) >= 3:
                    ru_text = item[0]
                    zh_text = item[1]
                    if ru_text and zh_text:
                        tatoeba_examples_for_lemma.append({
                            "ru": strip_stress(ru_text),
                            "zh": strip_stress(zh_text),
                            "source": "Tatoeba"
                        })

        # Step 4: Process existing examples (strip stress)
        existing_examples = []
        for ex in examples:
            existing_examples.append({
                "ru": strip_stress(ex.get("ru", "")),
                "zh": strip_stress(ex.get("zh", "")),
                "source": ex.get("source", "unknown")
            })

        # Step 5: Merge all sources, deduplicate
        seen = set()
        merged = []

        # 5a: BKRS-embedded from bullet phrases
        for ex in bullet_examples:
            ru = ex["ru"]
            if not ru:
                continue
            key = ru[:100]
            if key not in seen:
                seen.add(key)
                merged.append(ex)
                bullet_phrases_added += 1

        # 5b: Existing BKRS-embedded
        for ex in existing_examples:
            if ex["source"] != "BKRS-embedded":
                continue
            ru = ex["ru"]
            if not ru:
                continue
            key = ru[:100]
            if key not in seen:
                seen.add(key)
                merged.append(ex)

        # 5c: News examples
        for ex in news_examples_for_lemma:
            ru = ex["ru"]
            if not ru:
                continue
            key = ru[:100]
            if key not in seen:
                seen.add(key)
                merged.append(ex)
                news_examples_added += 1

        # 5d: Tatoeba examples
        for ex in tatoeba_examples_for_lemma:
            ru = ex["ru"]
            zh = ex["zh"]
            if not ru or not zh:
                continue
            key = ru[:100]
            if key not in seen:
                seen.add(key)
                merged.append(ex)
                tatoeba_examples_added += 1

        # 5e: Existing Tatoeba
        for ex in existing_examples:
            if ex["source"] != "Tatoeba":
                continue
            ru = ex["ru"]
            zh = ex["zh"]
            if not ru or not zh:
                continue
            key = ru[:100]
            if key not in seen:
                seen.add(key)
                merged.append(ex)

        # 5f: Existing Kaikki
        for ex in existing_examples:
            if ex["source"] != "Kaikki":
                continue
            ru = ex["ru"]
            if not ru:
                continue
            key = ru[:100]
            if key not in seen:
                seen.add(key)
                merged.append(ex)

        # Step 6: Sort by source priority, then by length
        merged.sort(key=lambda x: (source_priority(x["source"]), len(x["ru"])))

        # Step 7: Limit to 5-15 per word
        if len(merged) > 15:
            merged = merged[:15]

        entry["examples"] = merged
        total_after += len(merged)
        if merged:
            words_with_examples += 1
        for ex in merged:
            source_counts[ex["source"]] += 1

    # Write back
    with open(FUSED_JSONL, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"\n  Before: {total_before} examples")
    print(f"  After:  {total_after} examples")
    print(f"  Words with examples: {words_with_examples}")
    print(f"\n  Source breakdown:")
    for src in ["BKRS-embedded", "News", "Tatoeba", "Kaikki"]:
        count = source_counts.get(src, 0)
        print(f"    {src:>16}: {count:>6}")
    print(f"\n  Bullet phrases extracted: {bullet_phrases_added}")
    print(f"  News examples added: {news_examples_added}")
    print(f"  Tatoeba examples added: {tatoeba_examples_added}")
    print(f"\n  Output: {FUSED_JSONL}")
    print("=" * 60)

if __name__ == "__main__":
    main()
