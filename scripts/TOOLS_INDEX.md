# 学术调查工具索引

> **重要提示**：`scripts/` 根目录下多数 `.py` 文件（<500 字节）为兼容性 shim，真实实现位于 `archive/flat_export_redundant_20260501/` 目录下。**使用本索引中列出的真实路径，不要使用根目录 shim。**

---

## 核心基础设施

| 工具 | 真实路径 | 功能 | 何时使用 |
|:---|:---|:---|:---|
|| 案件管理器 | `archive/flat_export_redundant_20260501/core_case_manager.py` | 注册案件、生成案件ID、管理案件状态 | 每次启动新调查 |
| 数据库 | `archive/flat_export_redundant_20260501/core_db.py` | SQLite 案件数据库，9张表 + v3.1 状态机表 | `investigate.py init` 后自动初始化 |
| 配置加载器 | `archive/flat_export_redundant_20260501/core_config_loader.py` | 统一加载 config.yaml，支持 v1→v2 迁移 | 读取案件配置 |
| 工具路由器 | `archive/flat_export_redundant_20260501/core_router.py` | 自动检测调查类型（domestic/international/cross_border） | `investigate.py init` 时自动调用 |
| 水印工具 | `archive/flat_export_redundant_20260501/core_watermark.py` | 零宽度水印嵌入/提取 | 交付报告前 |
| 工具函数 | `archive/flat_export_redundant_20260501/core_utils.py` | 日志、目录创建、JSON保存等共享函数 | 被其他脚本依赖 |

---

## 调查工作流：7步框架 → 工具映射

### Step 0: 案件注册

| 工具 | 路径 | 用法 |
|:---|:---|:---|
| CLI 编排器 | `investigate.py` | `python investigate.py init --case-dir ./cases/姓名_机构 --name "案件名"` |
| 案件管理器 | `core/case_manager.py` | 被 CLI 自动调用；也可直接 `CaseManager().register("客户名")` |

**输出**：案件目录结构、`config.yaml` 模板、`case.db`、`.case/STATE.md`

---

### Step 1: 基本信息建立

**人工操作**：填写 `config.yaml`

**辅助脚本**：无（此步骤以人工为主）

---

### Step 2: 数据采集与导入

| 工具 | 真实路径 | 功能 | 输入 | 输出 |
|:---|:---|:---|:---|:---|
| 数据导入器 | `archive/flat_export_redundant_20260501/domestic_data_importer.py` | 导入 CNKI(.xlsx)/Wanfang(.csv)/WoS(.ris)/JSON，去重 | 数据库导出文件 | `data/unified_papers.json` |
| **研学网评价** | `_private/研学网导师评价表.xlsx` | **结构化导师评价数据库**（7.5万+条），14维度评价+可信度评分。**调查学生评价时必须优先查询**，再辅以小红书/知乎等非结构化来源。 | 导师姓名+学校 | `data/reviews_matched.json`（配合 review_matcher.py） |
| 微信搜索 | `archive/flat_export_redundant_20260501/domestic_wechat_search.py` | 搜狗微信文章搜索与下载 | 关键词 | `data/wechat_articles/*.md` + summary JSON |
| 小红书客户端 | `archive/flat_export_redundant_20260501/international_xiaohongshu_client.py` | 小红书外国导师评价抓取 | 关键词 | `data/xhs_reviews.json` |
| 国际数据获取 | `archive/flat_export_redundant_20260501/international_data_fetcher.py` | OpenAlex/ORCID/S2/GS/PubPeer/RW/arXiv 自动获取 | 学者姓名 | `data/auto_fetched.json` |

**注意**：`scripts/` 根目录的 `data_importer.py` 和 `wechat_search.py` 是 shim，**请使用 `domestic/` 子目录中的真实实现**。

---

### Step 3: 质量评估（核心工具链）

| 工具 | 真实路径 | 功能 | 输入 | 输出 |
|:---|:---|:---|:---|:---|
| **文本画像** | `archive/flat_export_redundant_20260501/analysis_text_profiler.py` | PDF/文本提取、词频统计、原创性标记、参考文献解析 | PDF/.md/.txt | `*_profile.json` |
| **六维评分** | `archive/flat_export_redundant_20260501/analysis_paper_quality_rubric.py` | 六维质量评分（原创性/严谨性/数据/结构/文献/清晰度） | `*_profile.json` + observations | `*_quality.json` |
| **混合评分** | `archive/flat_export_redundant_20260501/analysis_hybrid_scorer.py` | 批量脚本提取 + LLM 深度评分，两阶段流程 | PDF 文件夹 | `_final_ranked_report.json` |
| 引用画像 | `archive/flat_export_redundant_20260501/analysis_citation_profiler.py` | 自引率、团队引用率、h-index 异常检测 | 引用数据 JSON | `citation_report.json` |
| 风格画像 | `archive/flat_export_redundant_20260501/analysis_stylometry_profiler.py` | 文本风格相似度、代笔检测 | 多篇 PDF | `style_report.json` |
| 通用启发式 | `archive/flat_export_redundant_20260501/analysis_common_heuristics.py` | 共享异常规则（C01-C07） | 学者数据 | 异常标记 |

**重要**：`scripts/` 根目录的 `text_profiler.py`、`paper_quality_rubric.py`、`hybrid_scorer.py`、`citation_profiler.py`、`stylometry_profiler.py` 均为 shim。**始终使用 `analysis/` 子目录中的真实实现。**

**六维评分标准用法（单篇）**：
```bash
python analysis/text_profiler.py --input ./pdfs/paper.pdf --output ./data/paper_profile.json
python analysis/paper_quality_rubric.py \
  --profile ./data/paper_profile.json \
  --observations ./data/paper_obs.json \
  --output ./data/paper_quality.json
```

**批量评分用法**：
```bash
# Stage 1: 脚本提取
python analysis/hybrid_scorer.py prepare -i ./pdfs -o ./data/hybrid_scores
# Stage 2: LLM 审阅 llm_review_request.md，输出 llm_observations_batch.json
# Stage 3: 应用评分
python analysis/hybrid_scorer.py apply -i ./pdfs -o ./data/hybrid_scores
```

---

### Step 4: 关系网络

| 工具 | 真实路径 | 功能 | 输入 | 输出 |
|:---|:---|:---|:---|:---|
| 网络可视化 | `archive/flat_export_redundant_20260501/network_network_visualizer.py` | D3.js 交互式关系图谱 | `scholar_data.json` | `*_network.html` |
| 时间线编织 | `archive/flat_export_redundant_20260501/network_timeline_weaver.py` | 事件时间线可视化 | 时间线数据 | 时间线图表 |
| 基金链接 | `archive/flat_export_redundant_20260501/network_grant_linker.py` | 项目-人员-机构关联分析 | 项目数据 | 关联网络 |
| 负空间分析 | `archive/flat_export_redundant_20260501/network_negative_space_analyzer.py` | 检测刻意回避/信息缺失模式 | 调查数据 | 负空间报告 |
| 调查回溯 | `archive/flat_export_redundant_20260501/network_investigation_retrospector.py` | 案件历史回溯与偏差分析 | 案件数据库 | 回溯报告 |

**注意**：`scripts/` 根目录的 `network_visualizer.py`、`timeline_weaver.py`、`grant_linker.py`、`negative_space_analyzer.py`、`investigation_retrospector.py` 均为 shim。

---

### Step 5: 异常检测

| 工具 | 真实路径 | 功能 | 适用轨道 |
|:---|:---|:---|:---|
| 国内验证器 | `archive/flat_export_redundant_20260501/domestic_data_validator.py` | 学者数据 schema + 逻辑验证 | domestic |
| 国际验证器 | `archive/flat_export_redundant_20260501/international_data_validator.py` | 国际学者 schema 验证 | international |
| 跨境验证器 | `archive/flat_export_redundant_20260501/cross_border_validator.py` | 跨境数据一致性检查 | cross_border |
| 国际启发式 | `archive/flat_export_redundant_20260501/international_heuristics_classifier.py` | I01-I07 国际异常检测 | international |
| 基准引擎 | `archive/flat_export_redundant_20260501/benchmark_engine.py` | 学科基准数据库，5层异常评分 | 全部 |
| 学者画像匹配 v2 | `archive/flat_export_redundant_20260501/scholar_profile_matcher_v2.py` | 17维特征向量 +  misconduct 模式匹配 | 全部 |

---

### Step 6: 深度证据层（v3.0）

| 工具 | 真实路径 | 功能 | 触发条件 |
|:---|:---|:---|:---|
| 图像元数据提取 | `deep_evidence/data_forensics/image_metadata_extractor.py` | 提取图片创建时间戳和软件指纹 | `deep_evidence.data_forensics.image_metadata_extraction=true` |
| 统计反推 | `deep_evidence/data_forensics/stats_reverse_engineer.py` | 反推报告统计数据的内部一致性 | `deep_evidence.data_forensics.stats_reverse_engineer=true` |
| 预印本监控 | `deep_evidence/publication_trace/preprint_monitor.py` | 监控 arxiv/biorxiv/medrxiv | `deep_evidence.publication_trace.preprint_sources` 配置 |
| 双语发表检测 | `deep_evidence/publication_trace/bilingual_publication_detector.py` | CNKI + 英文期刊重复发表检测 | `deep_evidence.publication_trace.check_bilingual=true` |
| 会议-期刊重叠检测 | `deep_evidence/publication_trace/conference_paper_mapper.py` | 会议投稿与期刊投稿重叠检测 | `deep_evidence.publication_trace.check_conference_overlap=true` |
| Crossref 事件追踪 | `deep_evidence/publication_trace/crossref_event_tracker.py` | 追踪论文后续更正、撤稿、评论 | 自动 |
| 伦理声明解析 | `deep_evidence/ethics_audit/ethics_statement_parser.py` | 解析论文伦理声明 | `deep_evidence.ethics_audit.enabled=true` |
| 临床试验注册检查 | `deep_evidence/ethics_audit/clinical_trial_registry_checker.py` | ChiCTR/ClinicalTrials.gov 核对 | `deep_evidence.ethics_audit.registry_sources` 配置 |
| 编辑自出版检测 | `deep_evidence/peer_review_intel/editorial_self_publishing_detector.py` | 检测编委在自己的期刊大量发文 | `deep_evidence.peer_review_intel.check_editorial_self_publishing=true` |
| 推荐审稿人网络 | `deep_evidence/peer_review_intel/recommended_reviewer_network.py` | 检测推荐审稿人利益关联 | `deep_evidence.peer_review_intel.check_recommended_reviewer_network=true` |
| 审稿周期分析 | `deep_evidence/peer_review_intel/review_cycle_analyzer.py` | 异常快速审稿检测 | `deep_evidence.peer_review_intel.cycle_benchmark_years` 配置 |
| 期刊撤稿历史 | `deep_evidence/peer_review_intel/journal_retraction_history.py` | 目标期刊历史撤稿率分析 | 自动 |
| 证据链构建 | `deep_evidence/evidence_compiler/evidence_chain_builder.py` | 多源证据链自动构建 | deep_evidence 阶段后 |
| 信号聚合器 | `deep_evidence/evidence_compiler/signal_aggregator.py` | 多维度异常信号聚合 | aggregated 阶段 |

---

### Step 7: 报告生成

| 工具 | 真实路径 | 功能 | 输入 | 输出 |
|:---|:---|:---|:---|:---|
| 报告 Prompt 优化器 | `archive/flat_export_redundant_20260501/report_report_prompt_optimizer.py` | 为指定 LLM 生成优化后的报告 prompt | `scholar_data.json` + 模板 | `report_prompt.md` |
| 国内报告模板 | `archive/flat_export_redundant_20260501/report_report_template.md` | 国内学者报告 Markdown 模板 | LLM prompt | Markdown 报告 |
| 国际报告模板 | `archive/flat_export_redundant_20260501/report_international_template.md` | 国际学者报告 Markdown 模板 | LLM prompt | Markdown 报告 |

**注意**：`scripts/` 根目录的 `report_prompt_optimizer.py` 是 shim。

---

## 辅助工具

| 工具 | 真实路径 | 功能 |
|:---|:---|:---|
| 学者数据构建器 | `archive/flat_export_redundant_20260501/domestic_scholar_data_builder.py` / `archive/flat_export_redundant_20260501/international_scholar_data_builder.py` | 从 config + 脚本输出聚合 `scholar_data.json` |
| 缺失报告生成器 | `archive/flat_export_redundant_20260501/international_missing_reporter.py` | 自动生成"还缺什么+去哪里找"指南 |
| 跨境合并器 | `archive/flat_export_redundant_20260501/cross_border_merger.py` | 合并 domestic + international 数据 |
| 评估器 | `archive/flat_export_redundant_20260501/international_evaluator.py` | JCR quartile / CiteScore / tenure 评估 |
| 基准演示 | `archive/flat_export_redundant_20260501/benchmark_demo.py` | 一键演示：初始化→导入→基线→批量计算 |
| 基准可视化 | `archive/flat_export_redundant_20260501/benchmark_demo_visual.py` | 基准引擎可视化报告 |
| 学者画像匹配 v1 | `archive/flat_export_redundant_20260501/scholar_profile_matcher.py` | 基础画像相似度匹配 |
| 学者画像匹配 v2 | `archive/flat_export_redundant_20260501/scholar_profile_matcher_v2.py` | 17维特征向量 + 风险画像 |

---

## 快速查错：常见路径陷阱

| 错误路径 | 正确路径 | 陷阱说明 |
|:---|:---|:---|
| `scripts/text_profiler.py` | `archive/flat_export_redundant_20260501/analysis_text_profiler.py` | 根目录是 415 字节 shim |
| `scripts/paper_quality_rubric.py` | `archive/flat_export_redundant_20260501/analysis_paper_quality_rubric.py` | 根目录是 457 字节 shim |
| `scripts/hybrid_scorer.py` | `archive/flat_export_redundant_20260501/analysis_hybrid_scorer.py` | 根目录是 415 字节 shim |
| `scripts/data_importer.py` | `archive/flat_export_redundant_20260501/domestic_data_importer.py` | 根目录是 607 字节旧版 |
| `scripts/data_validator.py` | `archive/flat_export_redundant_20260501/domestic_data_validator.py` | 根目录是 421 字节 shim |
| `scripts/network_visualizer.py` | `archive/flat_export_redundant_20260501/network_network_visualizer.py` | 根目录是 441 字节 shim |
| `scripts/citation_profiler.py` | `archive/flat_export_redundant_20260501/analysis_citation_profiler.py` | 根目录是 439 字节 shim |
| `scripts/stylometry_profiler.py` | `archive/flat_export_redundant_20260501/analysis_stylometry_profiler.py` | 根目录是 451 字节 shim |
| `scripts/scholar_data_builder.py` | `archive/flat_export_redundant_20260501/domestic_scholar_data_builder.py` | 根目录是 457 字节 shim |
| `scripts/report_prompt_optimizer.py` | `archive/flat_export_redundant_20260501/report_report_prompt_optimizer.py` | 根目录是 467 字节 shim |
| `scripts/wechat_search.py` | `archive/flat_export_redundant_20260501/domestic_wechat_search.py` | 根目录是 415 字节 shim |
| `scripts/review_matcher.py` | `archive/flat_export_redundant_20260501/domestic_review_matcher.py` | 根目录是 421 字节 shim |

---

## 运行环境要求

所有脚本统一通过以下方式设置 Python 路径：

```bash
export PYTHONPATH="/path/to/scripts:$PYTHONPATH"
# 或
python3 -m analysis.text_profiler ...
```

依赖安装：
```bash
pip install pdfplumber PyMuPDF PyPDF2 pyyaml openpyxl
```

---

*最后更新：2026-05-02*
