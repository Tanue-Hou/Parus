"""
Interfax 多轮新闻抓取
====================
Interfax RSS每小时的新闻都不同，重复抓取多次累积数据。
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

def fetch_interfax():
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
    
    # 多轮抓取Interfax
    for round_num in range(5):
        print(f"\n=== Round {round_num+1} ===")
        try:
            results = fetch_interfax()
            all_results.extend(results)
            print(f"  +{len(results)} new sentences")
            
            # 去重保存
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
        time.sleep(2)
    
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
