"""
大规模俄语新闻抓取脚本 v2
=========================
从 TASS / RIA Novosti / Interfax 批量抓取新闻，
提取正文前3句，保存到 news_raw.json。
多轮抓取：RSS首页 + 翻页/归档
"""

import urllib.request, re, html, json, os, time, sys
from urllib.parse import quote

OUTPUT = '/mnt/d/Android/Parus/pipeline/output/news_raw.json'
# Windows Python兼容路径
if os.name == 'nt':
    OUTPUT = 'D:\\Android\\Parus\\pipeline\\output\\news_raw.json'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

def fetch(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f"  [ERR] {url[:60]}: {e}")
        return None

def extract_ria_article(url):
    html = fetch(url)
    if not html:
        return None
    body = re.search(r'class="article__body[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
    if not body:
        return None
    text = re.sub(r'<[^>]+>', ' ', body.group(1))
    # Windows Python: html.unescape not available, use regex
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"').replace('&#39;', "'")
    text = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), text)
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'^Краткий пересказ от РИА ИИ\.?\s*', '', text)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return ' '.join(sentences[:3]) if sentences else text[:200]

def extract_interfax_article(url):
    html = fetch(url)
    if not html:
        return None
    body = re.search(r'class="textBlock"[^>]*>(.*?)</div>', html, re.DOTALL)
    if not body:
        body = re.search(r'itemprop="articleBody"[^>]*>(.*?)</div>', html, re.DOTALL)
    if not body:
        return None
    text = re.sub(r'<[^>]+>', ' ', body.group(1))
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"').replace('&#39;', "'")
    text = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), text)
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return ' '.join(sentences[:3]) if sentences else text[:200]

def extract_tass_article(url):
    html = fetch(url)
    if not html:
        return None
    body = re.search(r'class="news-header__lead"[^>]*>(.*?)</div>', html, re.DOTALL)
    if not body:
        body = re.search(r'class="text-content"[^>]*>(.*?)</div>', html, re.DOTALL)
    if not body:
        return None
    text = re.sub(r'<[^>]+>', ' ', body.group(1))
    text = html.unescape(text).strip()
    text = re.sub(r'\s+', ' ', text)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return ' '.join(sentences[:3]) if sentences else text[:200]

def fetch_rss_ria():
    """抓取RIA Novosti RSS + 文章正文"""
    print("\n--- RIA Novosti ---")
    xml = fetch('https://ria.ru/export/rss2/archive/index.xml')
    if not xml:
        return []
    items = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)
    print(f"  RSS items: {len(items)}")
    results = []
    for i, item in enumerate(items):
        title = re.search(r'<title>(.*?)</title>', item)
        link = re.search(r'<link>(.*?)</link>', item)
        if not link:
            continue
        url = link.group(1).strip()
        print(f"  [{i+1}/{len(items)}] {url[:60]}...", end=' ')
        text = extract_ria_article(url)
        if text and len(text) > 30:
            sentences = re.split(r'(?<=[.!?])\s+', text)
            for s in sentences[:3]:
                s = s.strip()
                if len(s) > 20:
                    results.append([s, 'News:RIA'])
            print(f"OK ({len(text)} chars)")
        else:
            print("SKIP")
        time.sleep(0.3)
    return results

def fetch_rss_interfax():
    """抓取Interfax RSS + 文章正文"""
    print("\n--- Interfax ---")
    xml = fetch('https://www.interfax.ru/rss.asp')
    if not xml:
        return []
    items = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)
    print(f"  RSS items: {len(items)}")
    results = []
    for i, item in enumerate(items):
        title = re.search(r'<title>(.*?)</title>', item)
        link = re.search(r'<link>(.*?)</link>', item)
        desc = re.search(r'<description>(.*?)</description>', item)
        if not link:
            continue
        url = link.group(1).strip()
        print(f"  [{i+1}/{len(items)}] {url[:60]}...", end=' ')
        text = extract_interfax_article(url)
        if text and len(text) > 30:
            sentences = re.split(r'(?<=[.!?])\s+', text)
            for s in sentences[:3]:
                s = s.strip()
                if len(s) > 20:
                    results.append([s, 'News:Interfax'])
            print(f"OK ({len(text)} chars)")
        else:
            print("SKIP")
        time.sleep(0.3)
    return results

def fetch_rss_tass():
    """抓取TASS RSS + 文章正文"""
    print("\n--- TASS ---")
    xml = fetch('https://tass.ru/rss/v2.xml')
    if not xml:
        return []
    # 处理CDATA格式的链接
    xml = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', xml)
    items = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)
    print(f"  RSS items: {len(items)}")
    results = []
    for i, item in enumerate(items):
        title = re.search(r'<title>(.*?)</title>', item)
        link = re.search(r'<link>(.*?)</link>', item)
        if not link:
            continue
        url = link.group(1).strip()
        print(f"  [{i+1}/{len(items)}] {url[:60]}...", end=' ')
        text = extract_tass_article(url)
        if text and len(text) > 30:
            sentences = re.split(r'(?<=[.!?])\s+', text)
            for s in sentences[:3]:
                s = s.strip()
                if len(s) > 20:
                    results.append([s, 'News:TASS'])
            print(f"OK ({len(text)} chars)")
        else:
            print("SKIP")
        time.sleep(0.3)
    return results

def main():
    all_results = []
    
    # 加载已有
    if os.path.exists(OUTPUT):
        with open(OUTPUT, 'r', encoding='utf-8') as f:
            all_results = json.load(f)
        print(f"Loaded existing: {len(all_results)} sentences")
    
    # 抓取各源
    for fn in [fetch_rss_ria, fetch_rss_interfax, fetch_rss_tass]:
        try:
            results = fn()
            all_results.extend(results)
            print(f"  +{len(results)} sentences")
        except Exception as e:
            print(f"  FAILED: {e}")
    
    # 去重
    seen = set()
    deduped = []
    for s, src in all_results:
        key = s[:60]
        if key not in seen:
            seen.add(key)
            deduped.append([s, src])
    
    # 保存
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(deduped, f, ensure_ascii=False)
    
    print(f"\n=== Done ===")
    print(f"Total: {len(deduped)} sentences (from {len(all_results)} raw)")
    print(f"Saved: {OUTPUT}")

if __name__ == '__main__':
    main()
