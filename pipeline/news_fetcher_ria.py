"""
RIA Novosti 批量新闻抓取
========================
RIA有归档页面，每页显示多篇文章的摘要。
直接从归档页提取文章链接和摘要，不需要解析文章正文。
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

def extract_text(html):
    """从RIA页面提取正文，尝试多种class"""
    patterns = [
        r'class="article__body[^"]*"[^>]*>(.*?)</div>',
        r'class="article-body"[^>]*>(.*?)</div>',
        r'class="text-block"[^>]*>(.*?)</div>',
        r'class="article-text"[^>]*>(.*?)</div>',
        r'class="entry-content"[^>]*>(.*?)</div>',
        r'class="content"[^>]*>(.*?)</div>',
        r'<p[^>]*>(.*?)</p>',
    ]
    for pattern in patterns:
        m = re.search(pattern, html, re.DOTALL)
        if m:
            text = re.sub(r'<[^>]+>', ' ', m.group(1))
            text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
            text = text.replace('&quot;', '"').replace('&#39;', "'")
            text = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), text)
            text = text.strip()
            text = re.sub(r'\s+', ' ', text)
            text = re.sub(r'^Краткий пересказ от РИА ИИ\.?\s*', '', text)
            if len(text) > 30:
                sentences = re.split(r'(?<=[.!?])\s+', text)
                return ' '.join(sentences[:3]) if sentences else text[:200]
    return None

def fetch_ria_archive_page(page=1):
    """抓取RIA归档页"""
    url = f'https://ria.ru/last/{page}/'
    if page == 1:
        url = 'https://ria.ru/last/'
    print(f"\n--- RIA Archive page {page} ---")
    html = curl(url)
    if not html:
        return []
    
    # 找文章链接
    links = re.findall(r'href="(https://ria\.ru/\d+/\w+/\d+\.html)"', html)
    links = list(set(links))
    print(f"  Found {len(links)} article links")
    
    results = []
    for i, url in enumerate(links):
        print(f"  [{i+1}/{len(links)}]", end=' ', flush=True)
        article_html = curl(url)
        if not article_html:
            print("NO_HTML")
            continue
        
        text = extract_text(article_html)
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

def main():
    all_results = []
    if os.path.exists(OUTPUT):
        with open(OUTPUT, 'r', encoding='utf-8') as f:
            all_results = json.load(f)
        print(f"Loaded existing: {len(all_results)} sentences")
    
    # 抓取多页归档
    for page in range(1, 6):  # 5页
        try:
            results = fetch_ria_archive_page(page)
            all_results.extend(results)
            print(f"  +{len(results)} new sentences")
            
            # 每页保存
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
