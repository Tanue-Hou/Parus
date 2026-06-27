"""Parus v0.2 — Phase 2: 数据增强（纯规则，无LLM）
词性补全 + 变格清洗 + 例句关联 + 词频补全
"""

import json
import os
import sys
import sqlite3
import re
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (
    INTERMEDIATE_JSONL, BKRS_DB, OUTPUT_DIR, FUSED_JSONL, NOISE_TAGS
)
from utils import clean_stress, normalize_grammar_tag, is_noise_tag, guess_pos_from_suffix, pymorphy_pos_to_en

try:
    import pymorphy3
    MORPH = pymorphy3.MorphAnalyzer(lang='ru')
except ImportError:
    MORPH = None


# ============================================================
# 2a: 词性补全
# ============================================================

def complete_pos(entry):
    """按优先级补全词性：pymorphy3 > OpenRussian > Kaikki > 后缀启发式"""
    lemma = entry["lemma"]

    # 1. pymorphy3
    if MORPH:
        try:
            parsed = MORPH.parse(lemma)[0]
            if parsed.tag.POS:
                pos = pymorphy_pos_to_en(parsed.tag.POS)
                if pos:
                    return pos
        except:
            pass

    # 2. OpenRussian
    if entry.get("or_pos"):
        return entry["or_pos"]

    # 3. Kaikki
    if entry.get("kaikki_pos"):
        return entry["kaikki_pos"]

    # 4. 后缀启发式
    return guess_pos_from_suffix(lemma)


# ============================================================
# 2b: 变格清洗
# ============================================================

def clean_inflections(entry):
    """清洗并合并变格变位数据"""
    inflections = []

    # OpenRussian 变格（优先，质量高）
    for form, tag in entry.get("or_inflections", []):
        if form and len(form) > 1:
            inflections.append((form, tag, "OpenRussian"))

    # Kaikki 变格（补充 OpenRussian 未覆盖的）
    seen_forms = {f for f, _, _ in inflections}
    for form, tag in entry.get("kaikki_inflections", []):
        if form and len(form) > 1 and form not in seen_forms:
            if tag and not is_noise_tag([tag]):
                inflections.append((form, tag, "Kaikki"))
                seen_forms.add(form)

    return inflections


# ============================================================
# 2c: 例句关联（pymorphy3 分词）
# ============================================================

def link_examples(entry, lemma_id_map):
    """用 pymorphy3 将 Tatoeba 例句关联到 word_id"""
    lemma = entry["lemma"]
    examples = []

    # BKRS 内嵌例句
    for ru, zh in entry.get("bkrs_examples", []):
        examples.append({"ru": ru, "zh": zh, "source": "BKRS-embedded"})

    # Kaikki 例句
    for ru, zh in entry.get("kaikki_examples", []):
        examples.append({"ru": ru, "zh": zh or "", "source": "Kaikki"})

    # Tatoeba 例句（通过 pymorphy3 分词匹配）
    for ru, zh in entry.get("tatoeba_examples", []):
        if MORPH:
            words_in_sentence = ru.split()
            for w in words_in_sentence:
                try:
                    parsed = MORPH.parse(clean_stress(w))[0]
                    if parsed.normal_form == lemma:
                        examples.append({"ru": ru, "zh": zh, "source": "Tatoeba"})
                        break
                except:
                    continue

    # 去重（同一 ru+zh 只保留一条）
    seen = set()
    deduped = []
    for ex in examples:
        key = (ex["ru"], ex["zh"])
        if key not in seen:
            seen.add(key)
            deduped.append(ex)

    return deduped


# ============================================================
# 2d: 词频补全
# ============================================================

def get_frequency(entry):
    """从 OpenRussian 提取词频"""
    return entry.get("or_frequency")


# ============================================================
# 主流程
# ============================================================

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("Phase 2: 数据增强（纯规则）")
    print("=" * 60)

    # 统计
    stats = {
        "total": 0,
        "pos_filled": 0,
        "pos_pymorphy": 0,
        "pos_or": 0,
        "pos_kaikki": 0,
        "pos_guess": 0,
        "pos_missing": 0,
        "has_inflections": 0,
        "has_examples": 0,
        "inflection_count": 0,
    }

    with open(INTERMEDIATE_JSONL, "r", encoding="utf-8") as fin, \
         open(FUSED_JSONL, "w", encoding="utf-8") as fout:

        for line in fin:
            entry = json.loads(line)
            lemma = entry["lemma"]
            stats["total"] += 1

            # 2a: 词性补全
            pos = complete_pos(entry)
            if pos:
                stats["pos_filled"] += 1
                if pos == entry.get("or_pos"):
                    stats["pos_or"] += 1
                elif pos == entry.get("kaikki_pos"):
                    stats["pos_kaikki"] += 1
                elif MORPH and pos == pymorphy_pos_to_en(MORPH.parse(lemma)[0].tag.POS):
                    stats["pos_pymorphy"] += 1
                else:
                    stats["pos_guess"] += 1
            else:
                stats["pos_missing"] += 1

            # 2b: 变格清洗
            inflections = clean_inflections(entry)
            if inflections:
                stats["has_inflections"] += 1
                stats["inflection_count"] += len(inflections)

            # 2c: 例句关联（先不关联 word_id，留到 Phase 3）
            examples = link_examples(entry, {})
            if examples:
                stats["has_examples"] += 1

            # 输出 fused.jsonl
            output = {
                "lemma": lemma,
                "lemma_stressed": entry.get("stressed", lemma),
                "pos": pos,
                "definition": entry.get("bkrs_definition", ""),
                "inflections": inflections,
                "examples": examples,
                "etymology": entry.get("kaikki_etymology", ""),
                "translations_en": entry.get("or_translations_en", ""),
                "kaikki_glosses_en": entry.get("kaikki_glosses_en", []),
                "has_bkrs": bool(entry.get("bkrs_definition")),
            }
            fout.write(json.dumps(output, ensure_ascii=False) + "\n")

    # 打印统计
    print(f"\n{'='*60}")
    print(f"Phase 2 完成!")
    print(f"{'='*60}")
    print(f"总词条:            {stats['total']:>8,}")
    print(f"词性补全:          {stats['pos_filled']:>8,}  ({stats['pos_filled']/stats['total']*100:.1f}%)")
    print(f"  ├ pymorphy3:     {stats['pos_pymorphy']:>8,}")
    print(f"  ├ OpenRussian:   {stats['pos_or']:>8,}")
    print(f"  ├ Kaikki:        {stats['pos_kaikki']:>8,}")
    print(f"  └ 后缀启发:      {stats['pos_guess']:>8,}")
    print(f"词性缺失:          {stats['pos_missing']:>8,}  ({stats['pos_missing']/stats['total']*100:.1f}%)")
    print(f"有变格词条:        {stats['has_inflections']:>8,}")
    print(f"变格总条数:        {stats['inflection_count']:>8,}")
    print(f"有例句词条:        {stats['has_examples']:>8,}")
    print(f"\n输出: {FUSED_JSONL}")


if __name__ == "__main__":
    main()
