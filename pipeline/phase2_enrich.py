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
    INTERMEDIATE_JSONL, BKRS_DB, OUTPUT_DIR, FUSED_JSONL, NOISE_TAGS,
    TATOEBA_TSV
)
from utils import clean_stress, normalize_grammar_tag, is_noise_tag, guess_pos_from_suffix, pymorphy_pos_to_en

try:
    import pymorphy3
    MORPH = pymorphy3.MorphAnalyzer(lang='ru')
except ImportError:
    MORPH = None


# ============================================================
# 2e: Tatoeba 例句倒排索引（基于 pymorphy3 词形还原）
# ============================================================

# 第二变位法例外词（以 -ать/-еть 结尾但属于第二变位法）
SECOND_CONJ_EXCEPTIONS = {
    'гнать', 'держать', 'смотреть', 'видеть', 'ненавидеть',
    'терпеть', 'вертеть', 'обидеть', 'зависеть', 'дышать',
}
# 异常变位词（既非第一也非第二变位法）
IRREGULAR_CONJ = {
    'бежать', 'хотеть', 'бежать', 'дать', 'есть', 'ездить',
    'бриться', 'чтить', 'идти', 'шьить',
}


def infer_conjugation_type(lemma, pos):
    """推断动词变位类型 (Issue 4)

    Returns:
        0 = 非动词或无法判断
        1 = 第一变位法 (大多数 -ать/-ять/-еть/-оть/-уть 等)
        2 = 第二变位法 (-ить, 及少数 -ать/-еть 例外)
        3 = 异常变位 (бежать, хотеть 等)
    """
    if pos != 'verb':
        return 0
    if not lemma:
        return 0

    # 异常变位
    bare = lemma.rstrip('ся').rstrip('сь')
    if bare in IRREGULAR_CONJ or lemma in IRREGULAR_CONJ:
        return 3

    # 例外第二变位法
    if bare in SECOND_CONJ_EXCEPTIONS or lemma in SECOND_CONJ_EXCEPTIONS:
        return 2

    # 第二变位法: -ить
    if bare.endswith('ить'):
        return 2

    # 第一变位法: -ать, -ять, -еть, -оть, -уть, -юить, -ти, -чь
    if any(bare.endswith(s) for s in ['ать', 'ять', 'еть', 'оть', 'уть', 'юить']):
        return 1
    if bare.endswith('ти') or bare.endswith('чь'):
        return 1

    # 默认: 无法判断
    return 0


def build_tatoeba_lemma_index():
    """读取 Tatoeba TSV，使用 pymorphy3 词形还原建立 lemma→[(ru,zh)] 倒排索引

    每个句子中的每个俄文词都会被 pymorphy3 还原为 lemma，
    然后将句子关联到该 lemma。这样 "говорю" 会关联到 "говорить"。

    Returns:
        dict: {lemma: [(ru_sentence, zh_sentence), ...]}
    """
    index = defaultdict(list)
    if not os.path.exists(TATOEBA_TSV):
        print(f"  [Tatoeba] TSV not found: {TATOEBA_TSV}")
        return index

    if MORPH is None:
        print("  [Tatoeba] pymorphy3 not available, using surface form matching")
        # Fallback: surface form matching (original phase1 behavior)
        with open(TATOEBA_TSV, "r", encoding="utf-8-sig", errors="replace") as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) < 4:
                    continue
                ru_sentence = parts[1].strip()
                zh_sentence = parts[3].strip()
                if not ru_sentence or not zh_sentence:
                    continue
                words_in_sentence = set(
                    clean_stress(w).strip(".,!?;:\"()[]-")
                    for w in ru_sentence.split()
                )
                for w in words_in_sentence:
                    if len(w) > 1:
                        index[w].append((ru_sentence, zh_sentence))
        return index

    # Use pymorphy3 for proper lemmatization
    import string
    strip_chars = ".,!?;:\"()[]-«»—–…'" + string.punctuation
    seen_sentences = set()

    with open(TATOEBA_TSV, "r", encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 4:
                continue
            ru_sentence = parts[1].strip()
            zh_sentence = parts[3].strip()
            if not ru_sentence or not zh_sentence:
                continue

            # Skip duplicate sentences
            sent_key = (ru_sentence, zh_sentence)
            if sent_key in seen_sentences:
                continue
            seen_sentences.add(sent_key)

            # Lemmatize each word in the Russian sentence
            lemmas_found = set()
            for w in ru_sentence.split():
                w_clean = clean_stress(w).strip(strip_chars)
                if len(w_clean) < 2:
                    continue
                try:
                    parsed = MORPH.parse(w_clean)
                    if parsed:
                        lemma = parsed[0].normal_form
                        if lemma and len(lemma) > 1:
                            lemmas_found.add(lemma)
                except:
                    continue

            for lemma in lemmas_found:
                index[lemma].append((ru_sentence, zh_sentence))

    print(f"  [Tatoeba] Indexed {len(index)} lemmas from {len(seen_sentences)} sentence pairs")
    return index


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
# 2b+: 拼音清洗
# ============================================================

def clean_pinyin(text):
    """从 BKRS 释义文本中清除拼音（拉丁字母段），保留中文和俄文

    特殊处理：如果文本是纯拉丁文（无中文/俄文/数字），说明是英文释义
    （如 "ICQ", "DJ", "Linux", "to frustrate"），直接保留不清洗。
    """
    if not text:
        return text

    # 预检：如果文本不含中文、俄文、数字，只有拉丁字母+标点，则保留原文
    has_chinese = bool(re.search(r'[\u4e00-\u9fff]', text))
    has_cyrillic = bool(re.search(r'[\u0400-\u04ff]', text))
    has_digit = bool(re.search(r'[0-9]', text))
    if not has_chinese and not has_cyrillic and not has_digit:
        return text.strip()

    # Step 1: 处理 [xxx] 方括号
    # [是] → 是 (保留中文), [shì] → 删除 (纯拼音), [-de] → 删除
    def replace_bracket(m):
        content = m.group(1)
        chinese = re.sub(r'[a-zA-Zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜńňǹ\s\-]+', '', content)
        return chinese if chinese else ''
    text = re.sub(r'\[([^\]]+)\]', replace_bracket, text)

    # Step 2: 删除独立拼音词（连续拉丁字母+声调符号）
    text = re.sub(r'[a-zA-Zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜńňǹ]+', '', text)

    # Step 3: 清理空白
    text = re.sub(r'\s+([,;。.!?，；！？])', r'\1', text)  # 标点前去空格
    text = re.sub(r' {2,}', ' ', text)  # 多空格合一
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)

    return text.strip()


# ============================================================
# 2c: 例句关联（pymorphy3 分词）
# ============================================================

def link_examples(entry, tatoeba_index, max_examples=3):
    """用 pymorphy3 将 Tatoeba 例句关联到 word_id

    使用预构建的 lemma→sentences 倒排索引（基于 pymorphy3 词形还原），
    每个词最多保留 max_examples 条最短例句。
    """
    lemma = entry["lemma"]
    examples = []

    # BKRS 内嵌例句
    for ru, zh in entry.get("bkrs_examples", []):
        if ru and zh:
            examples.append({"ru": ru, "zh": zh, "source": "BKRS-embedded"})

    # Kaikki 例句
    for ru, zh in entry.get("kaikki_examples", []):
        if ru:
            examples.append({"ru": ru, "zh": zh or "", "source": "Kaikki"})

    # Tatoeba 例句（从预构建的 lemma 索引获取）
    tatoeba_sents = tatoeba_index.get(lemma, [])
    for ru, zh in tatoeba_sents:
        examples.append({"ru": ru, "zh": zh, "source": "Tatoeba"})

    # 去重（同一 ru+zh 只保留一条）
    seen = set()
    deduped = []
    for ex in examples:
        key = (ex["ru"], ex["zh"])
        if key not in seen:
            seen.add(key)
            deduped.append(ex)

    # 按句子长度排序（短句优先），每词最多 max_examples 条
    deduped.sort(key=lambda x: len(x["ru"]))
    return deduped[:max_examples]


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

    # 构建 Tatoeba lemma 索引（一次构建，全局复用）
    print("  Building Tatoeba lemma index...")
    tatoeba_index = build_tatoeba_lemma_index()

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
        "pinyin_cleaned": 0,
        "conjugation_filled": 0,
        "tatoeba_examples": 0,
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

            # 2c: 例句关联（使用预构建的 Tatoeba lemma 索引）
            examples = link_examples(entry, tatoeba_index)
            if examples:
                stats["has_examples"] += 1
                tatoeba_count = sum(1 for e in examples if e["source"] == "Tatoeba")
                stats["tatoeba_examples"] += tatoeba_count

            # 2d: 变位类型推断
            conjugation_type = infer_conjugation_type(lemma, pos)
            if conjugation_type > 0:
                stats["conjugation_filled"] += 1

            # 2e: 拼音清洗
            raw_def = entry.get("bkrs_definition", "")
            cleaned_def = clean_pinyin(raw_def)
            if raw_def != cleaned_def:
                stats["pinyin_cleaned"] += 1

            # 输出 fused.jsonl
            output = {
                "lemma": lemma,
                "lemma_stressed": entry.get("stressed", lemma),
                "pos": pos,
                "conjugation_type": conjugation_type,
                "definition": cleaned_def,
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
    print(f"变位类型补全:      {stats['conjugation_filled']:>8,}")
    print(f"有变格词条:        {stats['has_inflections']:>8,}")
    print(f"变格总条数:        {stats['inflection_count']:>8,}")
    print(f"有例句词条:        {stats['has_examples']:>8,}")
    print(f"  └ Tatoeba例句:  {stats['tatoeba_examples']:>8,}")
    print(f"拼音清洗词条:      {stats['pinyin_cleaned']:>8,}")
    print(f"\n输出: {FUSED_JSONL}")


if __name__ == "__main__":
    main()
