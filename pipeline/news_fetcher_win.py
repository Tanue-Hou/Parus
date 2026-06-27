"""
Parus 新闻抓取脚本 — 在 Windows Python 上运行（WSL网络不稳定）
抓取 TASS / RIA Novosti / Interfax 最近新闻，提取正文前3句，
用 pymorphy3 词形还原建 lemma 索引。

输出: pipeline/output/news_index.json
"""

import urllib.request, re, html, json, os, sys, time
from collections import defaultdict

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def fetch_url(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    resp = urllib.request.urlopen(req, timeout=timeout)
    return resp.read().decode("utf-8", errors="replace")

def extract_rss_items(content):
    items = re.findall(r"<item>(.*?)</item>", content, re.DOTALL)
    result = []
    for item in items:
        title = html.unescape(re.sub(r"<[^>]+>", "", re.search(r"<title>(.*?)</title>", item).group(1) if re.search(r"<title>(.*?)</title>", item) else ""))
        link = re.search(r"<link>(.*?)</link>", item)
        link = link.group(1).strip() if link else ""
        link = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", link)
        desc = re.search(r"<description>(.*?)</description>", item)
        desc = html.unescape(re.sub(r"<[^>]+>", "", desc.group(1))) if desc else ""
        pubdate = re.search(r"<pubDate>(.*?)</pubDate>", item)
        pubdate = pubdate.group(1) if pubdate else ""
        result.append({"title": title, "link": link, "desc": desc, "pubdate": pubdate})
    return result

def extract_ria_body(html_content):
    """从RIA文章页面提取正文"""
    body = re.search(r'class="article__body[^"]*"[^>]*>(.*?)</div>\s*</div>', html_content, re.DOTALL)
    if body:
        text = re.sub(r"<[^>]+>", " ", body.group(1))
        text = re.sub(r"\s+", " ", text)
        return html.unescape(text).strip()
    return ""

def extract_interfax_body(html_content):
    """从Interfax文章页面提取正文"""
    body = re.search(r'class="text[^"]*"[^>]*>(.*?)</div>', html_content, re.DOTALL)
    if body:
        text = re.sub(r"<[^>]+>", " ", body.group(1))
        text = re.sub(r"\s+", " ", text)
        return html.unescape(text).strip()
    return ""

def extract_sentences(text, max_sentences=3):
    """提取前N句"""
    sentences = re.findall(r"[^.!?]*[.!?]", text)
    result = []
    for s in sentences:
        s = s.strip()
        if len(s) > 15:  # 至少15个字符才算完整句
            result.append(s)
        if len(result) >= max_sentences:
            break
    return result

def fetch_article_body(source, link):
    """从文章页面提取正文"""
    try:
        content = fetch_url(link, timeout=10)
        if source == "RIA":
            return extract_ria_body(content)
        elif source == "Interfax":
            return extract_interfax_body(content)
        return ""
    except:
        return ""

def main():
    project_root = r"D:\Android\Parus"
    output_dir = os.path.join(project_root, "pipeline", "output")
    os.makedirs(output_dir, exist_ok=True)

    sources = {
        "TASS": "https://tass.ru/rss/v2.xml",
        "RIA": "https://ria.ru/export/rss2/archive/index.xml",
        "Interfax": "https://www.interfax.ru/rss.asp",
    }

    all_sentences = []  # [(sentence_ru, source_name), ...]

    for name, url in sources.items():
        print(f"\n[{name}] Fetching RSS: {url}")
        try:
            content = fetch_url(url)
            items = extract_rss_items(content)
            print(f"  Got {len(items)} items")

            for item in items[:20]:  # 每个源最多取20篇
                body = ""
                if name == "TASS":
                    # TASS RSS没有description，需要抓页面
                    body = fetch_article_body(name, item["link"])
                elif name == "RIA":
                    body = fetch_article_body(name, item["link"])
                elif name == "Interfax":
                    body = item["desc"]  # Interfax的description已经有正文

                if not body:
                    continue

                sentences = extract_sentences(body)
                for s in sentences:
                    all_sentences.append((s, name))

                if sentences:
                    print(f"  -> {item['title'][:50]}... ({len(sentences)} sentences)")

                time.sleep(0.5)  # 礼貌延迟

        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"\nTotal sentences collected: {len(all_sentences)}")

    # 保存原始句子（供后续pymorphy3处理）
    output_path = os.path.join(output_dir, "news_raw.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_sentences, f, ensure_ascii=False, indent=2)
    print(f"Saved raw sentences to {output_path}")

if __name__ == "__main__":
    main()
