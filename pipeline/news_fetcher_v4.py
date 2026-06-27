"""
大规模多轮新闻抓取脚本 v4
==========================
从多个俄语新闻源批量抓取新闻，
每轮抓取RSS首页，提取正文前3句。
多轮运行可以累积更多数据。

新闻源:
- RIA Novosti (article__body div)
- Interfax (textBlock div)
- Lenta.ru
- Izvestia
- Gazeta.ru
- RBK
- Kommersant
"""

import subprocess, re, json, os, time, sys

OUTPUT = '/mnt/d/Android/Parus/pipeline/output/news_raw.json'

def curl(url, timeout=15):
    try:
        r = subprocess.run(
            ['curl', '-sL', '--max-time', str(timeout),
             '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
             url],
            capture_output=True, text=True, timeout=timeout+5
        )
        if r.returncode == 0 and r.stdout:
            return r.stdout
        return None
    except:
        return None

EXTRACTORS = {
    'RIA': [
        (r'class="article__body[^"]*"[^>]*>(.*?)</div>', None),
        (r'class="article-body"[^>]*>(.*?)</div>', None),
        (r'class="text-block"[^>]*>(.*?)</div>', None),
    ],
    'Interfax': [
        (r'class="textBlock"[^>]*>(.*?)</div>', None),
        (r'itemprop="articleBody"[^>]*>(.*?)</div>', None),
    ],
    'Lenta': [
        (r'class="topic-body"[^>]*>(.*?)</div>', None),
        (r'class="article-body"[^>]*>(.*?)</div>', None),
    ],
    'Izvestia': [
        (r'class="article-content"[^>]*>(.*?)</div>', None),
        (r'class="text"[^>]*>(.*?)</div>', None),
    ],
    'Gazeta': [
        (r'class="article__text"[^>]*>(.*?)</div>', None),
        (r'class="b-article__text"[^>]*>(.*?)</div>', None),
    ],
    'RBK': [
        (r'class="article__text"[^>]*>(.*?)</div>', None),
        (r'class="text"[^>]*>(.*?)</div>', None),
    ],
    'Kommersant': [
        (r'class="article__text"[^>]*>(.*?)</div>', None),
        (r'class="text"[^>]*>(.*?)</div>', None),
    ],
}

def extract_text(html, patterns):
    for pattern, _ in patterns:
        m = re.search(pattern, html, re.DOTALL)
        if m:
            text = re.sub(r'<[^>]+>', ' ', m.group(1))
            text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
            text = text.replace('&quot;', '"').replace('&#39;', "'")
            text = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), text)
            text = text.strip()
            text = re.sub(r'\s+', ' ', text)
            text = re.sub(r'^Краткий пересказ от РИА ИИ\.?\s*', '', text)
            sentences = re.split(r'(?<=[.!?])\s+', text)
            return ' '.join(sentences[:3]) if sentences else text[:200]
    return None

def fetch_source(name, rss_url, extractor_name):
    print(f"\n--- {name} ---")
    xml = curl(rss_url)
    if not xml:
        print(f"  RSS failed")
        return []
    
    # 处理CDATA
    xml = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', xml)
    items = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)
    if not items:
        items = re.findall(r'<entry>(.*?)</entry>', xml, re.DOTALL)
    
    print(f"  RSS items: {len(items)}")
    results = []
    patterns = EXTRACTORS.get(extractor_name, EXTRACTORS['RIA'])
    
    for i, item in enumerate(items):
        link = re.search(r'<link[^>]*>(.*?)</link>', item)
        if not link:
            link = re.search(r'<link[^>]*href="([^"]+)"', item)
        if not link:
            continue
        url = link.group(1).strip()
        
        print(f"  [{i+1}/{len(items)}]", end=' ', flush=True)
        html = curl(url)
        if not html:
            print("NO_HTML")
            continue
        
        text = extract_text(html, patterns)
        if text and len(text) > 30:
            sentences = re.split(r'(?<=[.!?])\s+', text)
            for s in sentences[:3]:
                s = s.strip()
                if len(s) > 20:
                    results.append([s, f'News:{name}'])
            print(f"OK ({len(text)}c)")
        else:
            print("SKIP")
        time.sleep(0.2)
    
    return results

def main():
    all_results = []
    if os.path.exists(OUTPUT):
        with open(OUTPUT, 'r', encoding='utf-8') as f:
            all_results = json.load(f)
        print(f"Loaded existing: {len(all_results)} sentences")
    
    sources = [
        ('RIA Novosti', 'https://ria.ru/export/rss2/archive/index.xml', 'RIA'),
        ('Interfax', 'https://www.interfax.ru/rss.asp', 'Interfax'),
        ('Lenta.ru', 'https://lenta.ru/rss', 'Lenta'),
        ('Izvestia', 'https://iz.ru/rss.xml', 'Izvestia'),
        ('Gazeta.ru', 'https://www.gazeta.ru/export/rss.xml', 'Gazeta'),
        ('RBK', 'https://www.rbc.ru/rss/rbc_news.rss', 'RBK'),
        ('Kommersant', 'https://www.kommersant.ru/RSS/main.xml', 'Kommersant'),
    ]
    
    for name, rss_url, ext_name in sources:
        try:
            results = fetch_source(name, rss_url, ext_name)
            all_results.extend(results)
            print(f"  +{len(results)} new sentences")
            # 每抓完一个源立即保存
            seen = set()
            deduped = []
            for s, src in all_results:
                key = s[:60]
                if key not in seen:
                    seen.add(key)
                    deduped.append([s, src])
            with open(OUTPUT, 'w', encoding='utf-8') as f:
                json.dump(deduped, f, ensure_ascii=False)
            print(f"  Saved: {len(deduped)} sentences")
        except Exception as e:
            print(f"  FAILED: {e}")
    
    # 最终去重保存
    seen = set()
    deduped = []
    for s, src in all_results:
        key = s[:60]
        if key not in seen:
            seen.add(key)
            deduped.append([s, src])
    
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(deduped, f, ensure_ascii=False)
    
    print(f"\n=== Done ===")
    print(f"Total: {len(deduped)} sentences (from {len(all_results)} raw)")

if __name__ == '__main__':
    main()
