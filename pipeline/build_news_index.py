"""
重建新闻lemma索引
==================
从 news_raw.json 读取新闻句子，用 pymorphy3 做词形还原，
建立 lemma → [(sentence, source), ...] 索引。
"""
import json, re, os, sys

NEWS_RAW = '/mnt/d/Android/Parus/pipeline/output/news_raw.json'
OUTPUT = '/mnt/d/Android/Parus/pipeline/output/news_index.json'

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

def main():
    with open(NEWS_RAW, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"Loaded {len(data)} sentences")
    
    lemma_index = {}
    for sentence, source in data:
        words = re.findall(r'[а-яёА-ЯЁ]+', sentence)
        lemmas = set()
        for w in words:
            l = lemmatize(w)
            if len(l) > 1:
                lemmas.add(l)
        
        for lemma in lemmas:
            if lemma not in lemma_index:
                lemma_index[lemma] = []
            lemma_index[lemma].append([sentence, source])
    
    # 去重
    for lemma in lemma_index:
        seen = set()
        deduped = []
        for s, src in lemma_index[lemma]:
            key = s[:60]
            if key not in seen:
                seen.add(key)
                deduped.append([s, src])
        lemma_index[lemma] = deduped
    
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(lemma_index, f, ensure_ascii=False)
    
    total = sum(len(v) for v in lemma_index.values())
    print(f"Lemmas: {len(lemma_index)}")
    print(f"Total sentences: {total}")
    print(f"Saved: {OUTPUT}")

if __name__ == '__main__':
    main()
