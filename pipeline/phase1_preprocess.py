"""Parus v0.2 — Phase 1: 数据预处理
读取所有源数据，产出 intermediate.jsonl

Phase 1a: BKRS DSL → intermediate
Phase 1b: OpenRussian CSV → intermediate (变格+词频+英文翻译)
Phase 1c: Kaikki JSONL 流式 → intermediate (变格+词源+英文释义+例句)
Phase 1d: Tatoeba TSV → intermediate (例句)
Phase 1e: 聚合 → intermediate.jsonl
"""

import gzip
import json
import os
import re
import sys
import zipfile
import csv
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (
    BKRS_GZ, BKRS_DB, OPEN_RUSSIAN_ZIP, KAIKKI_JSONL,
    TATOEBA_TSV, OUTPUT_DIR, INTERMEDIATE_JSONL, NOISE_TAGS
)
from utils import clean_stress, clean_dsl_text, normalize_grammar_tag, is_noise_tag


# ============================================================
# Phase 1a: BKRS DSL → dict[lemma, BKRS数据]
# ============================================================

def parse_bkrs_dsl():
    """解析 BKRS DSL (.gz) 文件，返回 {lemma: {stressed, definitions, examples}}"""
    bkrs = {}
    with gzip.open(BKRS_GZ, "rt", encoding="utf-8-sig", errors="replace") as f:
        current_word = None
        current_def_lines = []
        for line in f:
            line = line.strip("\r\n")
            if not line or line.startswith("#"):
                continue
            if line.startswith(" ") or line.startswith("\t"):
                if current_word:
                    current_def_lines.append(line)
            else:
                if current_word:
                    _save_bkrs_entry(bkrs, current_word, current_def_lines)
                current_word = line.strip()
                current_def_lines = []
        if current_word:
            _save_bkrs_entry(bkrs, current_word, current_def_lines)

    print(f"[1a] BKRS DSL: {len(bkrs)} 词条")
    return bkrs


def _save_bkrs_entry(bkrs, word, def_lines):
    raw_def = "\n".join(def_lines)
    clean_def = clean_dsl_text(raw_def)
    if not clean_def:
        return
    lemma = clean_stress(word)
    # 提取内嵌例句
    examples = _extract_bkrs_examples(clean_def)
    entry = {
        "stressed": word,
        "definition": clean_def,
        "examples": examples,
    }
    if lemma in bkrs:
        bkrs[lemma]["examples"].extend(examples)
    else:
        bkrs[lemma] = entry


def _extract_bkrs_examples(text):
    """从 BKRS 释义文本提取内嵌例句 [(ru, zh), ...]"""
    pattern = re.compile(r"•\s*([^-\n]+?)\s*-\s*([^\n•]+)")
    matches = pattern.findall(text)
    return [(ru.strip(), zh.strip()) for ru, zh in matches]


# ============================================================
# Phase 1b: OpenRussian CSV → dict[lemma, OpenRussian数据]
# ============================================================

def parse_open_russian():
    """解析 OpenRussian ZIP 中的 CSV 文件"""
    or_data = {}  # {lemma: {pos, frequency, translations_en, inflections, gender, aspect}}
    if not os.path.exists(OPEN_RUSSIAN_ZIP):
        print("[1b] OpenRussian ZIP 不存在，跳过")
        return or_data

    with zipfile.ZipFile(OPEN_RUSSIAN_ZIP, "r") as zf:
        for name in zf.namelist():
            if not name.endswith(".csv"):
                continue
            pos_val = _or_pos_from_filename(name)
            content = zf.read(name).decode("utf-8").splitlines()
            reader = csv.DictReader(content, delimiter="\t")
            for row in reader:
                lemma = clean_stress(row.get("bare", ""))
                if not lemma:
                    continue
                entry = or_data.get(lemma, {
                    "pos": None, "frequency": None,
                    "translations_en": "", "gender": None,
                    "aspect": None, "inflections": [],
                })
                # POS: 优先保留非 'other' 的值
                if entry["pos"] is None or entry["pos"] == "other":
                    entry["pos"] = pos_val
                entry["translations_en"] = row.get("translations_en", "")
                entry["gender"] = row.get("gender") or entry["gender"]
                entry["aspect"] = row.get("aspect") or entry["aspect"]
                # 变格变位
                inflections = _extract_or_inflections(row, pos_val)
                entry["inflections"].extend(inflections)
                or_data[lemma] = entry

    print(f"[1b] OpenRussian: {len(or_data)} 词条")
    return or_data


def _or_pos_from_filename(name):
    basename = os.path.basename(name)
    if "nouns" in basename:
        return "noun"
    elif "verbs" in basename:
        return "verb"
    elif "adjectives" in basename:
        return "adj"
    return "other"


def _extract_or_inflections(row, pos):
    """从 OpenRussian CSV 行提取变格变位形式"""
    inflections = []
    if pos == "noun":
        case_sg = ["sg_nom", "sg_gen", "sg_dat", "sg_acc", "sg_inst", "sg_prep"]
        case_pl = ["pl_nom", "pl_gen", "pl_dat", "pl_acc", "pl_inst", "pl_prep"]
        tags_sg = ["nom_sg", "gen_sg", "dat_sg", "acc_sg", "ins_sg", "prep_sg"]
        tags_pl = ["nom_pl", "gen_pl", "dat_pl", "acc_pl", "ins_pl", "prep_pl"]
        for col, tag in zip(case_sg, tags_sg):
            val = row.get(col, "").strip()
            if val:
                inflections.append((val, tag))
        for col, tag in zip(case_pl, tags_pl):
            val = row.get(col, "").strip()
            if val:
                inflections.append((val, tag))
    elif pos == "verb":
        verb_cols = [
            ("imperative_sg", "imp_sg"), ("imperative_pl", "imp_pl"),
            ("past_m", "past_m"), ("past_f", "past_f"),
            ("past_n", "past_n"), ("past_pl", "past_pl"),
            ("presfut_sg1", "pres_1sg"), ("presfut_sg2", "pres_2sg"),
            ("presfut_sg3", "pres_3sg"), ("presfut_pl1", "pres_1pl"),
            ("presfut_pl2", "pres_2pl"), ("presfut_pl3", "pres_3pl"),
        ]
        for col, tag in verb_cols:
            val = row.get(col, "").strip()
            if val:
                inflections.append((val, tag))
    elif pos == "adj":
        adj_cols = [
            ("decl_m_nom", "nom_m"), ("decl_m_gen", "gen_m"),
            ("decl_m_dat", "dat_m"), ("decl_m_acc", "acc_m"),
            ("decl_m_inst", "ins_m"), ("decl_m_prep", "prep_m"),
            ("decl_f_nom", "nom_f"), ("decl_f_gen", "gen_f"),
            ("decl_f_dat", "dat_f"), ("decl_f_acc", "acc_f"),
            ("decl_f_inst", "ins_f"), ("decl_f_prep", "prep_f"),
            ("decl_n_nom", "nom_n"), ("decl_n_gen", "gen_n"),
            ("decl_n_dat", "dat_n"), ("decl_n_acc", "acc_n"),
            ("decl_n_inst", "ins_n"), ("decl_n_prep", "prep_n"),
            ("decl_pl_nom", "nom_pl"), ("decl_pl_gen", "gen_pl"),
            ("decl_pl_dat", "dat_pl"), ("decl_pl_acc", "acc_pl"),
            ("decl_pl_inst", "ins_pl"), ("decl_pl_prep", "prep_pl"),
            ("short_m", "short_m"), ("short_f", "short_f"),
            ("short_n", "short_n"), ("short_pl", "short_pl"),
            ("comparative", "comp"), ("superlative", "superl"),
        ]
        for col, tag in adj_cols:
            val = row.get(col, "").strip()
            if val:
                inflections.append((val, tag))
    return inflections


# ============================================================
# Phase 1c: Kaikki JSONL → dict[lemma, Kaikki数据]
# ============================================================

def parse_kaikki():
    """流式解析 Kaikki JSONL，返回 {lemma: {pos, forms, senses, etymology}}"""
    kaikki = {}
    if not os.path.exists(KAIKKI_JSONL):
        print("[1c] Kaikki JSONL 不存在，跳过")
        return kaikki

    with open(KAIKKI_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)
            word = entry.get("word", "").strip()
            if not word:
                continue
            lemma = clean_stress(word)
            pos = entry.get("pos")
            forms = entry.get("forms", [])
            senses = entry.get("senses", [])
            etymology = entry.get("etymology_text", "")

            # 提取变格变位
            inflections = []
            for form in forms:
                form_text = form.get("form", "")
                tags = form.get("tags", [])
                if not is_noise_tag(tags):
                    tag_norm = normalize_grammar_tag(tags)
                    inflections.append((form_text, tag_norm))

            # 提取释义 + 例句
            glosses_en = []
            examples = []
            for s in senses:
                glosses_en.extend(s.get("glosses", []))
                for ex in s.get("examples", []):
                    ex_text = ex.get("text", "")
                    ex_trans = ex.get("translation", "")
                    if ex_text:
                        examples.append((ex_text, ex_trans))

            kaikki[lemma] = {
                "pos": pos,
                "inflections": inflections,
                "glosses_en": glosses_en,
                "examples": examples,
                "etymology": etymology,
            }

    print(f"[1c] Kaikki: {len(kaikki)} 词条")
    return kaikki


# ============================================================
# Phase 1d: Tatoeba TSV → dict[lemma, Tatoeba例句]
# ============================================================

def parse_tatoeba():
    """解析 Tatoeba 中俄例句 TSV，按词关联"""
    tatoeba = defaultdict(list)
    if not os.path.exists(TATOEBA_TSV):
        print("[1d] Tatoeba TSV 不存在，跳过")
        return tatoeba

    with open(TATOEBA_TSV, "r", encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 4:
                continue
            ru_sentence = parts[1].strip()
            zh_sentence = parts[3].strip()
            if not ru_sentence or not zh_sentence:
                continue
            # 从俄语句子中提取可能的词条关联
            words_in_sentence = set(clean_stress(w).strip(".,!?;:\"()[]-") for w in ru_sentence.split())
            for w in words_in_sentence:
                if len(w) > 1:
                    tatoeba[w].append((ru_sentence, zh_sentence))

    print(f"[1d] Tatoeba: {len(tatoeba)} 词有关联例句")
    return tatoeba


# ============================================================
# Phase 1e: 聚合 → intermediate.jsonl
# ============================================================

def aggregate(bkrs, or_data, kaikki, tatoeba):
    """聚合所有源数据为统一格式，写入 intermediate.jsonl"""
    all_lemmas = set(bkrs.keys()) | set(or_data.keys()) | set(kaikki.keys())
    count = 0

    with open(INTERMEDIATE_JSONL, "w", encoding="utf-8") as out:
        for lemma in sorted(all_lemmas):
            entry = {"lemma": lemma}

            # BKRS
            if lemma in bkrs:
                entry["stressed"] = bkrs[lemma]["stressed"]
                entry["bkrs_definition"] = bkrs[lemma]["definition"]
                entry["bkrs_examples"] = bkrs[lemma]["examples"]
            else:
                entry["stressed"] = lemma
                entry["bkrs_definition"] = None
                entry["bkrs_examples"] = []

            # OpenRussian
            if lemma in or_data:
                o = or_data[lemma]
                entry["or_pos"] = o["pos"]
                entry["or_translations_en"] = o["translations_en"]
                entry["or_gender"] = o["gender"]
                entry["or_aspect"] = o["aspect"]
                entry["or_inflections"] = o["inflections"]
            else:
                entry["or_pos"] = None
                entry["or_translations_en"] = ""
                entry["or_gender"] = None
                entry["or_aspect"] = None
                entry["or_inflections"] = []

            # Kaikki
            if lemma in kaikki:
                k = kaikki[lemma]
                entry["kaikki_pos"] = k["pos"]
                entry["kaikki_glosses_en"] = k["glosses_en"]
                entry["kaikki_etymology"] = k["etymology"]
                entry["kaikki_inflections"] = k["inflections"]
                entry["kaikki_examples"] = k["examples"]
            else:
                entry["kaikki_pos"] = None
                entry["kaikki_glosses_en"] = []
                entry["kaikki_etymology"] = ""
                entry["kaikki_inflections"] = []
                entry["kaikki_examples"] = []

            # Tatoeba
            entry["tatoeba_examples"] = tatoeba.get(lemma, [])

            out.write(json.dumps(entry, ensure_ascii=False) + "\n")
            count += 1

    print(f"[1e] 聚合完成: {count} 词条 → {INTERMEDIATE_JSONL}")


# ============================================================
# 主入口
# ============================================================

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("Phase 1: 数据预处理")
    print("=" * 60)

    bkrs = parse_bkrs_dsl()
    or_data = parse_open_russian()
    kaikki = parse_kaikki()
    tatoeba = parse_tatoeba()

    aggregate(bkrs, or_data, kaikki, tatoeba)

    print("\nPhase 1 完成!")


if __name__ == "__main__":
    main()
