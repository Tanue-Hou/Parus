"""
从Tatoeba TSV提取所有俄汉句子对，用pymorphy3做词形还原
"""
import json, re, os, sys

TATOEBA_TSV = '/mnt/c/Users/Tanue Hou/Downloads/Sentence pairs in Russian-Mandarin Chinese - 2026-06-26.tsv'
OUTPUT = '/mnt/d/Android/Parus/pipeline/output/tatoeba_index.json'

try:
    import pymorphy3
    morph = pymorphy3.MorphAnalyzer()
except:
    morph = None

def lemmatize(word):
    if morph and word.isalpha():
        try:
            p = morph.parse(word)[0]
            if p.score > 0.3:
                return p.normal_form
        except:
            pass
    return word.lower()

def strip_stress(text):
    return text.replace('́', '').replace('`', '').replace('\u0301', '')

def main():
    print(f"Reading Tatoeba TSV: {TATOEBA_TSV}")
    
    # 先统计行数
    with open(TATOEBA_TSV, 'r', encoding='utf-8') as f:
        total_lines = sum(1 for _ in f)
    print(f"Total lines: {total_lines}")
    
    lemma_index = {}
    processed = 0
    skipped = 0
    
    with open(TATOEBA_TSV, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 4:
                ru = strip_stress(parts[1].strip())
                zh = strip_stress(parts[3].strip())
                # 过滤太短/太长的句子
                if len(ru) < 10 or len(ru) > 150:
                    skipped += 1
                    continue
                if not zh:
                    skipped += 1
                    continue
                
                # 提取俄语词做lemma索引
                ru_words = re.findall(r'[а-яёА-ЯЁ]+', ru)
                lemmas = set()
                for w in ru_words:
                    l = lemmatize(w)
                    if len(l) > 1:
                        lemmas.add(l)
                
                for lemma in lemmas:
                    if lemma not in lemma_index:
                        lemma_index[lemma] = []
                    lemma_index[lemma].append([ru, zh, 'Tatoeba'])
                
                processed += 1
                if processed % 10000 == 0:
                    print(f"  Processed: {processed}, lemmas: {len(lemma_index)}")
    
    # 去重
    for lemma in lemma_index:
        seen = set()
        deduped = []
        for ru, zh, src in lemma_index[lemma]:
            key = ru[:60]
            if key not in seen:
                seen.add(key)
                deduped.append([ru, zh, src])
        lemma_index[lemma] = deduped
    
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(lemma_index, f, ensure_ascii=False)
    
    print(f"\n=== Done ===")
    print(f"Processed: {processed}")
    print(f"Skipped: {skipped}")
    print(f"Lemmas: {len(lemma_index)}")
    total_sentences = sum(len(v) for v in lemma_index.values())
    print(f"Total sentences: {total_sentences}")
    print(f"Saved: {OUTPUT}")

if __name__ == '__main__':
    main()
