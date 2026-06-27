"""
大规模多源新闻抓取脚本 v5
==========================
从多个俄语新闻源批量抓取新闻。
基于调研结果，使用正确的正文class。

可抓取的源:
1. Lenta.ru - topic-body__content-text (200条RSS)
2. RIA Novosti - article__body (86条RSS)
3. Interfax - textBlock (25条RSS)
4. Kommersant - doc__text (14条RSS)
5. Vedomosti - box-paragraph__text (大量RSS)
6. RT Russia Today - article__text (大量RSS)
7. MK Московский Комсомолец - article__body (大量RSS)
8. Mail.ru Новости - p tags (大量RSS)
9. Rambler - p tags (大量RSS)
10. URA.RU - p tags
11. Life.ru - p tags
12. M24 Москва 24 - b-material-body
"""

import subprocess, re, json, os, time

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

def clean_text(text):
    text = re.sub(r'<[^>]+>', ' ', text)
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&quot;', '"').replace('&#39;', "'")
    text = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), text)
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'^Краткий пересказ от РИА ИИ\.?\s*', '', text)
    return text

def extract_text(html, patterns):
    """尝试多种pattern提取正文"""
    for pattern in patterns:
        m = re.search(pattern, html, re.DOTALL)
        if m:
            text = clean_text(m.group(1))
            if len(text) > 30:
                sentences = re.split(r'(?<=[.!?])\s+', text)
                return ' '.join(sentences[:3]) if sentences else text[:200]
    return None

def extract_ptags(html):
    """从p标签提取正文"""
    ps = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL)
    texts = []
    for p in ps:
        t = clean_text(p)
        if len(t) > 30:
            texts.append(t)
    if texts:
        # 取前3个p标签
        return ' '.join(texts[:3])
    return None

SOURCES = [
    {
        'name': 'Lenta',
        'rss': 'https://lenta.ru/rss',
        'patterns': [r'class="topic-body__content-text[^"]*"[^>]*>(.*?)</div>'],
        'max_items': 100,
    },
    {
        'name': 'RIA',
        'rss': 'https://ria.ru/export/rss2/archive/index.xml',
        'patterns': [
            r'class="article__body[^"]*"[^>]*>(.*?)</div>',
            r'class="js-mediator-article"[^>]*>(.*?)</div>',
        ],
        'max_items': 86,
    },
    {
        'name': 'Interfax',
        'rss': 'https://www.interfax.ru/rss.asp',
        'patterns': [
            r'class="textBlock"[^>]*>(.*?)</div>',
            r'itemprop="articleBody"[^>]*>(.*?)</div>',
        ],
        'max_items': 25,
    },
    {
        'name': 'Kommersant',
        'rss': 'https://www.kommersant.ru/RSS/main.xml',
        'patterns': [r'class="doc__text"[^>]*>(.*?)</div>'],
        'max_items': 14,
    },
    {
        'name': 'Vedomosti',
        'rss': 'https://www.vedomosti.ru/rss/news',
        'patterns': [r'class="box-paragraph__text"[^>]*>(.*?)</div>'],
        'max_items': 100,
    },
    {
        'name': 'RT',
        'rss': 'https://russian.rt.com/rss',
        'patterns': [r'class="article__text[^"]*"[^>]*>(.*?)</div>'],
        'max_items': 100,
    },
    {
        'name': 'MK',
        'rss': 'https://www.mk.ru/rss/news/index.xml',
        'patterns': [r'class="article__body"[^>]*>(.*?)</div>'],
        'max_items': 100,
    },
    {
        'name': 'MailRu',
        'rss': 'https://news.mail.ru/rss',
        'patterns': [],  # 用ptags
        'max_items': 100,
    },
    {
        'name': 'Rambler',
        'rss': 'https://news.rambler.ru/rss/head/',
        'patterns': [],  # 用ptags
        'max_items': 100,
    },
    {
        'name': 'URA',
        'rss': 'https://ura.ru/rss',
        'patterns': [],  # 用ptags
        'max_items': 100,
    },
    {
        'name': 'Life',
        'rss': 'https://life.ru/rss',
        'patterns': [],  # 用ptags
        'max_items': 100,
    },
    {
        'name': 'M24',
        'rss': 'https://www.m24.ru/rss.xml',
        'patterns': [r'class="b-material-body"[^>]*>(.*?)</div>'],
        'max_items': 100,
    },
]

def fetch_source(source):
    name = source['name']
    rss_url = source['rss']
    patterns = source['patterns']
    max_items = source['max_items']
    
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
    
    for i, item in enumerate(items[:max_items]):
        # 提取link
        link = re.search(r'<link[^>]*>(.*?)</link>', item)
        if not link:
            link = re.search(r'<link[^>]*href="([^"]+)"', item)
        if not link:
            continue
        url = link.group(1).strip()
        
        print(f"  [{i+1}/{min(len(items), max_items)}]", end=' ', flush=True)
        html = curl(url)
        if not html:
            print("NO_HTML")
            continue
        
        if patterns:
            text = extract_text(html, patterns)
        else:
            text = extract_ptags(html)
        
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
    
    for source in SOURCES:
        try:
            results = fetch_source(source)
            all_results.extend(results)
            print(f"  +{len(results)} new sentences")
            
            # 每源保存
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
    
    # 最终去重
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
    print(f"Total: {len(deduped)} sentences")

if __name__ == '__main__':
    main()
