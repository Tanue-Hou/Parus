"""
Parus v0.2 — 融合管线配置
所有路径和参数集中管理
"""

import os

# ============================================================
# 路径配置
# ============================================================

# 项目根
PROJECT_ROOT = r"/mnt/d/Android/Parus"

# 现有 BKRS 数据库
BKRS_DB = os.path.join(PROJECT_ROOT, "app/src/main/assets/database/dict.db")

# OpenRussian ZIP
OPEN_RUSSIAN_ZIP = r"/mnt/c/Users/Tanue Hou/Downloads/russian-dictionary-master.zip"

# Kaikki JSONL
KAIKKI_JSONL = r"/mnt/c/Users/Tanue Hou/Downloads/kaikki.org-dictionary-Russian.jsonl"

# Tatoeba TSV
TATOEBA_TSV = r"/mnt/c/Users/Tanue Hou/Downloads/Sentence pairs in Russian-Mandarin Chinese - 2026-06-26.tsv"

# 输出目录
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "pipeline", "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Phase 1 产出
INTERMEDIATE_JSONL = os.path.join(OUTPUT_DIR, "intermediate.jsonl")

# Phase 2 产出
FUSED_JSONL = os.path.join(OUTPUT_DIR, "fused.jsonl")
LLM_CACHE_JSON = os.path.join(OUTPUT_DIR, "llm_cache.json")

# Phase 3 产出
NEW_DB_PATH = os.path.join(PROJECT_ROOT, "app", "src", "main", "assets", "database", "dict_v2.db")

# 日志
LOG_FILE = os.path.join(OUTPUT_DIR, "pipeline.log")

# ============================================================
# 数据参数
# ============================================================

# BKRS DSL 文件
BKRS_GZ = r"/mnt/c/Users/Tanue Hou/.gemini/antigravity/brain/c6799849-977e-4cbd-94b1-ea495082674e/scratch/dabruks_260625.gz"

# ============================================================
# LLM 配置
# ============================================================

# Hermes API 端点 (本地)
HERMES_API_URL = "http://localhost:8648/api/chat/completions"

# 模型
LLM_MODEL = "ark-code-latest"

# 并发
LLM_MAX_WORKERS = 10

# 批次大小 (每批处理多少条后保存缓存)
LLM_SAVE_INTERVAL = 50

# 重试
LLM_MAX_RETRIES = 3

# ============================================================
# 数据库参数
# ============================================================

# 批量插入大小
BATCH_SIZE = 5000

# ============================================================
# 噪声过滤
# ============================================================

NOISE_TAGS = {
    'romanization', 'ru-conj', 'ru-noun-table', 'inflection-template',
    'hard-stem', 'accent-d', 'class', 'noun-from-verb', 'table-tags',
    'no-table-tags', 'no-short-form', 'velar-stem', 'accent-a',
    'accent-b', 'accent-c', 'accent-d', 'accent-e', 'accent-f',
}
