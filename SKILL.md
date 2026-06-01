---
name: academic-investigation
description: Academic integrity investigation and scholar profile analysis system. Use when conducting comprehensive academic background checks, credential verification, publication analysis, or institutional affiliation audits of scholars, researchers, or faculty members. Triggers on phrases like "调查学者", "学术调查", "查某人的学术背景", "核实论文", "学术档案调查", "学者背调", or when analyzing academic misconduct, credential inflation, publication quality, or research integrity issues.
---

> ⚠️ **LLM 强制指令（请逐条执行）**：
> 
> 1. **优先使用现有脚本**。本系统的工具链位于 `scripts/` 目录下，不要自己写 Python 代码替代现有工具。
> 2. **所有脚本路径以下方工具索引表为准**。`scripts/` 根目录下绝大多数 <500 字节的 `.py` 文件是兼容性 shim，真实实现位于子目录中。
> 3. **执行流程**：先 ls 确认文件存在 → 再执行。如果不确定某个脚本的具体路径或参数，先 Read 该脚本头部的 docstring。
> 4. **遵循七步顺序**：Basic Profile → Output Quantity → Quality Assessment → Relationship Network → Anomaly Detection → Multi-Source Validation → Report Generation。不要跳步。
> 5. **分层加载**：执行具体步骤前，先 Read 对应的 `docs/skill/` 文档获取详细流程。

# Academic Investigation Skill

Comprehensive academic background investigation system based on proven methodology from verified case studies.

## Overview

A systematic 7-step framework for investigating academic profiles, verifying credentials, analyzing publication quality, and identifying potential academic misconduct or credential inflation.

## When to Use

- Investigating a scholar's academic background or credentials
- Verifying publication claims or academic achievements
- Analyzing research quality and originality
- Checking for academic misconduct (plagiarism, duplicate publication, credential fraud)
- Auditing institutional affiliations and career progression
- Evaluating relationship networks and resource dependencies

## Semi-Automatic Workflow Philosophy

**Human-in-the-loop** design. Scripts assist with computation; human judgment drives decisions.

| Actor | Responsibilities |
|:------|:----------------|
| **Human** | CNKI/Wanfang/WoS searches, institutional verification, monograph acquisition, final interpretation |
| **LLM** | Tool selection, signal interpretation, hypothesis generation, report drafting |
| **Scripts** | Data normalization, quantitative analysis, text profiling, report assembly |

```
scripts/
├── core/                    # 共享基础设施
├── domestic/                # 国内学者调查适配器
├── international/           # 国际学者/导师调查适配器
├── cross_border/            # 海归学者调查（合并国内+国际）
├── analysis/                # 共享分析模块
├── network/                 # 关系网络与腐败图谱
├── deep_evidence/           # 深度证据层（数据取证/发表链/伦理/同行评议/证据编译）
├── report/                  # 报告生成
├── agents/                  # 多智能体协作层
├── delivery/                # 交付层（自检+格式化）
├── backend/                 # Web 后端 API
└── investigate.py           # CLI 编排入口
```

---

## 精准工具索引表

> 每个工具的真实路径已排除根目录兼容性 shim。执行前先 `ls` 确认文件存在。

### Core（基础设施）

| 工具 | 路径 | 功能 | 输入 | 输出 | 时机 | Track |
|:-----|:-----|:-----|:-----|:-----|:-----|:------|
| case_manager | `scripts/core/case_manager.py` | 案件注册与 ID 生成 (AD-YYYY-MM-DD-NNN) | 甲方名称 | case_id + 目录结构 | Step 0 | all |
| db | `scripts/core/db.py` | SQLite 案件数据库（9表） | case_id | .db 文件 | Step 0 后自动 | all |
| config_loader | `scripts/core/config_loader.py` | 统一配置加载（v1→v2 迁移） | config.yaml | config dict | 全程 | all |
| router | `scripts/core/router.py` | 调查类型路由 (domestic/international/cross_border) | config | track 判定 | Step 0 | all |
| watermark | `scripts/core/watermark.py` | 零宽水印嵌入/提取 | Markdown 报告 | 水印报告 | Step 8 交付 | all |
| utils | `scripts/core/utils.py` | 日志、JSON 存储等公共工具 | — | — | 全程 | all |

### Data Import（数据导入）

| 工具 | 路径 | 功能 | 输入 | 输出 | 时机 | Track | 依赖 |
|:-----|:-----|:-----|:-----|:-----|:-----|:------|:-----|
| data_importer | `scripts/domestic/data_importer.py` | CNKI/万方/WoS 导入 + 去重 | 导出的 txt/csv 文件 | 统一 JSON 论文列表 | Step 2 | domestic | init 完成 |
| data_fetcher | `scripts/international/data_fetcher.py` | OpenAlex/ORCID/S2/GS/PubPeer/RW/arXiv 自动抓取 | config.yaml (scholar name + IDs) | `auto_fetched.json` | Step 2 | international | init 完成 |
| openalex_enricher | `scripts/domestic/openalex_enricher.py` | 用 OpenAlex 补充国内论文的国际引用数据 | 论文 JSON | 增强后 JSON | Step 2 后 | domestic | data_importer |
| xiaohongshu_client | `scripts/international/xiaohongshu_client.py` | 小红书学生评价抓取 + 情感/维度提取 | 导师名/学校名 | 评价 JSON | Step 6 | international/cross_border | — |
| wechat_search | `scripts/domestic/wechat_search.py` | 微信公众号文章搜索（补充线索） | 关键词 | 文章列表 | Step 6 | domestic | — |
| review_matcher | `scripts/domestic/review_matcher.py` | 研学网评价表匹配 → investigation_leads | 导师名/学校 | 结构化 leads JSON | Step 6 | domestic | `_private/研学网导师评价表.xlsx` |

### Analysis（分析）

| 工具 | 路径 | 功能 | 输入 | 输出 | 时机 | Track | 依赖 |
|:-----|:-----|:-----|:-----|:-----|:-----|:------|:-----|
| text_profiler | `scripts/analysis/text_profiler.py` | PDF/Markdown/文本分析: 词频、原创性标记、引用模式、论文类型分类 | PDF/Markdown 文件 | JSON profile | Step 3 | all | 论文 PDF 获取 |
| paper_quality_rubric | `scripts/analysis/paper_quality_rubric.py` | 论文六维评分（创新性/方法/论证/文献/写作/贡献） | text_profiler 输出 JSON | 六维评分 JSON | Step 3 | all | text_profiler |
| hybrid_scorer | `scripts/analysis/hybrid_scorer.py` | 综合评分（合并多维度） | 多个评分 JSON | 综合分 JSON | Step 3 | all | paper_quality_rubric |
| stylometry_profiler | `scripts/analysis/stylometry_profiler.py` | 风格计量学：虚词频率、句法结构、相似度矩阵 | 多篇文本 | 相似度热力图 + JSON | Step 5 代笔检测 | all | 多篇 PDF |
| citation_profiler | `scripts/analysis/citation_profiler.py` | 引用分析：自引率、互引、引用质量分布 | 论文 JSON (含引用) | 引用分析 JSON | Step 4/5 | all | data_importer/data_fetcher |
| common_heuristics | `scripts/analysis/common_heuristics.py` | 共享异常检测规则 (C01-C07): 产出量、期刊集中度、引用模式等 | 论文列表 + author_profile | 异常 flags 列表 | Step 5 | all | Step 2 数据 |
| review_aggregator | `scripts/analysis/review_aggregator.py` | 多源评价合并（研学网 + 小红书 + RMP） | 多个评价 JSON | 合并评价 JSON | Step 6 | all | 各评价源 |
| journal_credibility_checker | `scripts/analysis/journal_credibility_checker.py` | 期刊可信度评估（掠夺性期刊检测） | ISSN/期刊名列表 | 风险评级 JSON | Step 5 | all | — |

### Network（关系网络）

| 工具 | 路径 | 功能 | 输入 | 输出 | 时机 | Track | 依赖 |
|:-----|:-----|:-----|:-----|:-----|:-----|:------|:-----|
| network_visualizer | `scripts/network/network_visualizer.py` | D3.js 交互式关系网络图 | relationship_network JSON | `{name}_network.html` | Step 4 | all | Step 2 数据 |
| timeline_weaver | `scripts/network/timeline_weaver.py` | 时间线编织（事件序列可视化） | career_timeline JSON | 时间线 HTML | Step 4 | all | Step 1 |
| grant_linker | `scripts/network/grant_linker.py` | 基金项目关联分析 | 基金数据 JSON | 关联图 JSON | Step 4 | domestic | — |
| negative_space_analyzer | `scripts/network/negative_space_analyzer.py` | 负面空间分析（官方通报回避了什么） | 通报文本 | evasion_score matrix | Step 5 | all | — |
| citation_constellation | `scripts/network/citation_constellation.py` | 引用星座图（引用关系可视化） | 引用数据 JSON | 星座图 HTML | Step 4/5 | all | citation_profiler |
| investigation_retrospector | `scripts/network/investigation_retrospector.py` | 调查复盘（提取可复用签名） | 完成的案件数据 | heuristics 更新建议 | 案件结束后 | all | — |

### Deep Evidence / Data Forensics（数据取证）

| 工具 | 路径 | 功能 | 输入 | 输出 | 时机 | Track | 依赖 |
|:-----|:-----|:-----|:-----|:-----|:-----|:------|:-----|
| data_integrity_checker | `scripts/deep_evidence/data_forensics/data_integrity_checker.py` | 数据造假统计指纹检测（尾数/小数位/重复） | Excel/CSV 原始数据 | risk_score + findings JSON | Step 5 有原始数据时 | all | 人工提取表格数据 |
| stats_reverse_engineer | `scripts/deep_evidence/data_forensics/stats_reverse_engineer.py` | 统计反推一致性检验（均值/SD/n → t/F 值验证） | 论文表格统计量 | 不一致性标记 JSON | Step 5 | all | 人工提取统计量 |
| image_metadata_extractor | `scripts/deep_evidence/data_forensics/image_metadata_extractor.py` | 图像元数据提取（EXIF/创建时间/软件） | 图片文件 | 元数据 JSON | Step 5 | all | 论文图片提取 |

### Deep Evidence / Publication Trace（发表链追踪）

| 工具 | 路径 | 功能 | 输入 | 输出 | 时机 | Track | 依赖 |
|:-----|:-----|:-----|:-----|:-----|:-----|:------|:-----|
| preprint_monitor | `scripts/deep_evidence/publication_trace/preprint_monitor.py` | 预印本监控（arXiv/bioRxiv/SSRN） | 作者名/DOI | 预印本-期刊映射 JSON | Step 5 | all | — |
| conference_paper_mapper | `scripts/deep_evidence/publication_trace/conference_paper_mapper.py` | 会议论文→期刊论文转化追踪 | 论文列表 JSON | 转化映射 JSON | Step 5 | all | Step 2 数据 |
| bilingual_publication_detector | `scripts/deep_evidence/publication_trace/bilingual_publication_detector.py` | 双语发表检测（中英文重复发表） | 合并论文列表 | 疑似重复对 JSON | Step 5 | cross_border | merger 输出 |
| crossref_event_tracker | `scripts/deep_evidence/publication_trace/crossref_event_tracker.py` | Crossref 事件追踪（更正/撤稿/表达关注） | DOI 列表 | 事件 JSON | Step 5 | all | Step 2 数据 |

### Deep Evidence / Ethics & Peer Review（伦理与同行评议）

| 工具 | 路径 | 功能 | 输入 | 输出 | 时机 | Track | 依赖 |
|:-----|:-----|:-----|:-----|:-----|:-----|:------|:-----|
| ethics_statement_parser | `scripts/deep_evidence/ethics_audit/ethics_statement_parser.py` | 伦理声明解析（IRB 批号提取与验证） | 论文 PDF/文本 | 伦理声明结构化 JSON | Step 5 | all | 论文 PDF |
| clinical_trial_registry_checker | `scripts/deep_evidence/ethics_audit/clinical_trial_registry_checker.py` | 临床试验注册核查（ClinicalTrials.gov/ChiCTR） | 注册号列表 | 注册状态 JSON | Step 5 | all | ethics_statement_parser |
| review_cycle_analyzer | `scripts/deep_evidence/peer_review_intel/review_cycle_analyzer.py` | 审稿周期分析（投稿→接收时间异常检测） | 论文元数据 JSON | 周期异常 flags | Step 5 | all | Step 2 数据 |
| editorial_self_publishing_detector | `scripts/deep_evidence/peer_review_intel/editorial_self_publishing_detector.py` | 编委自发文检测（编委任期内发文模式） | 编委名单 + 论文列表 | 自发文率 JSON | Step 5 | all | 人工收集编委名单 |
| recommended_reviewer_network | `scripts/deep_evidence/peer_review_intel/recommended_reviewer_network.py` | 推荐审稿人网络分析 | 审稿人数据 | 网络图 JSON | Step 5 | all | — |
| journal_retraction_history | `scripts/deep_evidence/peer_review_intel/journal_retraction_history.py` | 期刊撤稿历史查询 | 期刊名/ISSN | 撤稿记录 JSON | Step 5 | all | — |

### Deep Evidence / Evidence Compiler（证据链编译）

| 工具 | 路径 | 功能 | 输入 | 输出 | 时机 | Track | 依赖 |
|:-----|:-----|:-----|:-----|:-----|:-----|:------|:-----|
| signal_aggregator | `scripts/deep_evidence/evidence_compiler/signal_aggregator.py` | 多模块信号聚合（统一格式汇总所有异常信号） | 各模块输出 JSON | 聚合信号 JSON | Step 5 末尾 | all | 各检测模块 |
| evidence_chain_builder | `scripts/deep_evidence/evidence_compiler/evidence_chain_builder.py` | 证据链构建（信号→假设→证据链） | 聚合信号 JSON | 证据链 JSON + 可视化 | Step 7 前 | all | signal_aggregator |

### Benchmark & Matching（基准线与匹配）

| 工具 | 路径 | 功能 | 输入 | 输出 | 时机 | Track | 依赖 |
|:-----|:-----|:-----|:-----|:-----|:-----|:------|:-----|
| benchmark_engine | `scripts/benchmark_engine.py` | 学科基准线数据库：5层异常评分（Z-score/对数正态/t分布） | 结构化指标 (h-index, 年均论文等) | composite_score + risk_level JSON | Step 5 | all | Step 2 数据 |
| scholar_profile_matcher_v2 | `scripts/scholar_profile_matcher_v2.py` | 17维特征向量匹配：与46案例库对比 + 不端模式相似度 | scholar_data JSON | 匹配报告 JSON | Step 5 后 | all | Step 3 + Step 5 |

### Validation（校验）

| 工具 | 路径 | 功能 | 输入 | 输出 | 时机 | Track | 依赖 |
|:-----|:-----|:-----|:-----|:-----|:-----|:------|:-----|
| data_validator (domestic) | `scripts/domestic/data_validator.py` | 国内 scholar_data JSON schema + 逻辑校验 | scholar_data JSON | 校验报告 | Step 7 前 | domestic | scholar_data_builder |
| data_validator (international) | `scripts/international/data_validator.py` | 国际 scholar_data schema + 逻辑校验 | scholar_data JSON | 校验报告 | Step 8 前 | international | scholar_data_builder |
| cross_border validator | `scripts/cross_border/validator.py` | 跨境一致性检查（时间线重叠、学历真伪） | merged scholar_data | 一致性报告 JSON | Step 3 (cross_border) | cross_border | merger |
| scholar_data_builder (domestic) | `scripts/domestic/scholar_data_builder.py` | 构建统一 scholar_data.json | config + 各脚本输出 | `scholar_data.json` | 各步骤输出后 | domestic | — |
| scholar_data_builder (international) | `scripts/international/scholar_data_builder.py` | 构建国际 scholar_data.json | config + auto_fetched + xhs | `scholar_data.json` | 各步骤输出后 | international | — |
| cross_border merger | `scripts/cross_border/merger.py` | 合并国内+国际 scholar_data | 两套 JSON | merged JSON | Step 2 后 | cross_border | 两个 builder |

### Report & Delivery（报告与交付）

| 工具 | 路径 | 功能 | 输入 | 输出 | 时机 | Track | 依赖 |
|:-----|:-----|:-----|:-----|:-----|:-----|:------|:-----|
| report_prompt_optimizer | `scripts/report/report_prompt_optimizer.py` | 报告 prompt 优化（注入语言规范 + 置信度体系） | 报告草稿 | 优化后 prompt | Step 7 | all | — |
| md_to_pdf | `scripts/md_to_pdf.py` | Markdown→PDF（A4/封面/TOC/图表自动生成） | Markdown 报告 | styled PDF | Step 7 后 | all | chart_generator |
| chart_generator | `scripts/chart_generator.py` | 自动生成图表（雷达/饼图/热力图/时间线/网络图） | Markdown 中 `<!--chart:-->` 注解 | PNG 图表 | Step 7 | all | — |

### Orchestration（编排）

| 工具 | 路径 | 功能 | 输入 | 输出 | 时机 | Track |
|:-----|:-----|:-----|:-----|:-----|:-----|:------|
| investigate.py | `scripts/investigate.py` | CLI 主入口：init/import/generate/smart-step 等子命令 | CLI args + config.yaml | 各步骤输出 | 全程 | all |
| investigate_visual.py | `scripts/investigate_visual.py` | Rich 终端可视化包装 + smart-step 自动推进 | 同 investigate.py | 彩色终端输出 | 全程 | all |

---

## 三 Track 路由表

| Track | 判定条件 | 入口命令 | 详细流程文档 |
|:------|:---------|:---------|:-------------|
| **domestic** | 学者仅在国内机构任职，无海外学位/教职 | `investigate.py init --type domestic` | `docs/skill/workflow_domestic.md` |
| **international** | 外国学者/导师，或仅在海外机构任职 | `investigate.py init --type international` | `docs/skill/workflow_international.md` |
| **cross_border** | 学者同时具有国内任职 + 海外学位/教职经历 | `investigate.py init --type cross_border` | `docs/skill/workflow_cross_border.md` |

---

## 7 步框架概览

| Step | 名称 | 核心动作 | 主要工具 |
|:-----|:-----|:---------|:---------|
| 0 | Case Registry | 案件注册，生成唯一 ID | `case_manager.py` |
| 1 | Basic Profile | 建立身份时间线 | `config.yaml` + `investigate.py init` |
| 2 | Output Quantity | 核实声称 vs 实际产出 | `data_importer` / `data_fetcher` |
| 3 | Quality Assessment | 论文质量六维评分 | `text_profiler` → `paper_quality_rubric` |
| 4 | Relationship Network | 合作关系与资源依赖图谱 | `network_visualizer` + `grant_linker` |
| 5 | Anomaly Detection | 异常检测 + 深度证据 | `common_heuristics` + `deep_evidence/*` + `benchmark_engine` |
| 6 | Multi-Source Validation | 多源交叉验证 | `review_aggregator` + `wechat_search` / `xiaohongshu_client` |
| 7 | Report Generation | 报告生成 + 交付 | `report_prompt_optimizer` → `md_to_pdf` → `watermark` |

> 📖 每步的详细流程、证据标准、红旗信号，请 Read `docs/skill/workflow_domestic.md`（国内）或对应 track 文档。

---

## PDF 直接审查补充流程

当用户直接提供论文 PDF（而非结构化数据）时：

1. **Read PDF** → 提取文本、表格、Figure caption
2. **六式扫描** → 图片复用/数据造假/图片拼接/统计异常/产出异常/方法矛盾
3. **数值提取** → 从表格提取数值，保存 CSV → 可选喂给 `data_integrity_checker.py`
4. **交叉验证** → 多个可疑点是否指向系统性造假
5. **报告输出** → 结构化 Markdown 审查报告

> ⚠️ LLM 对图片的分析基于视觉理解，无法进行像素级 ELA。需精确图像比对时标注"建议使用 ImageTwin/Forensically 进一步验证"。

---

## 分层加载指令

执行具体步骤时，按需 Read 以下文档：

| 场景 | Read 文档 |
|:-----|:----------|
| 执行国内 track 某步骤的详细流程 | `docs/skill/workflow_domestic.md` |
| 执行国际 track 某步骤的详细流程 | `docs/skill/workflow_international.md` |
| 执行海归 track 的合并/验证流程 | `docs/skill/workflow_cross_border.md` |
| 需要了解 13+8 种调查类型定义 | `docs/skill/investigation_types.md` |
| 需要扩展调查模块 A-E 的详细方法 | `docs/skill/extended_modules.md` |
| 需要深度证据层的架构设计细节 | `docs/skill/deep_evidence_layer.md` |
| 需要多智能体/交付层的协作协议 | `docs/skill/multi_agent_delivery.md` |
| 需要导师蒸馏服务的 API 接口 | `docs/skill/mentor_distill.md` |
| 生成报告前的交付物检查清单 | `docs/skill/report_checklist.md` |
| 需要启发式规则库（结构签名 S1-S10） | `scripts/heuristics.md` |
| 需要报告语言规范（置信度 L1-L5） | `scripts/report_language_spec.md` |
