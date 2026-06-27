"""
大规模俄语新闻抓取脚本 v3 — WSL版
==================================
用WSL的curl抓取RIA Novosti和Interfax新闻，
提取正文前3句，保存到 news_raw.json。
跳过TASS（被墙403）。
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

def extract_ria_article(url):
    html = curl(url)
    if not html:
        return None
    body = re.search(r'class="article__body[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
    if not body:
        return None
    text = re.sub(r'<[^>]+>', ' ', body.group(1))
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"').replace('&#39;', "'")
    text = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), text)
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'^Краткий пересказ от РИА ИИ\.?\s*', '', text)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return ' '.join(sentences[:3]) if sentences else text[:200]

def extract_interfax_article(url):
    html = curl(url)
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

def fetch_rss_ria():
    print("\n--- RIA Novosti ---")
    xml = curl('https://ria.ru/export/rss2/archive/index.xml')
    if not xml:
        return []
    items = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)
    print(f"  RSS items: {len(items)}")
    results = []
    for i, item in enumerate(items):
        link = re.search(r'<link>(.*?)</link>', item)
        if not link:
            continue
        url = link.group(1).strip()
        print(f"  [{i+1}/{len(items)}]", end=' ', flush=True)
        text = extract_ria_article(url)
        if text and len(text) > 30:
            sentences = re.split(r'(?<=[.!?])\s+', text)
            for s in sentences[:3]:
                s = s.strip()
                if len(s) > 20:
                    results.append([s, 'News:RIA'])
            print(f"OK ({len(text)}c)")
        else:
            print("SKIP")
        time.sleep(0.2)
    return results

def fetch_rss_interfax():
    print("\n--- Interfax ---")
    xml = curl('https://www.interfax.ru/rss.asp')
    if not xml:
        return []
    items = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)
    print(f"  RSS items: {len(items)}")
    results = []
    for i, item in enumerate(items):
        link = re.search(r'<link>(.*?)</link>', item)
        if not link:
            continue
        url = link.group(1).strip()
        print(f"  [{i+1}/{len(items)}]", end=' ', flush=True)
        text = extract_interfax_article(url)
        if text and len(text) > 30:
            sentences = re.split(r'(?<=[.!?])\s+', text)
            for s in sentences[:3]:
                s = s.strip()
                if len(s) > 20:
                    results.append([s, 'News:Interfax'])
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
    
    for fn in [fetch_rss_ria, fetch_rss_interfax]:
        try:
            results = fn()
            all_results.extend(results)
            print(f"  +{len(results)} new sentences")
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
    
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(deduped, f, ensure_ascii=False)
    
    print(f"\n=== Done ===")
    print(f"Total: {len(deduped)} sentences (from {len(all_results)} raw)")
    print(f"Saved: {OUTPUT}")

if __name__ == '__main__':
    main()
