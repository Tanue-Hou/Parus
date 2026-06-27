"""
Parus v0.2 — Phase 2: LLM 语义融合
======================================
读取 intermediate.jsonl → 对每个有 BKRS 定义的词条调用方舟 Agent Plan API
做多源释义融合 → 输出 fused.jsonl + llm_cache.json

用法:
    python phase2_fuse.py [--batch N] [--workers N] [--resume]

环境变量:
    VOLC_AGENT_KEY — 方舟 API Key (必需)
"""

import json
import os
import sys
import time
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests

# ── 项目配置 ──────────────────────────────────────────────────
PROJECT_ROOT = r"/mnt/d/Android/Parus"
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "pipeline", "output")
INTERMEDIATE_JSONL = os.path.join(OUTPUT_DIR, "intermediate.jsonl")
FUSED_JSONL = os.path.join(OUTPUT_DIR, "fused.jsonl")
LLM_CACHE_JSON = os.path.join(OUTPUT_DIR, "llm_cache.json")

# API 配置
API_URL = "https://ark.cn-beijing.volces.com/api/plan/v3/chat/completions"
API_MODEL = "ark-code-latest"

# 默认参数
DEFAULT_BATCH_SIZE = 50
DEFAULT_MAX_WORKERS = 5
DEFAULT_MAX_RETRIES = 3

# ── Prompt 模板 ───────────────────────────────────────────────

SYSTEM_PROMPT = """你是俄中词典编纂专家。下面是一个俄语词条的多源数据，请进行语义级融合，输出最完整的中文释义。

规则:
1. BKRS中文释义为主干，保留其编号结构和例句
2. 英文释义中BKRS未覆盖的语义点→翻译为中文加入new_senses
3. confidence: 3=四源一致, 2=三源, 1=两源, 0=单源
4. 输出必须是合法JSON，不要markdown代码块，不要多余文字"""

USER_PROMPT_TEMPLATE = """词条: {lemma} ({pos})
词源: {etymology}

数据源1 — BKRS俄汉词典:
{bkrs_definitions}

数据源2 — OpenRussian英文翻译:
{openrussian_en}

数据源3 — Kaikki/Wiktionary英文释义:
{kaikki_en}

数据源4 — Kaikki/Wiktionary俄语单语释义:
{kaikki_ru}

请输出JSON:
{{
  "fused_definition": "融合后的中文释义(多义词用1)2)3)编号)",
  "confidence": 0-3,
  "new_senses": ["BKRS未覆盖的新语义点(中文)"],
  "semantic_notes": "语义歧义/语境标注",
  "pos_corrected": "修正后的词性或null"
}}"""


# ── 辅助函数 ──────────────────────────────────────────────────

def get_api_key():
    """获取 API Key，优先环境变量"""
    key = os.environ.get("VOLC_AGENT_KEY")
    if not key:
        print("❌ 环境变量 VOLC_AGENT_KEY 未设置！", file=sys.stderr)
        print("   请设置: export VOLC_AGENT_KEY='your-api-key'", file=sys.stderr)
        sys.exit(1)
    return key


def build_user_prompt(entry):
    """根据词条数据构建用户 prompt"""
    lemma = entry.get("lemma", "")
    stressed = entry.get("stressed", "")

    # 词性: 优先 OR，其次 Kaikki，最后 guess
    pos = entry.get("or_pos") or entry.get("kaikki_pos") or "unknown"

    # 词源
    etymology = entry.get("kaikki_etymology") or ""

    # BKRS 定义
    bkrs_def = entry.get("bkrs_definition") or "（无）"

    # OpenRussian 英文翻译
    or_en = entry.get("or_translations_en") or "（无）"

    # Kaikki 英文释义
    kaikki_glosses = entry.get("kaikki_glosses_en") or []
    if kaikki_glosses:
        kaikki_en = "\n".join(f"- {g}" for g in kaikki_glosses)
    else:
        kaikki_en = "（无）"

    # Kaikki 俄语单语释义
    kaikki_ru_glosses = entry.get("kaikki_glosses_ru") or entry.get("kaikki_ru_glosses") or []
    if kaikki_ru_glosses:
        kaikki_ru = "\n".join(f"- {g}" for g in kaikki_ru_glosses)
    else:
        kaikki_ru = "（无）"

    return USER_PROMPT_TEMPLATE.format(
        lemma=stressed or lemma,
        pos=pos,
        etymology=etymology,
        bkrs_definitions=bkrs_def,
        openrussian_en=or_en,
        kaikki_en=kaikki_en,
        kaikki_ru=kaikki_ru,
    )


def call_llm(api_key, user_prompt, retries=DEFAULT_MAX_RETRIES):
    """调用方舟 Agent Plan API，带重试"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": API_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 2048,
    }

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(API_URL, headers=headers, json=payload, timeout=120)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                # 尝试解析 JSON
                return parse_llm_response(content)
            else:
                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                print(f"  ⚠ API 错误 (尝试 {attempt}/{retries}): {last_error}")
        except requests.exceptions.Timeout:
            last_error = "请求超时"
            print(f"  ⚠ 超时 (尝试 {attempt}/{retries})")
        except requests.exceptions.ConnectionError as e:
            last_error = f"连接错误: {e}"
            print(f"  ⚠ 连接错误 (尝试 {attempt}/{retries})")
        except Exception as e:
            last_error = str(e)
            print(f"  ⚠ 异常 (尝试 {attempt}/{retries}): {e}")

        if attempt < retries:
            time.sleep(2 * attempt)  # 退避

    return {"error": f"重试 {retries} 次均失败: {last_error}"}


def parse_llm_response(content):
    """从 LLM 回复中提取 JSON"""
    content = content.strip()

    # 去掉可能的 markdown 代码块标记
    if content.startswith("```"):
        lines = content.split("\n")
        # 去掉第一行 ```json 或 ``` 和最后一行 ```
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines).strip()

    # 尝试直接解析
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # 尝试提取 {...} 部分
    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(content[start : end + 1])
        except json.JSONDecodeError:
            pass

    return {"error": f"无法解析 LLM 输出为 JSON", "raw": content[:500]}


def build_fused_entry(entry, llm_result):
    """构建 fused.jsonl 的一行"""
    lemma = entry.get("lemma", "")
    fused_def = llm_result.get("fused_definition", "")
    confidence = llm_result.get("confidence", 0)

    # 构建 definitions_to_insert (符合 spec 2.4)
    definitions_to_insert = []
    if fused_def:
        definitions_to_insert.append({
            "source": "AI-Fused",
            "definition": fused_def,
            "confidence": confidence if confidence else 1,
            "is_primary": 1,
        })
    if entry.get("bkrs_definition"):
        definitions_to_insert.append({
            "source": "BKRS",
            "definition": entry["bkrs_definition"],
            "confidence": 1,
            "is_primary": 0,
        })

    return {
        "lemma": lemma,
        "lemma_stressed": entry.get("stressed", ""),
        "pos": entry.get("or_pos") or entry.get("kaikki_pos") or "unknown",
        "fused_definition": fused_def,
        "confidence": confidence,
        "new_senses": llm_result.get("new_senses", []),
        "semantic_notes": llm_result.get("semantic_notes", ""),
        "pos_corrected": llm_result.get("pos_corrected"),
        "definitions_to_insert": definitions_to_insert,
        # 保留原始数据引用
        "_sources": {
            "bkrs": bool(entry.get("bkrs_definition")),
            "openrussian": bool(entry.get("or_translations_en")),
            "kaikki": bool(entry.get("kaikki_glosses_en")),
        },
    }


# ── 缓存管理 ──────────────────────────────────────────────────

def load_cache():
    """加载 llm_cache.json，返回 {lemma: result}"""
    if not os.path.exists(LLM_CACHE_JSON):
        return {}
    try:
        with open(LLM_CACHE_JSON, "r", encoding="utf-8") as f:
            cache = json.load(f)
        print(f"📦 加载缓存: {len(cache)} 条")
        return cache
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠ 缓存文件损坏，重新开始: {e}")
        return {}


def save_cache(cache):
    """保存 llm_cache.json"""
    tmp_path = LLM_CACHE_JSON + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1)
    os.replace(tmp_path, LLM_CACHE_JSON)
    print(f"💾 缓存已保存: {len(cache)} 条 → {LLM_CACHE_JSON}")


def append_fused(entries):
    """追加 fused.jsonl（逐行追加，非覆盖）"""
    with open(FUSED_JSONL, "a", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def count_fused_lines():
    """统计 fused.jsonl 已有行数"""
    if not os.path.exists(FUSED_JSONL):
        return 0
    with open(FUSED_JSONL, "r", encoding="utf-8") as f:
        return sum(1 for _ in f)


# ── 主流程 ────────────────────────────────────────────────────

def process_entry(api_key, entry):
    """处理单个词条"""
    lemma = entry.get("lemma", "")
    user_prompt = build_user_prompt(entry)
    result = call_llm(api_key, user_prompt)
    return lemma, result


def main():
    parser = argparse.ArgumentParser(description="Parus v0.2 Phase 2 — LLM 语义融合")
    parser.add_argument("--batch", type=int, default=DEFAULT_BATCH_SIZE,
                        help=f"每批保存间隔 (默认: {DEFAULT_BATCH_SIZE})")
    parser.add_argument("--workers", type=int, default=DEFAULT_MAX_WORKERS,
                        help=f"并发数 (默认: {DEFAULT_MAX_WORKERS})")
    parser.add_argument("--resume", action="store_true",
                        help="从缓存断点续传")
    parser.add_argument("--max", type=int, default=0,
                        help="最多处理 N 条 (0=全部, 用于测试)")
    parser.add_argument("--skip", type=int, default=0,
                        help="跳过前 N 条有 BKRS 的词条")
    args = parser.parse_args()

    api_key = get_api_key()

    # ── 加载缓存 ──
    cache = load_cache() if args.resume else {}
    cached_lemmas = set(cache.keys())
    if cached_lemmas:
        print(f"📋 已缓存 lemma 数: {len(cached_lemmas)}")

    # ── 统计 fused.jsonl 已有行数 ──
    fused_count = count_fused_lines()
    print(f"📋 fused.jsonl 已有: {fused_count} 行")

    # ── 扫描 intermediate.jsonl ──
    print(f"📖 扫描 {INTERMEDIATE_JSONL} ...")
    total_lines = 0
    bkrs_lines = 0
    to_process = []

    with open(INTERMEDIATE_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            total_lines += 1
            entry = json.loads(line)
            if not entry.get("bkrs_definition"):
                continue
            bkrs_lines += 1
            lemma = entry.get("lemma", "")

            # 跳过已缓存的
            if lemma in cached_lemmas:
                continue

            to_process.append(entry)

    print(f"📊 总计: {total_lines} 行, 有 BKRS: {bkrs_lines}, 待处理: {len(to_process)}")

    # 测试模式
    if args.max > 0:
        to_process = to_process[: args.max]
        print(f"🔬 测试模式: 只处理前 {args.max} 条")

    # 跳过
    if args.skip > 0:
        to_process = to_process[args.skip :]
        print(f"⏭ 跳过前 {args.skip} 条, 剩余: {len(to_process)}")

    if not to_process:
        print("✅ 没有待处理的词条")
        return

    # ── 开始处理 ──
    print(f"🚀 开始处理 {len(to_process)} 个词条 (workers={args.workers}, batch={args.batch})")
    print(f"   API: {API_URL}")
    print(f"   Model: {API_MODEL}")
    print(f"   开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    processed = 0
    errors = 0
    batch_buffer = []
    fused_buffer = []
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # 提交所有任务
        future_to_entry = {
            executor.submit(process_entry, api_key, entry): entry
            for entry in to_process
        }

        for future in as_completed(future_to_entry):
            entry = future_to_entry[future]
            lemma = entry.get("lemma", "")

            try:
                lemma_key, result = future.result()
            except Exception as e:
                result = {"error": f"Worker 异常: {e}"}

            processed += 1

            if "error" in result:
                errors += 1
                print(f"  ❌ [{processed}/{len(to_process)}] {lemma}: {result.get('error', '未知错误')[:80]}")
            else:
                # 构建 fused 条目
                fused_entry = build_fused_entry(entry, result)
                fused_buffer.append(fused_entry)

                # 更新缓存
                cache[lemma] = result
                batch_buffer.append(lemma)

                # 进度
                if processed % 10 == 0 or processed == len(to_process):
                    elapsed = time.time() - start_time
                    rate = processed / elapsed if elapsed > 0 else 0
                    eta = (len(to_process) - processed) / rate if rate > 0 else 0
                    print(
                        f"  ✅ [{processed}/{len(to_process)}] {lemma[:30]:<30s} "
                        f"| conf={result.get('confidence', '?')} "
                        f"| {rate:.1f}条/秒 | ETA: {eta:.0f}s"
                    )

            # 每批保存
            if len(batch_buffer) >= args.batch:
                # 保存 fused.jsonl
                append_fused(fused_buffer)
                fused_buffer = []
                # 保存缓存
                save_cache(cache)
                batch_buffer = []
                print(f"  📊 进度: {processed}/{len(to_process)} | 错误: {errors}")

    # 最后一批
    if fused_buffer:
        append_fused(fused_buffer)
    if batch_buffer:
        save_cache(cache)

    # ── 完成 ──
    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"🏁 处理完成!")
    print(f"   处理: {processed} 条")
    print(f"   成功: {processed - errors} 条")
    print(f"   失败: {errors} 条")
    print(f"   耗时: {elapsed:.1f} 秒 ({elapsed/60:.1f} 分钟)")
    print(f"   速率: {processed/elapsed:.1f} 条/秒")
    print(f"   输出:")
    print(f"     - {FUSED_JSONL}")
    print(f"     - {LLM_CACHE_JSON}")
    print(f"   完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
