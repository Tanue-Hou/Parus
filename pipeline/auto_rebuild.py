#!/usr/bin/env python3
"""
Parus 自动重建监控脚本
等待 phase2c_translate.py 和 phase2d_fuse_ai.py 完成后，
自动跑 phase3_build_db.py 重建 dict_v2.db。
"""

import json, os, time, subprocess

PIPELINE_DIR = "/mnt/d/Android/Parus/pipeline"
OUTPUT_DIR = os.path.join(PIPELINE_DIR, "output")
AI_TRANSLATED = os.path.join(OUTPUT_DIR, "ai_translated.json")
LLM_CACHE = os.path.join(OUTPUT_DIR, "llm_cache.json")
PHASE3 = os.path.join(PIPELINE_DIR, "phase3_build_db.py")
DB_PATH = "/mnt/d/Android/Parus/app/src/main/assets/database/dict_v2.db"

def check_progress(path, label):
    if os.path.exists(path):
        with open(path) as f:
            d = json.load(f)
        print(f"[{label}] {len(d)} lemmas")
        return len(d)
    print(f"[{label}] not found")
    return 0

def wait_for_stable(path, label, min_count, max_checks=60, interval=30):
    """等待文件达到目标大小并稳定"""
    prev = 0
    stable_count = 0
    for i in range(max_checks):
        if os.path.exists(path):
            with open(path) as f:
                d = json.load(f)
            curr = len(d)
            print(f"[{label}] {curr}/{min_count} lemmas (check {i+1}/{max_checks})")
            if curr >= min_count:
                if curr == prev:
                    stable_count += 1
                    if stable_count >= 3:
                        print(f"[{label}] Stable at {curr} lemmas")
                        return curr
                else:
                    stable_count = 0
                prev = curr
        time.sleep(interval)
    print(f"[{label}] Timeout after {max_checks} checks")
    return check_progress(path, label)

def main():
    print("=== Parus Auto-Rebuild Monitor ===")
    print(f"Waiting for phase2c (target: 50000) and phase2d (target: 8500)...")
    
    # 等待翻译完成
    ai_count = wait_for_stable(AI_TRANSLATED, "AI-Translated", 50000, max_checks=120, interval=30)
    
    # 等待融合完成
    llm_count = wait_for_stable(LLM_CACHE, "AI-Fused", 8500, max_checks=120, interval=30)
    
    print(f"\n=== Both complete ===")
    print(f"AI-Translated: {ai_count} lemmas")
    print(f"AI-Fused: {llm_count} lemmas")
    
    # 运行phase3重建DB
    print(f"\n=== Rebuilding DB ===")
    result = subprocess.run(
        ["python3", PHASE3],
        capture_output=True, text=True, timeout=300
    )
    print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
    if result.returncode != 0:
        print(f"ERROR: phase3 failed: {result.stderr}")
        return
    
    # 验证
    import sqlite3
    db = sqlite3.connect(DB_PATH)
    print("\n=== Verification ===")
    print(f"words: {db.execute('SELECT COUNT(*) FROM words').fetchone()[0]}")
    print(f"definitions: {db.execute('SELECT COUNT(*) FROM definitions').fetchone()[0]}")
    print(f"examples: {db.execute('SELECT COUNT(*) FROM examples').fetchone()[0]}")
    
    src = db.execute("SELECT source, COUNT(*) FROM definitions GROUP BY source ORDER BY COUNT(*) DESC").fetchall()
    print("\nSources:")
    for s, c in src:
        print(f"  {s}: {c}")
    
    # 中文词性
    cn = db.execute("SELECT COUNT(*) FROM words WHERE pos IN ('名词','动词','形容词','专有名词','副词','感叹词','数词','谚语','连词','短语','名词，阳性','名','动','形')").fetchone()[0]
    print(f"\n中文词性残留: {cn}")
    
    print(f"\nroom hash: {db.execute('SELECT * FROM room_master_table').fetchone()}")
    db.close()
    
    print("\n=== Auto-rebuild complete! ===")

if __name__ == '__main__':
    main()
