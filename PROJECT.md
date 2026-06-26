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

### v0.2 — 词库增强 (进行中)
- 目标：多源融合、语义增强、例句完备
- 详见 tasks/v0.2.md

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
│   └── database/dict.db   # 预填充 SQLite (不入 git)
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
