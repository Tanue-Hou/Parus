# Parus (Парус) — 俄汉词典 App

> ⛵ 俄语学习者的帆 — 一本好用的离线俄汉词典

## 项目概述

Android 离线俄汉词典应用，面向俄语学习者（留学生/翻译/研究者），支持俄→中、中→俄双向查询，25万词条离线可用。

## 技术栈

- Kotlin + Jetpack Compose (UI)
- Room (数据库, SQLite)
- Koin (依赖注入)
- StateFlow (响应式状态)
- MVVM 架构

## 当前版本

### v0.1 (2026-06-25) — MVP ✅
- BKRS 25万词条 + Wiktionary 100万变格
- Apple Spotlight 风格搜索界面
- 俄→中 FTS5 高速搜索 (4.5ms/次)
- 中→俄 LIKE + 6级 GLOB 智能排序
- 词形还原（输入变格形式自动匹配原型）
- 多词库融合架构（source 字段区分来源）

### v0.2 — 词库增强 ✅ (2026-06-27)
- 多源融合：BKRS + OpenRussian + Kaikki + Tatoeba 四源聚合
- 词条总数：255,188 → **637,295**（+382k Kaikki 新增）
- 变格变位：120万 → **209万**（清洗去噪，30%噪声→<2%）
- 例句库：0 → **73,243 条**（Tatoeba + BKRS内嵌 + Kaikki）
- POS 覆盖：18% → **100%**（pymorphy3 + OpenRussian + Kaikki + 后缀启发）
- 管线：Phase 1 预处理 → Phase 2 数据增强 → Phase 3 数据库构建
- 详见 tasks/v0.2-fusion-pipeline.md

## 项目结构

```
Parus/
├── app/src/main/java/com/tanue/parus/
│   ├── data/
│   │   ├── database/     # Room Database + DAO
│   │   ├── model/         # Entity + 关系模型
│   │   └── repository/    # Repository 层
│   ├── di/                # Koin 依赖注入
│   └── presentation/     # Compose UI
├── app/src/main/assets/
│   └── database/dict.db   # v0.1 预填充 SQLite (不入 git)
├── pipeline/              # v0.2 数据管线
│   ├── config.py          # 配置
│   ├── utils.py           # 工具函数
│   ├── phase1_preprocess.py  # Phase 1: 数据预处理
│   ├── phase2_enrich.py      # Phase 2: 数据增强
│   ├── phase3_build_db.py    # Phase 3: 数据库构建
│   └── output/            # 管线产出 (不入 git)
├── tasks/                 # 版本任务计划
├── logs/                  # 操作日志
├── build_bkrs_db.py       # v0.1 构建脚本
└── build_parus_db.py      # v0.2 多源构建脚本 (待实现)
```

## 数据库 Schema (v0.1)

```
words (id, lemma, lemma_stressed, pos)
definitions (id, word_id, source, definition)
inflections (id, word_id, form, grammar_tag)
```

## 开发日志

见 logs/operations.log
