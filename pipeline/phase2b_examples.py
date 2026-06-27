"""
Phase 2b — 例句增强脚本 (v2)
==============================
读取 fused.jsonl，从以下来源合并例句：
1. BKRS-embedded: 从 definition 字段提取 • 标记短语 + 已有的 bkrs_examples
2. News: 从 news_index.json 加载新闻例句（pymorphy3 词形还原匹配）
3. Tatoeba: 已有的 Tatoeba 例句
4. Kaikki: 已有的 Kaikki 例句

每词 5-10 条，去重，按来源排序（BKRS-embedded > News > Tatoeba > Kaikki）
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
    """
    从 definition 字段提取 • 标记的短语。
    格式示例:
        • занима́ться (+ instr) — 从事，做
        • занима́ться (+ sport) — 从事（运动）
    返回 [(ru_phrase, zh_phrase), ...]
    """
    if not definition_text:
        return []
    phrases = []
    for line in definition_text.split('\n'):
        line = line.strip()
        if line.startswith('•'):
            # Remove bullet
            content = line[1:].strip()
            # Split by — or – or -
            for sep in [' — ', ' – ', ' - ', ' —', ' –', '— ', '– ', ' -', '- ']:
                if sep in content:
                    parts = content.split(sep, 1)
                    ru_part = parts[0].strip()
                    zh_part = parts[1].strip() if len(parts) > 1 else ''
                    if ru_part and len(ru_part) > 1:
                        # Clean up: remove grammar notes in parentheses from ru
                        ru_clean = re.sub(r'\([^)]*\)', '', ru_part).strip()
                        if ru_clean and len(ru_clean) > 1:
                            phrases.append((ru_clean, zh_part))
                    break
            else:
                # No separator found, treat whole thing as ru
                if len(content) > 1:
                    phrases.append((content, ''))
    return phrases

def load_news_index():
    """Load news lemma index"""
    news_path = os.path.join(OUTPUT_DIR, "news_index.json")
    if not os.path.exists(news_path):
        print("  [News] news_index.json not found, skipping news examples")
        return {}
    with open(news_path, "r", encoding="utf-8") as f:
        return json.load(f)

def source_priority(source):
    """Sort key: BKRS-embedded > News > Tatoeba > Kaikki"""
    order = {
        "BKRS-embedded": 0,
        "News": 1,
        "Tatoeba": 2,
        "Kaikki": 3,
    }
    return order.get(source, 99)

def main():
    print("=" * 60)
    print("Phase 2b: 例句增强 (v2)")
    print("=" * 60)

    # Load news index
    print("  Loading news index...")
    news_index = load_news_index()
    print(f"  [News] {len(news_index)} lemmas in news index")

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

        # Step 2: Get news examples for this lemma
        news_examples_for_lemma = []
        if lemma in news_index:
            for ru_text, src in news_index[lemma]:
                news_examples_for_lemma.append({
                    "ru": strip_stress(ru_text),
                    "zh": "",  # News has no Chinese translation
                    "source": "News"
                })

        # Step 3: Process existing examples (strip stress)
        existing_examples = []
        for ex in examples:
            existing_examples.append({
                "ru": strip_stress(ex.get("ru", "")),
                "zh": strip_stress(ex.get("zh", "")),
                "source": ex.get("source", "unknown")
            })

        # Step 4: Merge all sources, deduplicate
        # Priority: BKRS-embedded (bullet phrases first, then existing BKRS-embedded)
        # Then News, then Tatoeba, then Kaikki
        seen = set()
        merged = []

        # 4a: BKRS-embedded from bullet phrases
        for ex in bullet_examples:
            ru = ex["ru"]
            if not ru:
                continue
            key = ru[:100]  # Use first 100 chars as dedup key
            if key not in seen:
                seen.add(key)
                merged.append(ex)
                bullet_phrases_added += 1

        # 4b: Existing BKRS-embedded
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

        # 4c: News examples
        for ex in news_examples_for_lemma:
            ru = ex["ru"]
            if not ru:
                continue
            key = ru[:100]
            if key not in seen:
                seen.add(key)
                merged.append(ex)
                news_examples_added += 1

        # 4d: Tatoeba
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

        # 4e: Kaikki
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

        # Step 5: Sort by source priority, then by length (short first)
        merged.sort(key=lambda x: (source_priority(x["source"]), len(x["ru"])))

        # Step 6: Limit to 5-15 per word
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
    print(f"\n  Output: {FUSED_JSONL}")
    print("=" * 60)

if __name__ == "__main__":
    main()
