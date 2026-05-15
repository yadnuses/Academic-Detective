---
name: academic-investigation
description: Academic integrity investigation and scholar profile analysis system. Use when conducting comprehensive academic background checks, credential verification, publication analysis, or institutional affiliation audits of scholars, researchers, or faculty members. Triggers on phrases like "调查学者", "学术调查", "查某人的学术背景", "核实论文", "学术档案调查", "学者背调", or when analyzing academic misconduct, credential inflation, publication quality, or research integrity issues.
---

> ⚠️ **LLM 强制指令（请逐条执行）**：
> 
> 1. **不要自己创建脚本**。本系统的所有工具脚本已预装在 `archive/flat_export_redundant_20260501/` 目录下。不要自己写 Python 代码替代现有工具。
> 2. **所有脚本路径以 `archive/flat_export_redundant_20260501/` 开头**。SKILL.md 中描述的路径是抽象路径（如 `scripts/analysis/text_profiler.py`），实际文件在 `archive/flat_export_redundant_20260501/analysis_text_profiler.py`。
> 3. **执行流程**：先 ls 确认文件存在 → 再执行。如果不确定某个脚本的具体路径或参数，先 read_file 查看该脚本头部的 docstring 和 main() 函数，不要猜测。
> 4. **遵循七步顺序**：Basic Profile → Output Quantity → Quality Assessment → Relationship Network → Anomaly Detection → Multi-Source Validation → Report Generation。不要跳步。

# Academic Investigation Skill

Comprehensive academic background investigation system based on proven methodology from three anonymized verified case studies.

## Overview

This skill provides a systematic 7-step framework for investigating academic profiles, verifying credentials, analyzing publication quality, and identifying potential academic misconduct or credential inflation.

## When to Use

Use this skill when:
- Investigating a scholar's academic background or credentials
- Verifying publication claims or academic achievements
- Analyzing research quality and originality
- Checking for academic misconduct (plagiarism, duplicate publication, credential fraud)
- Auditing institutional affiliations and career progression
- Comparing stated vs. actual academic outputs
- Evaluating relationship networks and resource dependencies

## Semi-Automatic Workflow Philosophy

This skill is designed as a **human-in-the-loop, semi-automatic investigation system**. Scripts assist with repetitive labor and complex computations, but human judgment remains at the center of every critical decision.

### What Humans Do

| Task | Why Human |
|:---|:---|
| **CNKI / Wanfang / WoS searches** | Automated crawling of subscription databases is legally risky, technically fragile, and institution-dependent. The investigator manually searches, exports results, and downloads PDFs. |
| **Institutional website verification** | Manual saving of HTML snapshots and screenshots. If a site is dynamic or redesigned, the investigator resolves it directly. No automated scraper is used. |
| **Monograph / dissertation acquisition** | Full-text books and theses must be obtained manually (purchase, library loan, or provided by the client). Scripts then perform quantitative text analysis on the downloaded files. |
| **Final interpretation** | Confidence ratings, ethical framing, and balanced conclusions require human judgment. Scripts generate drafts; humans finalize. |

### What Scripts Do

| Task | Script Role |
|:---|:---|
| **Data normalization** | Convert manually exported CNKI/Wanfang results, PDF metadata, and web snapshots into unified JSON schemas. |
| **Quantitative analysis** | Count papers, map author positions, detect timeline anomalies, and build collaboration networks from structured data. |
| **Text profiling** | Analyze downloaded monographs/PDFs for term frequency, originality markers, reference patterns, and theoretical depth indicators. |
| **Report drafting** | Assemble findings into structured Markdown reports with evidence溯源, confidence ratings, and two-sided assessments. |

### Script Architecture (4-Layer Semi-Automatic Chain)

```
scripts/
├── core/                    # Shared infrastructure (moved from scripts/ root)
│   ├── utils.py, db.py, case_manager.py, watermark.py
│   ├── router.py            # Investigation type routing (domestic/international/cross_border)
│   └── config_loader.py     # Unified config loading with v1→v2 migration
├── domestic/                # Domestic (CN) scholar investigation adapter
│   ├── data_importer.py     # CNKI/Wanfang/WoS import + deduplication
│   ├── data_validator.py    # Schema validation for domestic scholar_data
│   ├── scholar_data_builder.py
│   ├── review_matcher.py    # 导师评价网 structured review matching
│   └── wechat_search.py
├── international/           # International scholar/advisor investigation adapter (NEW)
│   ├── data_fetcher.py      # OpenAlex/ORCID/Semantic Scholar/Google Scholar/PubPeer/Retraction Watch/arXiv
│   ├── scholar_data_builder.py
│   ├── data_validator.py    # International-specific validation
│   ├── evaluator.py         # JCR quartile/CiteScore/tenure benchmarks
│   ├── xiaohongshu_client.py # Chinese student reviews of foreign advisors
│   ├── heuristics_classifier.py # International anomaly detection (I01-I07)
│   └── missing_reporter.py  # Auto-generate manual lookup guide
├── analysis/                # Shared analysis modules (moved from scripts/ root)
│   ├── text_profiler.py, paper_quality_rubric.py, hybrid_scorer.py
│   ├── stylometry_profiler.py, citation_profiler.py
│   ├── common_heuristics.py  # Shared anomaly rules (C01-C07)
│   └── review_aggregator.py  # Multi-source review merging (domestic + xiaohongshu + RMP)
├── network/                 # Corruption network / relationship graph (moved from scripts/ root)
│   ├── network_visualizer.py, timeline_weaver.py, grant_linker.py
│   ├── negative_space_analyzer.py, investigation_retrospector.py
├── report/                  # Report generation (moved from scripts/ root)
│   ├── report_prompt_optimizer.py
│   ├── report_template.md   # Domestic report template
│   └── international_template.md # International report template (NEW)
├── cross_border/            # Cross-border (海归) scholar investigation (NEW)
│   ├── merger.py            # Merge domestic + international data
│   └── validator.py         # Cross-border consistency checks
├── schema/                  # JSON Schema definitions
│   ├── scholar_data.schema.json
│   └── international_scholar.schema.json (NEW)
├── investigate.py           # CLI orchestrator (retains original location)
├── investigate_visual.py    # Rich terminal visualization wrapper + smart-step auto-advance
├── md_to_pdf.py             # Markdown report → styled PDF with auto-generated charts
├── chart_generator.py       # Auto-generate radar/pie/heatmap/timeline/network charts from Markdown annotations
├── config.template.yaml     # Enhanced with international_sources section
├── scholar_profile_matcher.py    # Basic profile similarity matching (v1)
├── scholar_profile_matcher_v2.py # Enhanced matching: 17-dim feature vectors + risk profiling
├── benchmark_engine.py           # Discipline benchmark DB engine: 5-layer anomaly scoring
└── benchmark_demo.py             # Demo script: init → import → baseline → batch calculation
```

**Key design decisions**:
- **No black-box web crawling** against paywalled academic databases.
- **Graceful degradation**: if a script fails, it surfaces the error to the human instead of fabricating data.
- **Evidence chain**: every automated analysis links back to the original human-provided file or manually verified source.

### Available Tools

| Tool | Location | Purpose | When to Use |
|:---|:---|:---|:---|
| Tool | Location | Purpose | When to Use |
|:---|:---|:---|:---|
| `config.template.yaml` | `scripts/` | Investigation configuration (domestic + international) | Before starting any case |
| `case_manager.py` | `scripts/core/` | Case registry & ID generation (`AD-YYYY-MM-DD-NNN`) | Right after client provides 甲方 name; auto-dedup same-day cases |
| `db.py` | `scripts/core/` | SQLite per-case database (9 tables, `+investigation_type` column) | After `investigate.py init` or manual JSON import |
| `data_importer.py` | `scripts/domestic/` | Bulk import CNKI/Wanfang/WoS exports with deduplication | **Domestic only**: After manual database searches |
| `data_validator.py` | `scripts/domestic/` / `scripts/international/` | JSON schema & logic validation. v2.0 adds `_version` and `peer_cohort` field validation. | Before LLM report generation (track-specific) |
| `text_profiler.py` | `scripts/analysis/` | PDF / Markdown / text monograph/dissertation analysis. v2.0 adds `paper_type_classification` for auto-detecting academic_paper / review / commentary / non_academic. | After manually acquiring book/thesis PDFs |
| `network_visualizer.py` | `scripts/network/` | Interactive D3.js relationship network graph | After `relationship_network` fields are populated |
| `watermark.py` | `scripts/core/` | Invisible zero-width watermark embed/extract | Before delivering final report |
| `report_template.md` | `scripts/report/` | **Domestic** report template (CSSCI/CSSCD-based) | Feed to LLM for domestic report |
| `international_template.md` | `scripts/report/` | **International** report template (JCR Q/CiteScore/tenure-based) | Feed to LLM for international report |
| `wechat_search.py` | `scripts/domestic/` | Search WeChat articles as supplementary leads | **Domestic only**: informal rumors, book promos |
| `xiaohongshu_client.py` | `scripts/international/` | Scrape Xiaohongshu for Chinese student reviews of foreign advisors | **International only**: first-hand student experiences |
| `data_fetcher.py` | `scripts/international/` | Auto-fetch from OpenAlex/ORCID/S2/GS/PubPeer/RW/arXiv | **International only**: free API data collection |
| `evaluator.py` | `scripts/international/` | JCR quartile / CiteScore / tenure benchmark evaluation | **International only**: journal quality & tenure assessment |
| `heuristics_classifier.py` | `scripts/international/` | Detect predatory journals, paper mills, citation cartels | **International only**: anomaly detection |
| `missing_reporter.py` | `scripts/international/` | Auto-generate "what's missing + where to look" guide | **International only**: after API fetching, before manual supplement |
| `研学网导师评价表.xlsx` | `_private/` | **结构化导师评价数据库**（7.5万+条评价）。调查学生对导师的评价时，**必须优先查询此表**，再辅以小红书/知乎等非结构化来源。表内含14个维度评价、可信度评分、可转化为 investigation_leads。 | 任何时候需要了解学生的真实评价反馈 |
| `review_matcher.py` | `scripts/domestic/` | 将研学网评价表的匹配结果转化为结构化 investigation_leads | After matching 研学网 评价 |
| `scholar_data_builder.py` | `scripts/domestic/` / `scripts/international/` | Builds unified `scholar_data.json` from config + script outputs. v2.0 adds `_version` (data collection round tracking) and `peer_cohort` from config. | After all script outputs are available |
| `review_aggregator.py` | `scripts/analysis/` | Merge domestic reviews + xiaohongshu + RateMyProfessors | When multiple review sources available |
| `cross_border/merger.py` | `scripts/cross_border/` | Merge domestic + international scholar_data for 海归 scholars | When scholar has dual affiliations (China + abroad) |
| `investigate.py` | `scripts/` | CLI orchestrator with `--type domestic|international|cross_border` | Throughout the investigation as entry point |
| `investigate_visual.py` | `scripts/` | Rich terminal visualization wrapper: colored phase panels, live subprocess output, interactive prompts, ASCII progress bars. Includes `smart-step` for condition-checked auto-advance with human confirmation. | Use when you want a visual terminal experience; use `smart-step` to let the system check completion conditions and ask before auto-advancing |
| `md_to_pdf.py` | `scripts/` | Convert Markdown investigation report to styled PDF (A4, cover page, TOC, headers/footers). Auto-generates charts from `<!--chart:...-->` annotations via `chart_generator.py` | After `generate` produces the final Markdown report; run with `--pdf` flag |
| `chart_generator.py` | `scripts/` | Auto-generate matplotlib charts: radar (6-dim quality), pie (authorship structure), heatmap (risk matrix), timeline (event sequence), network (mentor-student-collaboration) | Called by `md_to_pdf.py` when chart annotations are detected in Markdown |
| `scholar_profile_matcher_v2.py` | `scripts/` | **Profile similarity + misconduct pattern matching** (v2.0). Compares target scholar against 46-case database (20 normal + 24 confirmed_misconduct + 2 suspicious) using 17-dim feature vectors + prefilter metrics | **After** Step 3 quality assessment + Step 5 anomaly detection: benchmark target against known cases |
| `benchmark_engine.py` | `scripts/` | **Discipline benchmark database engine** (v1.0). 5-layer architecture (discipline/journal/researcher/rule/case-link). Calculates deviation scores (Z-score / lognormal / t-distribution), anomaly probabilities, confidence intervals, and composite risk scores across three comparison modes (individual / peer_group / global) | **Step 5**: after collecting structured metrics (h-index, avg papers, coauthor count, review days) for quantitative anomaly detection |
| `benchmark_demo.py` | `scripts/` | **One-command demo**: initializes SQLite DB, imports 46-case profile DB, creates discipline baselines, runs batch anomaly calculation, outputs Top-N report + JSON export | **Development / validation**: verify benchmark engine behavior against existing cases |
| `kimi-webbridge` | Browser automation skill | Control user's real browser for anti-bot sites | When `xiaohongshu_client.py` / `wechat_search.py` fail due to anti-bot; or CNKI/Xiaohongshu require live session |

> **Note on `kimi-webbridge`**: For platforms with strict anti-bot measures (e.g., 小红书, 中国知网), the built-in `fetch` tool or headless scripts are often blocked. In these cases, invoke the `kimi-webbridge` skill to drive the user's real browser directly. It navigates, clicks, fills forms, and extracts content using the user's actual login sessions and IP reputation, bypassing most bot detection. Typical workflow: `navigate` → `snapshot` → `click` / `evaluate` → `snapshot` → read content. React-based custom inputs may require `evaluate` with manual DOM manipulation rather than `fill`.

### 7-Step Framework → Tool Mapping

### 7-Step Framework → Tool Mapping (Domestic Track)

| Step | Primary Actor | Supporting Tool | Output |
|:---|:---:|:---|:---|
| 0. Case Registry | Human (tell 甲方 name) | `core/case_manager.py` | Unique case ID (`AD-YYYY-MM-DD-NNN`) |
| 1. Basic Profile | Human + LLM | `config.template.yaml`, `investigate.py init` | Structured identity JSON + SQLite DB |
| 2. Output Quantity | Human (manual DB search) | `domestic/data_importer.py`, `domestic/data_validator.py` | CLAIMED vs. VERIFIED table, deduplicated paper list |
| 3. Quality Assessment | LLM | `analysis/text_profiler.py` + `stylometry_profiler.py` | Term counts, originality markers, reference stats, paper type classification + stylometric similarity matrix & heatmap |
| 4. Relationship Network | LLM + Human | `network/network_visualizer.py` | Collaboration graph + interactive HTML visualization |
| 5. Anomaly Detection | LLM | `domestic/data_validator.py` | Flagged inconsistencies with confidence scores |
| 6. Multi-Source Validation | Human + `domestic/wechat_search.py` | `domestic/data_validator.py` | Evidence checklist verification; WeChat articles as rumor leads |
| 7. Report Generation | LLM | `report/report_template.md` | Final Markdown report |
| 8. Delivery Protection | Human | `core/watermark.py` | Watermarked report + hash manifest |

### International Track Workflow

For **foreign graduate advisors / international scholars**, use the **International Track** with different tools and evaluation criteria:

| Step | Primary Actor | Supporting Tool | Output |
|:---|:---:|:---|:---|
| 0. Case Registry | Human | `core/case_manager.py` | Unique case ID |
| 1. Init | Human | `investigate.py init --type international` | Config + DB with `investigation_type=international` |
| 2. Auto-Fetch | Scripts (free APIs) | `international/data_fetcher.py` | `auto_fetched.json` (papers, metrics, collaborators from OpenAlex/S2/ORCID) |
| 3. Student Reviews | Scripts | `international/xiaohongshu_client.py` | Xiaohongshu reviews with sentiment/dimension extraction |
| 4. Manual Supplement | Human | `international/missing_reporter.py` | Markdown guide: what's missing + where to look |
| 5. Build | Scripts | `international/scholar_data_builder.py` | `scholar_data.json` conforming to `international_scholar.schema.json` |
| 6. Evaluate | Scripts | `international/evaluator.py` | JCR quartile table, tenure benchmark, grant portfolio assessment |
| 7. Heuristics | Scripts | `international/heuristics_classifier.py` | Flags: I01 predatory journal, I02 paper mill, I04 citation cartel, etc. |
| 8. Validate | Scripts | `international/data_validator.py` | Schema + logic validation |
| 9. Report Generation | LLM | `report/international_template.md` | International report (tenure clock, OA cost, visa/salary reviews) |
| 10. Delivery | Human | `core/watermark.py` | Watermarked report |

**Key CLI commands for international track:**
```bash
python investigate.py init --type international --config ./config.yaml
python investigate.py international-fetch --config ./config.yaml
python investigate.py international-build --config ./config.yaml --xiaohongshu ./data/xhs_reviews.json
python investigate.py missing-report --scholar-data ./scholar_data.json
python investigate.py review-aggregate --domestic ./reviews.json --xiaohongshu ./xhs.json --output ./merged_reviews.json
```

See `scripts/README.md` for detailed usage instructions.

### 显式工具索引与案件检查清单

为避免工具路径混乱和流程遗漏，系统提供两个配套文件：

| 文件 | 路径 | 用途 |
|:---|:---|:---|
| **显式工具索引** | `scripts/TOOLS_INDEX.md` | 列出所有脚本的真实路径（排除根目录 shim），按调查步骤分类，附带输入/输出说明和常见路径陷阱 |
| **案件检查清单模板** | `scripts/templates/CHECKLIST.md` | 每个案件初始化时必须复制到案件根目录，逐条勾选确保不跳过关键步骤 |

**强制要求**：
1. 每次启动新调查，`investigate.py init` 完成后必须将 `scripts/templates/CHECKLIST.md` 复制到案件目录，并命名为 `CHECKLIST.md`。
2. 执行任何脚本前，先在 `scripts/TOOLS_INDEX.md` 中确认该工具的真实路径。**`scripts/` 根目录下绝大多数 <500 字节的 `.py` 文件是兼容性 shim，真实实现位于 `analysis/`、`domestic/`、`international/`、`network/`、`report/` 等子目录中。**
3. Step 3 质量评估中，**每篇 PDF 必须依次经过 `analysis/text_profiler.py` → `analysis/paper_quality_rubric.py` 完整流程**，禁止跳过六维评分直接输出主观质量判断。

---

## 7-Step Investigation Framework

### Step 1: Basic Profile Establishment

**Goal**: Create foundational identity and timeline.

**Information to Collect**:
| Category | Sources | Key Checks |
|:---|:---|:---|
| Name, Institution, Title | Official website, CV, institutional directory | Verify current position accuracy |
| Education Background | Degree certificates, university records, dissertation databases | Check graduation years, advisors |
| Career Timeline | Institutional profiles, promotion records | Map all position changes with dates |
| Current Role | Department pages, administrative listings | Note any leadership titles |

**Key Action**: Create **chronological timeline** marking all degree acquisitions, position appointments, and major publications.

#### Step 1 Evidence Standards
- **Every date and position must be traceable to a specific source** (institutional webpage URL, CV PDF page number, or official directory screenshot).
- **Distinguish fact from inference**: mark uncertain dates with "推断" or "待核实".
- **Do not rely on a single self-reported source** (e.g., Baidu Baike alone). Cross-check with at least one independent institutional record.
- **Institutional bios are self-reported**: treat them as reference only. Verify recent activity (last 3 years) through independent publication and funding databases.

### Step 2: Academic Output Quantity Verification

**Goal**: Verify claimed vs. actual academic production.

**Sources**: CNKI, Wanfang, Web of Science, institutional repositories.

**Critical Comparison**: Create CLAIMED vs. VERIFIED table.

**Red Flags**: >20% discrepancy, unverifiable items, conference presentations counted as peer-reviewed publications.

#### Practical Paper Evaluation Guide

When manually searching academic databases (CNKI, Wanfang, Web of Science), search for `"scholar name" + "institution"` and evaluate the results across **5 dimensions**:

| Dimension | What to Check | Red Flags |
|:---|:---|:---|
| **1. Research Direction** | Does the scholar have a sustained research focus? Is there thematic coherence across publications? | Frequent topic jumping with no cumulative depth; work unrelated to claimed expertise |
| **2. Publication Volume & Frequency** | Count papers from the last 3–5 years. Is there at least 1 peer-reviewed paper per year? | **Two consecutive years with zero output** suggests research stagnation or administrative overloading |
| **3. Journal Quality** | **Domestic**: CSSCI (C刊), Peking University Core (北大核心). **International**: JCR Quartile (Q1–Q4), CiteScore, SJR. | Heavy reliance on **paid open-access journals** or low-tier general journals (普刊) without peer review rigor |
| **4. Authorship Position** | STEM:导师 routinely occupying first authorship on lab papers is a serious concern. HSS: doctoral students should be first author on their own dissertations-derived work. |导师 as first author on most papers in STEM; student **not first author** on dissertation-based chapters in HSS |
| **5. Content Differentiation** | Do recent papers present genuinely new arguments, data, or methods? Or do they recycle the same framework with superficial cosmetic changes? | **"换汤不换药"** (same soup, different bowl): identical arguments packaged across multiple outlets; OR extreme **topic inconsistency** with no logical progression |

**Note on applicability**: The authorship-position rules above originated in doctoral-supervisor evaluation contexts. When investigating **established senior scholars**, adjust expectations accordingly: senior researchers may legitimately appear as corresponding or last author, but a pattern of **never allowing junior colleagues first authorship** remains a red flag for exploitative credit practices.

#### Step 2 Evidence Standards
- **Every numeric claim must quote the exact source**: database name, search date, query string, and result count. Example: "CNKI, 2026-04-14, author='SCHOLAR_NAME' AND institution='INSTITUTION_NAME', 39 results".
- **For any discrepancy >10%**, preserve the original screenshot or export file as evidence.
- **Distinguish "claimed" from "verified"** rigorously. Self-claimed numbers from lecture slides or personal intros must be tagged as **声称** and never presented as established fact.
- **No finding that could damage reputation may rest on a single source.** Minimum 2 independent databases or records.

#### Practical Manual Investigation Techniques

Beyond raw database searches, the following low-tech but high-yield methods should be performed whenever the scholar has a student supervision record:

| Technique | How to Do It | What It Reveals |
|:---|:---|:---|
| **Student graduation audit** | Search CNKI dissertations for the scholar's advisees. Check degree year against program length (e.g., MA 3 years, direct PhD 5 years). | Systematic **delay in graduation** is one of the strongest signals of poor mentorship or exploitative lab culture. |
| **First-paper timeline** | For each advisee, identify the time from enrollment to first co-authored paper and the journal quality of that paper. | Delays >2 years for the first publication, or first papers appearing only in low-tier paid journals, suggest inadequate guidance. |
| **Enrollment gap analysis** | Check the scholar's admission roster over the past 5–10 years. Are there multi-year gaps with zero new students? | **Enrollment断档** often means previous students actively warned applicants away. |
| **Student trajectory mapping** | Search for former students on LinkedIn, ResearchGate, or institutional alumni pages. Where did they end up? | A pattern of students leaving academia entirely with no publications is a negative signal. |
| **Peer consultation** | If possible, speak with current or former students **privately** (not in open lab settings). | First-hand accounts of authorship theft, excessive administrative burdens, or funding shortages. |

### Step 3: Academic Quality Assessment

本步骤采用国际主流出版机构（Nature、Springer、ACM/IEEE）的同行评审标准，建立六维论文质量评估体系。评估结果使用与顶刊审稿人一致的 A/B+/B/C/D 五级量表输出。

#### 3.1 六维评估框架

| 维度 | 权重 | 核心问题（Nature/Springer/ACM 标准） | 人工审查要点 | 脚本辅助 |
|:---|:---:|:---|:---|:---:|
| **原创性与重要性** | 25% | 论文是否提出了足以影响该领域思考方向的新理解、新方法或新证据？是否值得在高级别期刊发表而非仅发表于专业期刊？ | 核心论点的新颖度、与已有研究的区分度、选题的战略价值 | `paper_quality_rubric.py`  originality_significance |
| **技术严谨性** | 20% | 研究方法是否存在应禁止发表的致命缺陷（fatal flaws）？方法选择是否适合研究问题？ | 方法论匹配度、逻辑跳跃、因果推断是否过度、是否存在无法补救的硬伤 | `paper_quality_rubric.py` validity_rigor |
| **数据与证据质量** | 20% | 数据质量如何？方法透明度和可重复性是否充分？统计处理是否恰当？ | 数据来源说明、样本/案例选择合理性、稳健性检验、误差条和概率值描述 | `paper_quality_rubric.py` data_evidence |
| **逻辑结构与结论稳健性** | 15% | 结构是否清晰？结论是否与数据匹配？解释是否稳健、有效、可靠？ | 章节逻辑、假设-证据-结论链条、对反向证据的处理 | `paper_quality_rubric.py` structure_conclusions |
| **文献综述与引用规范** | 10% | 是否恰当引用前人工作？是否存在过度自引或遗漏关键文献？ | 经典文献覆盖度、对立观点是否被引用、自引率是否合理 | `paper_quality_rubric.py` literature_engagement |
| **表达清晰度与可及性** | 10% | 摘要是否清晰可及？写作是否专业？图表是否自明？ | 摘要准确性、语言规范、术语一致性、图表说明完整性 | `paper_quality_rubric.py` clarity_accessibility |

#### 3.2 质量评级量表

基于国际同行评审实践（参考浙江大学学报英文版国际审稿数据分布），采用五级评级：

| 评级 | 分数区间 | 英文对应 | 含义 |
|:---:|:---:|:---:|:---|
| **A** | ≥85 | Excellent | 重大进展，具备 Nature/Science 级别可见度的开创性工作 |
| **B+** | 75-84 | Good | 扎实可靠，仅需 minor revisions 即可发表 |
| **B** | 65-74 | Moderate/Acceptable | 经修改后可在专业期刊发表，但缺乏顶刊冲击力 |
| **C** | 55-64 | Poor/Weak | 存在重大疑虑，需 extensive revision 或建议拒稿 |
| **D** | <55 | Unacceptable | 存在致命缺陷（fatal flaws），不应发表 |

**引用分数时的重要说明**：
- `paper_quality_rubric.py` 输出的分数是**基于文本特征和人工观察的推断分**，不能等同于真实审稿人的评分。
- 单一论文的评分应放在学者整体产出曲线中理解：一篇 B 不等于学者能力差，但多篇 C/D 或持续无 A/B+ 则反映学术产出质量存在结构性问题。

#### 3.3 脚本工具链：`paper_quality_rubric.py`

在运行 `text_profiler.py` 提取 PDF / Markdown / 文本的基础统计后，可进一步运行质量评分脚本：

```bash
# 基础模式：仅从 text_profiler 输出推断
python analysis/text_profiler.py --input ./pdfs/paper.pdf --output ./data/paper_profile.json
python analysis/paper_quality_rubric.py --profile ./data/paper_profile.json --output ./data/paper_quality.json

# 增强模式：叠加人工观察（推荐）
python analysis/text_profiler.py --input ./pdfs/paper.pdf --output ./data/paper_profile.json
python analysis/paper_quality_rubric.py \
  --profile ./data/paper_profile.json \
  --observations ./data/paper_observations.json \
  --output ./data/paper_quality.json
```

> ⚠️ **路径警告**：`scripts/` 根目录的 `text_profiler.py` 和 `paper_quality_rubric.py` 均为 <500 字节的兼容性 shim。真实实现位于 `scripts/analysis/` 子目录。运行前请查阅 `scripts/TOOLS_INDEX.md` 确认正确路径。

##### 3.3.1 混合评分工作流（hybrid_scorer.py）

当需要对多篇论文批量评分时，使用 **脚本+LLM 混合评分** 工作流。脚本负责提取基础统计和文本节选，LLM 负责判断作品类型、署名权重和学科相关性，最后由脚本批量计算并输出排名表。

```bash
# 步骤1：准备 review pack（纯脚本）
python scripts/hybrid_scorer.py prepare -i ./pdfs -o ./data/hybrid_scores

# 步骤2：LLM 审阅 llm_review_request.md 后输出 llm_observations_batch.json

# 步骤3：应用观察并生成最终排名表
python scripts/hybrid_scorer.py apply -i ./pdfs -o ./data/hybrid_scores
```

该工作流可通过 `investigate.py` 直接调用：

```bash
python investigate.py score -i ./pdfs -o ./data/hybrid_scores
python investigate.py score -i ./pdfs -o ./data/hybrid_scores --apply
```

##### 3.3.2 `observations.json` 字段说明

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| `originality_score` | int | 人工/LLM 对原创性的 0-100 评分，脚本会将其与文本标记密度加权融合 |
| `has_fatal_flaw` | bool | 是否存在致命缺陷（如方法根本错误、数据伪造嫌疑） |
| `validity_concerns` | list[str] | 具体有效性疑点列表 |
| `data_reproducibility` | string | `high`/`medium`/`low`/`unknown`/`na` |
| `conclusion_robustness` | string | `high`/`medium`/`low` |
| `statistical_rigor` | string | `high`/`medium`/`low`/`na`（不适用） |
| `structure_score` | int | **可选** 0-100，直接覆盖「逻辑结构与结论稳健性」维度得分 |
| `structure_quality` | string | `high`/`medium`/`low`，在无直接覆盖时微调结构分 |
| `paper_type` | string | `dissertation` / `monograph` / `journal_article` / `review` / `report` / `commentary` / `dialogue` (human-assigned via observations). Auto-detect also available via `text_profiler.py` `paper_type_classification` output. |
| `authorship_role` | string | `solo` / `first_author` / `coauthor` / `group_member` |
| `llm_reasoning` | string | 评分依据简要说明（仅用于可追溯） |

#### 3.4 扩展审查方法：PDF 表格提取与统计一致性审查（LLM 自选）

除了 `text_profiler.py` 和 `paper_quality_rubric.py` 提供的文本特征分析外，当现场环境具备可直接读取 PDF 的编程能力（如 `pdfplumber`、`PyPDF2`、`camelot` 等库可用）时，LLM **可自行选择调用更科学、更契合具体论文类型的审查方法**。这些方法尤其适用于包含实验数据表格、统计描述和量化结果的医学/生命科学/工程类论文。

**推荐方法**：

| 方法 | 适用场景 | 核心检查点 | 工具示例 |
|:---|:---|:---|:---|
| **PDF 表格提取 + 统计一致性审查** | 论文内含 Mean±SD、P 值、样本量（n）、基因型频率、时间序列等量化表格 | 1. P 值与样本量/效应量是否匹配<br>2. 均值与标准差是否出现不可能组合（如 Mean≠0 但 SD=0）<br>3. 分组人数前后是否一致<br>4. 基因型频率是否偏离 Hardy-Weinberg 平衡<br>5. 生物学趋势是否符合已知规律 | `pdfplumber`, `tabula-py`, `camelot` |
| **图像重复比对** | 怀疑存在图片拼接、重复使用 | 在不同论文间比对电泳条带、免疫组化、显微镜照片的相似度 | `imagehash`, `PIL`, 手动目视复核 |
| **原始数据可用性审查** | 论文声称数据公开但无法访问 | 补充材料链接有效性、数据库登录号（GEO/PRJNA/DRYAD 等）可解析性 | `requests`, `BeautifulSoup` |

**方法选择原则**：
- **按需调用**：不必对每一篇论文都执行全套扩展审查，优先对第一作者/通信作者的核心论文、或存在初步可疑信号的论文进行深入审查。
- **结果应与六维评分相互印证**：例如，若统计一致性审查发现某篇论文存在 P 值与样本量严重矛盾，则该论文的「技术严谨性」和「数据与证据质量」维度应相应降级。
- **记录审查过程**：报告中应明确说明使用了哪种扩展方法、审查了多少篇论文、发现了哪些异常（或无异常），以及所使用的 Python 库名称。

> **案例参考**：在一次对某神经内科研究者 50 篇 PDF 论文的调查中，调查者使用 `pdfplumber` 提取了 9 篇核心论文的统计表格，并执行了 n=6 动物实验的 t 值反推、640 人样本的 HWE 检验、CV（变异系数）审查等。最终 9 篇论文的造假风险评估平均分为 8.2/10（低风险），有效缓解了"数据造假"的嫌疑，同时发现研究者独立学术能力的天花板约为 B 级（六维评分平均分 71.00）。

#### 3.5 特殊审查：伦理合规性（Ethical Compliance）

Springer 和 ACM 的出版伦理指南将以下问题视为**零容忍红线**，需在质量评估中单独列出：

| 审查项 | 红旗信号 | 证据来源 |
|:---|:---|:---|
| **一稿多投/一稿多发** | 同一内容同时投稿多个期刊，或学位论文拆分过度（salami slicing） | 时间戳比对、学位论文与期刊论文重合度分析 |
| **数据/图片操纵** | 无法提供原始数据、图片在不同论文中重复出现、统计数值与样本量矛盾 | 原始数据请求记录、图片反查 |
| **署名权问题** | 未满足 ICMJE 四条署名标准（贡献度、起草/修改、批准、负责）即挂名 | 作者贡献声明缺失、与致谢部分矛盾 |
| **利益冲突未披露** | 论文存在企业资助或持股关联但未声明 | 工商信息、基金资助数据库 |
| **抄袭/自我抄袭** | 查重率过高、大段未标注引用、自我重复发表 | 查重报告、原文对比 |

#### Step 3 Evidence Standards
- **质量判断必须引用具体作品**：每篇被评估论文需标注标题、年份、期刊、页码范围。避免"所有论文质量都很低"这类笼统表述。
- **抄袭或 salami slicing 指控必须提供逐字/逐段对比**及来源文献。禁止仅凭怀疑指控学术不端。
- **期刊级别声明必须引用权威索引**（CSSCI、北大核心、SCI/SSCI 分区、中科院分区、官方期刊评价目录）并标注查询日期。
- **任何涉及主观解释的质量评估**（如"理论深度"）必须附带评估者的推理链条和依据。
- **评级量表使用规范**：报告中出现 A/B+/B/C/D 评级的，必须同时说明该评级对应的具体缺陷或优点，禁止只给分数不给理由。

### Step 4: Relationship Network & Resource Dependencies

**Investigation Areas**:
- Advisor-Mentee Relationships (advisor's institutional power, timeline overlap)
- Collaboration Patterns (frequent collaboration with superiors, author position trends)
- Institutional Dependencies (home institution bias, editorial board connections)
- **Funding & Resource Base** (active grants, lab equipment, student stipends)
- **Structured Alumni Reviews** (large-scale anonymous student evaluations)

**Red Flags**: All top-tier publications co-authored with leaders, consistently middle/last position, sudden surge with advisor's promotion, no verifiable active grants in the last 3 years, consistently low ratings or repeated severe allegations in structured review databases.

#### Funding Resource Verification

For scholars in STEM and natural sciences, active grant support is a critical proxy for research viability.

| Source | What to Search | Signal Interpretation |
|:---|:---|:---|
| **NSFC (国家自然科学基金)** | Search the scholar's name on the [NSFC Big-Data Portal](https://kd.nsfc.cn) or the official grant system | Zero active projects in the last 3 years suggests limited funding for equipment, reagents, or student support |
| **Provincial/Ministry grants** | Provincial Natural Science Foundation, Ministry of Education projects | Supplementary funding stream; absence is a yellow flag if NSFC is also empty |
| **Corporate/横向 projects** | Company contracts, consulting records | May explain high output but also signals "company boss" or "project entrepreneur" archetypes |

**Important**: Detailed researcher profiles on the NSFC portal require login. The investigator should perform this search manually. Do not attempt automated credential-based access.

#### Structured Anonymous Review Database (e.g., baoyanren.com exports)

If the investigator has access to a structured student-review database, use `review_matcher.py` to query it before manual database searches. This converts subjective alumni experiences into **verifiable investigation leads**.

**What `review_matcher.py` does**:
- Matches scholar by name + school (+ optional college)
- Aggregates rating statistics (average, count, distribution)
- Parses **14 dimension-specific comments**:
  - *Original 7*: 导师辨识特征, 学术水平, 科研经费, 学生补助, 师生关系, 工作时间, 学生前途
  - *New 7*: 自证认识导师, 毕业要求与论文署名, 组会与指导方式, 人品与性格, 实习与就业支持, 推荐意愿, 实验室氛围
- Runs **sentiment polarity analysis** per dimension (positive / neutral / negative)
- Computes **credibility scores** per review based on self-certification, length, dimension coverage, and concrete-detail density
- Generates `investigation_leads` mapped to concrete verification actions

**Lead-to-Verification Mapping**:

| Lead Type | Typical Keywords | Verification Action | Severity |
|:---|:---|:---|:---:|
| Delayed graduation | 延毕, 卡毕业, 不让毕业 | Cross-check CNKI dissertations for actual graduation years vs. standard program length | high |
| Authorship extraction | 抢一作, 导师一作, 抢论文 | Count student-first vs. mentor-first authorships in recent papers | high |
| Internship banned | 不允许实习, 不让实习, 禁止实习 | Trace alumni career trajectories on LinkedIn/ResearchGate | medium |
| Corporate capture | 横向, 为公司, 给企业, 项目多 | Check corporate co-op projects and thesis topics for over-commercialization | medium |
| High workload | 打卡, 996, 加班, 晚上, 周末 | Private peer consultation to verify work hours and attendance policies | medium |
| Funding shortage | 补助少, 不发工资, 经费少 | NSFC active-project count vs. lab size | medium |
| Absent shepherd | 放养, 不管学生, 见不到人 | Cross-check with recent authorship patterns (corresponding-author rate, output continuity) | medium |
| Toxic culture | 骂人, PUA, 压榨, 威胁 | Increase weight of peer consultation; verify specific incidents | high |
| Graduation barrier | 毕业要求, 发文要求, 必须发, 卡论文 | Compare stated graduation requirements against official program regulations | medium |

**Evidence standard**: Treat structured review databases as **hypothesis generators** (⭐⭐⭐☆☆). Every specific allegation extracted from a review must be cross-checked against a verifiable public record before inclusion in the main findings.

#### Scholar/Advisor Archetype Signals

When evaluating relationship networks and resource dependencies, it can be useful to map observed behavior patterns to common archetypes. The following taxonomy (adapted from doctoral-advisor selection research) provides investigative heuristics:

| Archetype | Observable Signals | Investigative Relevance |
|:---|:---|:---|
| **Company Boss** | Lab run as a hierarchy; heavy横向项目 load; students treated as employees; publications secondary to deliverables | May explain **low academic output** despite large team size; risk of student exploitation |
| **Absent Shepherd** | Rarely meets students; no fixed group meetings; students left to figure out projects alone | Explains **erratic publication quality** or **topic inconsistency** in student work |
| **Push/Taskmaster** | Frequent meetings; high output demands; rapid turnaround expectations | Can produce volume, but may correlate with **high turnover** or **mental-health-related departures** |
| **Benevolent Patron** | Genuinely supportive; protects student authorship; provides introductions and resources | The positive counter-example; if present, explains **stable student outcomes** |
| **Rent-Seeking Landlord** | Claims first authorship on student-derived work; assigns non-academic chores; controls funding tightly | Directly correlates with **authorship exploitation** and **credential inflation** patterns |
| **Figurehead Elder** | High title (academician/changjiang/jieqing) but minimal direct contact; daily supervision delegated | Students' actual intellectual contribution may be **appropriated by middle-layer proxies**. Prestigious titles do **not** guarantee available mentorship time. |
| **Project Entrepreneur** | Runs companies or extensive consulting; diverts student labor to commercial ventures | Explains **delayed graduation** and **thesis topics unrelated to scholar's claimed research** |

**Important**: These are **pattern descriptors**, not clinical diagnoses. A single trait does not prove misconduct; clusters of traits strengthen inferential confidence.

#### Step 4 Evidence Standards
- **Every relationship claim must specify the evidence type**: co-authorship on a specific paper (cite title and year), shared project grant number, or institutional appointment record.
- **Correlation is not causation**: if an advisor held editorial power during a student's publication surge, note the temporal overlap precisely but do not assert direct manipulation without additional evidence (e.g., correspondence, witness testimony).
- **Map all co-authors by full name and institutional affiliation** at the time of publication to avoid false matches.
- Flag "institutional bias" claims with concrete examples (e.g., "7 of 8 top-tier papers published in journals where the advisor served on the editorial board").

#### Discipline-Specific Authorship Norms

| Dimension | STEM / Natural Sciences | Humanities / Social Sciences |
|:---|:---|:---|
| Mentor first authorship | **Strong red flag** on lab papers;导师 should typically be last or corresponding author | Less common but still suspect on student dissertation chapters |
| Student first authorship | Expected on thesis-derived experimental work | **Required** on chapters derived from the student's own dissertation |
| Group size correlation | Large groups (>20) may indicate corporate/company-boss culture | Small groups (1–5) are normal; excessive isolation is the concern |
| Funding transparency | Equipment and reagent costs should be covered; student stipends should be clear | Conference travel and book purchases are the main material supports |

### Step 5: Anomaly Detection & Deep Investigation

**Focus Areas**:
- Promotion Timeline Analysis (compare to peer cohort)
- Publication Time Clustering (pre-promotion surges, post-advisor spikes)
- Credential Verification (international degrees, visiting positions, awards)

#### Extended Red Flag Catalog

Beyond the quantity and relationship-network red flags above, watch for the following concrete warning signals:

| Red Flag | What to Look For | Typical Pattern |
|:---|:---|:---|
| **Directional Chaos** | Scholar's publications span unrelated subfields with no cumulative thread; or advises students on wildly different topics | Absent-shepherd or figurehead-elder archetype; scholar lacks actual expertise in claimed areas |
| **Enrollment Gap** | No new graduate students admitted for 2+ years in recent history | Previous cohorts actively warned applicants away |
| **Systematic Delay** | Multiple advisees exceed standard degree duration (MA >3 years, direct PhD >5–6 years) | Push/taskmaster or rent-seeking-landlord culture; may also indicate funding manipulation |
| **Corporate Capture** | Student theses address commercial products; scholar runs active companies alongside academic post | Project-entrepreneur archetype; academic output is secondary |
| **Authorship Extraction** | Students have zero or few first-author papers despite multi-year enrollment;导师 dominates first authorship | Rent-seeking-landlord pattern; correlates with dependency-pattern cases |
| **Quality Collapse** | Early career shows solid journals; recent 5 years shift predominantly to low-tier/paid-open-access venues | Figurehead-elder or company-boss pattern; has stopped doing rigorous peer-reviewed research |
| **Mentorship Vacuum** | No verifiable student mentorship record despite holding a professor/b doctoral-supervisor title for many years | May indicate the scholar was promoted on political or networking grounds rather than academic merit |

#### Scholar Profile Database Benchmarking (NEW)

**数据库概况** (`data/scholar_profile_database.csv`)：
- **总计46条记录**：20 normal + 24 confirmed_misconduct + 2 suspicious
- **来源**：23条为实际调查案例（CASE_002、CASE_020、CASE_015、CASE_021等），23条为外部典型案例（某博士、某教授A、某教授B、某教授C、某教授D等，含13个NSFC通报+Tumor Biology批量撤稿+论文工厂模式）
- **字段**：67列，分四大组
  - **身份信息**（14列）：researcher_id, profile_id, name, institution, department, current_title, academic_title, gender, birth_year, career_stage, career_tier, primary_discipline, secondary_disciplines, discipline_id
  - **定量指标**（29列）：h_index, total_citations, num_papers_claimed/verified, first_author_count/ratio, corresponding_author_ratio, coauthor_count/concentration, avg/median_papers_per_year, median_citations_per_paper, self_citation_rate, retraction_count, median/min/max_review_days, funding_hit_rate, total_grants/amount, max_journal_tier, avg_hybrid_score 等
  - **17维不端特征标签**（17列）：feat_data_fabrication ~ feat_supervisor_abuse
  - **状态信息**（7列）：investigation_status, is_confirmed_misconduct, investigation_date, update_date, notes, data_path

**17维不端特征标签**：

| 维度 | 标签代码 | 典型触发场景 |
|:---|:---|:---|
| 数据伪造 | `feat_data_fabrication` | 凭空编造实验数据、BET曲线复制 |
| 数据篡改 | `feat_data_falsification` | 修改数据点、删除异常值、调整统计结果 |
| 图像操纵 | `feat_image_manipulation` | SEM/TEM图像造假、Western Blot重复、裁剪拼接 |
| 抄袭剽窃 | `feat_plagiarism` | 直接复制他人论文段落、多源拼接 |
| 自我抄袭 | `feat_self_plagiarism` | 同一内容未引用重复发表、旧文集结为专著 |
| 翻译抄袭 | `feat_translation_plagiarism` | 整篇翻译外文论文投稿 |
| 代写 | `feat_ghostwriting` | 第三方完成论文写作、买来的署名 |
| 虚假同行评审 | `feat_fake_peer_review` | 伪造评审人邮箱、自己评审自己的论文 |
| 论文工厂 | `feat_paper_mill` | 批量购买论文、模板化写作、中介代投 |
| 数据买卖 | `feat_data_trading` | 购买实验数据而未实际开展实验 |
| 作者身份不端 | `feat_authorship_misconduct` | 权力干预署名、挂名、买卖作者位置 |
| 基金不端 | `feat_fund_misconduct` | 擅自标注他人基金、虚构基金支持 |
| 重复发表 | `feat_duplicate_publication` | 一稿多投、拆分发表、旧文集结 |
| 引用操纵 | `feat_citation_manipulation` | 互引协议、要求引用无关文献 |
| 伦理违规 | `feat_ethical_violation` | 未披露利益冲突、商业利益边界模糊、精神压迫学生 |
| 系统性造假 | `feat_systemic_fraud` | 导师组织批量造假、长期产业链式造假 |
| 导师权力滥用 | `feat_supervisor_abuse` | 禁止学生使用课题组数据、为亲属批量生产论文 |

**比对脚本用法**：

```bash
# 综合比对（前置筛查 + 模式相似度）
python scripts/scholar_profile_matcher_v2.py --name "学者姓名" --top 5 --mode composite

# 风险画像（逐特征维度输出最接近的确认不端案例）
python scripts/scholar_profile_matcher_v2.py --name "学者姓名" --mode risk_profile

# 与confirmed_misconduct案例的专门比对
python scripts/scholar_profile_matcher_v2.py --name "学者姓名" --top 5 --mode misconduct_ranking
```

**解读标准**：
- **模式相似度 > 50%**：与已知不端案例高度相似，需重点审查
- **模式相似度 30–50%**：存在模式重叠，建议深入调查重叠特征维度
- **模式相似度 < 30%**：不端模式不匹配，但不排除未发现的新模式
- **前置筛查相似度高 + 模式相似度 = 0%**：与正常学者基线接近，快速结案

#### 学科基准线数据库 Benchmarking (NEW v1.0)

**五层架构** (`data/benchmark_schema.sql` + `scripts/benchmark_engine.py`)：

| 层级 | 表名 | 作用 | 关键字段 |
|:---|:---|:---|:---|
| Layer 1 | `discipline_benchmarks` | 学科维度基线：某个学科在特定区域/时间段的"正常"统计分布 | median_papers_per_year, mad_papers_per_year, median_h_index, median_review_days, retraction_rate |
| Layer 2 | `journal_benchmarks` | 期刊维度基线：某本期刊的审稿周期、接受率、撤稿率 | impact_factor, median_review_days, acceptance_rate, retraction_rate, country_distribution |
| Layer 3 | `researcher_baseline` | 个体研究者画像：从学者档案库提取的数值化指标 | h_index, avg_papers_per_year, coauthor_concentration, cross_discipline_count, funding_hit_rate |
| Layer 4 | `anomaly_rules` | 异常模式规则：10种可运行的检测规则（A001-A010） | detection_logic, threshold_params, distribution_assumption, weight, severity_level |
| Layer 5 | `case_anomaly_links` | 案例-异常关联：每条触发的规则及其偏离度、概率、置信区间 | deviation_score, anomaly_probability, confidence_interval_lower/upper |

**核心算法**：
- **偏离度计算**：三种比较模式（individual 学科基线 / peer_group 同群 / global 全局）
- **稳健统计量**：中位数 + MAD + IQR，替代均值 + 标准差
- **对数正态分布**：处理右偏学术指标（发文量、h-index）
- **MAD退化防护**：当MAD=0（大量重复值）时，自动fallback到std/IQR
- **异常概率**：双侧检验 P = 2 * (1 - Φ(|Z|))
- **置信区间**：大样本正态近似 + 小样本t分布修正

**10种预设异常规则**（A001-A010）：

| 规则 | 名称 | 检测指标 | 阈值参数 | 严重度 | 权重 |
|:---|:---|:---|:---|:---:|:---:|
| A001 | 超高产 | avg_papers_per_year | z_threshold=1.0, direction=high | 2 | 1.0 |
| A002 | 引用异常 | h_index / median_citations_per_paper | z_threshold=1.0, direction=low | 2 | 1.0 |
| A003 | 合作者高度集中 | coauthor_concentration | z_threshold=1.0, threshold=0.6, direction=high | 2 | 1.0 |
| A004 | 异常快速发表 | median_review_days | z_threshold=1.0, direction=fast | 2 | 1.0 |
| A005 | 撤稿历史 | retraction_count | z_threshold=0.5 | 2 | 1.0 |
| A006 | 跨领域过度延伸 | cross_discipline_count | z_threshold=1.5 | 2 | 0.8 |
| A007 | 一作比例异常 | first_author_ratio | low_threshold=0.1, high_threshold=0.9 | 1 | 0.8 |
| A008 | 基金命中率异常 | funding_hit_rate | z_threshold=1.5 | 2 | 0.8 |
| A009 | 自引率突增 | self_citation_rate | z_threshold=1.5 | 2 | 0.8 |
| A010 | 期刊层级错配 | avg_journal_tier | tier_gap=2 | 1 | 0.6 |

**使用方法**：

```bash
# 初始化数据库 + 导入46条案例 + 创建基线 + 批量计算
python scripts/benchmark_demo.py

# 单独计算某个学者的异常指数
python scripts/benchmark_engine.py --init --import-profiles
python scripts/benchmark_engine.py --calc CASE_001 --report

# 批量计算并导出JSON
python scripts/benchmark_engine.py --init --import-profiles --batch --export data/results.json
```

**风险等级判定**：

| 综合异常指数 | 风险等级 | 建议动作 |
|:---:|:---:|:---|
| < 2.0 | low | 正常范围，无需额外关注 |
| 2.0 - 5.0 | medium | 存在1-2个异常信号，建议关注相关指标 |
| 5.0 - 10.0 | high | 多个异常信号叠加，建议深入调查 |
| > 10.0 | critical | 显著偏离基线，与已知不端模式高度吻合 |

**当前限制与下一步**：
- **数据缺口**：46条案例中仅25条有 `num_papers_verified`，仅1条有 `h_index`，大量数值字段缺失。导致基线样本量小（n=25），分布估计不稳定。
- **学科基线缺失**：38/46条案例的 `department` 字段为空，无法按学科分组建立基线。当前使用全局基线（GLOBAL）作为fallback。
- **阈值已调参**：A001-A004 阈值收紧至 z=1.0（灵敏度提高），A005 降至 z=0.5（只要有撤稿即触发），A006/A008/A009 保持 z=1.5。上述阈值基于小样本调试，正式使用前需根据各学科真实数据重新校准。
- **Phase 1目标**：引入WOS/CNKI/Scopus数据权限后，按3-5个高发学科建立粗基线（样本量n>100），替换当前全局基线。

#### Step 5 Evidence Standards
- **Anomaly claims must include a baseline comparison**: peer cohort data, institutional norms, or national statistics. Example: "Median time to full professor in this institute is 5–8 years; subject has not advanced in 16 years."
- **Publication clustering must show exact dates and statistical justification** (e.g., "3 papers accepted within 6 months prior to promotion review").
- **Profile similarity check (NEW)**: Run `python scripts/scholar_profile_matcher_v2.py --name "学者姓名" --top 5` to benchmark the target against the 46-case database (20 normal + 24 confirmed_misconduct + 2 suspicious). If the top matches are confirmed_misconduct cases with high mode similarity (>30%), flag as high-risk pattern match. If top matches are normal scholars, the target likely falls within baseline range.
- **Credential verification must cite the issuing body**: university registrar, embassy certification, or official award announcement. Unverifiable credentials must be marked **待核实**.
- Every anomaly flagged must be labeled with a **confidence level** (low / medium / high / very high) and the reasoning behind it.

### Step 6: Multi-Source Cross-Validation

**Source Hierarchy**:
| Tier | Source | Reliability |
|:---:|:---|:---:|
| 1 | Official institutional records | ⭐⭐⭐⭐⭐ |
| 2 | Academic databases | ⭐⭐⭐⭐⭐ |
| 3 | Third-party evaluations | ⭐⭐⭐⭐☆ |
| 4 | Large-scale structured review databases | ⭐⭐⭐☆☆ |
| 5 | Media reports | ⭐⭐⭐☆☆ |
| 6 | Social media | ⭐⭐☆☆☆ |
| 7 | Anonymous review sites (scattered posts) | ⭐☆☆☆☆ |

**Protocol**: Minimum 2 independent sources for each major finding.

#### Public Reputation Collection (Optional)

When the investigation aims to assess mentorship quality or lab culture, the following sources may provide supplementary signals.

**Structured review databases** (e.g., baoyanren.com exports with 10,000+ entries) are more reliable than scattered social-media posts because they use consistent rating scales and dimension tags. Use `review_matcher.py` to convert them into `investigation_leads`. Every lead must still be cross-checked against a verifiable public record.

**Unofficial platforms** (导师评价网, 知乎, 小红书, RateMyProfessors) should be treated as **hearsay** — useful for generating hypotheses, insufficient for standalone allegations. For international investigations, `analysis/review_aggregator.py` can merge multiple sources into a unified review schema with source-weighted credibility scoring.

| Platform | Search Query | Typical Signal | Reliability |
|:---|:---|:---|:---:|
| **Structured review DB** (baoyanren.com export) | `review_matcher.py --name xxx --school yyy` | Rating distribution, dimension breakdowns, verified leads | ⭐⭐⭐☆☆ |
| **导师评价网** (daoshidianping.com) | `导师姓名 + 学校` | Student complaints about authorship theft, excessive chores, or delayed graduation | ⭐☆☆☆☆ |
| **知乎 / 小红书 (国内导师)** | `导师姓名 + 读研体验 / 实验室` | Informal peer experiences; high noise-to-signal ratio | ⭐☆☆☆☆ |
| **小红书 (国外导师)** | `xiaohongshu_client.py --name "Prof. X" --institution "MIT"` | Chinese international students' first-hand reviews of foreign advisors: graduation difficulty, workload, supportiveness, funding | ⭐⭐☆☆☆ |
| **RateMyProfessors** | `ratemyprofessors.com` search | Western student ratings: overall quality, difficulty, "would take again" | ⭐⭐☆☆☆ |
| **微信公众号** | `wechat_search.py --keyword 导师姓名` | Book promotions, institutional gossip, and unverified rumors; useful for generating leads | ⭐☆☆☆☆ |
| **ResearchGate / LinkedIn** | Scholar name + former students | Alumni trajectories; frequent departure from academia without publications is a negative signal | ⭐⭐☆☆☆ |

**Evidence standard for public reputation**: Every claim from an anonymous source must be recorded with **platform name, post date, and exact URL or screenshot filename / database row reference**. It may **not** be presented as established fact. Cross-check any specific allegation (e.g., "delays graduation") against verifiable public records (dissertation submission dates) before inclusion in the main findings.

> **Source attribution rules**:
> - **WeChat articles**: Attribute as **"微信公众号"**. Do **not** mention tool names (`wechat_search.py`, Playwright, camoufox).
> - **Xiaohongshu reviews**: Attribute as **"来自匿名社交媒体分享"**. Author IDs must be anonymized in output. Never expose personally identifiable information.
> - **RateMyProfessors**: Attribute as **"RateMyProfessors 学生评价"**. Note that RMP has strong negative selection bias.

#### Step 6 Evidence Standards
- **Maintain a source inventory** that maps every major claim to its supporting evidence. Use numbered footnotes or endnotes throughout the report.
- **Independence check**: two sources are "independent" only if they do not derive from the same press release, biography, or institutional webpage. A news report quoting the scholar's CV does **not** count as independent of the CV.
- **Downgrade confidence** for any claim where sources conflict or where the only sources are self-reported.
- **Document negative searches**: if a claimed degree or publication cannot be found, record the exact databases searched, query terms, and dates.

### Step 7: Synthesis & Report Generation

**Framework**: Two-sided assessment (Achievements + Issues)

**Report Structure**:
1. Executive Summary
2. Basic Profile & Timeline
3. Output Quantity Verification
4. Quality Assessment
5. Relationship Network Analysis
6. Anomaly Detection Results
7. Multi-Source Validation
8. Balanced Conclusions
9. Appendices

#### Step 7 Evidence Standards
- **The executive summary must accurately reflect the body of the report**; no new claims or inflated language may be introduced at this stage.
- **Balanced conclusions require at least one paragraph of acknowledged strengths** for every paragraph of documented weaknesses.
- **Attach the full evidence chain**: raw database exports, PDF text profiles, screenshot filenames, and interview notes (anonymized) must be listed in the appendices.
- **Include a limitations section** that explicitly states what could **not** be verified and why.

## Investigation Checklist

- [ ] Basic profile complete with timeline
- [ ] All claimed outputs verified
- [ ] Core works assessed for quality/originality
- [ ] Advisor and key relationships mapped
- [ ] Promotion timeline compared to peers
- [ ] At least 2 independent sources for major claims
- [ ] Both achievements and issues documented
- [ ] Evidence chain preserved
- [ ] Confidence ratings assigned

## 最终交付物检查清单（LLM 交付前必须逐项确认）

> ⚠️ **LLM 强制指令**：生成最终报告后，必须逐项勾选以下清单。
> 缺少任何一项，不得视为完成交付。

### 核心交付物

- [ ] 深度调查报告（Markdown/PDF）—— 含执行摘要、多维度分析、两面性结论
- [ ] 交互式学术关系网络图谱（`{姓名}_network.html`）—— D3.js 力导向图
- [ ] 导师蒸馏知识库（可选）—— 将调查资料上传至 `mentor-distill/` 服务进行蒸馏，生成可对话的学者知识库，提供 OpenAI 兼容的对话接口

### 结构化数据附件

- [ ] 文本画像数据（text_profiler.py 输出的 JSON）
- [ ] 论文六维评分数据（paper_quality_rubric.py 输出的 JSON，如有论文分析）
- [ ] 引用分析报告（citation_profiler.py 输出的 JSON，如有引用数据）
- [ ] 风格计量学报告（stylometry_profiler.py 输出的 JSON，如有多篇可比文本）
- [ ] 基准线偏差报告（benchmark_engine.py 输出的异常指数，如已运行）

### 证据与合规

- [ ] 每条主要结论标注了数据来源和查询时间
- [ ] 置信度评定已为每条核心发现赋值（L1-L5）
- [ ] 免责声明已完整包含
- [ ] 水印已嵌入（如适用）
- [ ] 报告无客户个人信息泄漏风险

## Special Investigation Types

The framework has been validated against three anonymized case studies representing distinct patterns. The following 12 investigation types map to the 7-step framework:

| Type | Focus | Key Checks | Typical Pattern |
|:---|:---|:---|:---|
| 1. Credential Fraud & Inflation | Stated vs. verifiable academic achievements | Paper counts, monograph verification, CV timeline gaps | +40% inflation in claimed paper counts; visiting scholar misrepresented as postdoc |
| 2. Plagiarism | Unauthorized use of others' work or ideas | Text duplication rates, side-by-side comparison, translated-as-original claims | High similarity without attribution; core chapters lack originality markers |
| 3. Data & Image Fabrication | Falsified or manipulated research data/images | Repeated images across papers, impossible statistics, unavailable raw data | Identical gel bands in unrelated experiments; stats contradict sample size |
| 4. Duplicate Publication / Salami Slicing | Same results split or republished across outlets | Dissertation-monograph overlap, bilingual duplication, fragmented outputs | 1 dissertation → 7+ derivative publications; overlap <5% with original thesis |
| 5. Paper Mill & Authorship Commerce | Commercial acquisition of papers or authorship slots | Tortured phrases, ultra-fast acceptance, topic-author mismatch | Nonsensical synonym-swapped phrases; acceptance within days |
| 6. Authorship Corruption | Author credits not matching actual contribution | First-author dominance by mentor, ghost writers, bought authorship | Mentor claims first authorship on all student work with no verifiable contribution |
| 7. Peer Review Manipulation | Improper influence on peer review outcomes | Fake reviewer emails, coercive citations, editorial collusion | Authors review own papers via false email domains; editors demand self-citations |
| 8. Dependency Pattern | Over-reliance on advisor/leader networks for publications and promotion | Co-author concentration with one superior, promotion gaps, absent independent mentorship | 15+ years without promotion yet continuous top-tier papers with same leader |
| 9. Academic Clique & Citation Manipulation | Monopolistic control of resources and metric gaming | Citation cartels, coercive citations, nepotism in evaluation | Mutual citation rates >30% within closed circle; evaluation manipulation via guanxi |
| 10. Grant Fraud & Financial Misconduct | Misuse, embezzlement, or fraudulent use of research funds | Abnormal reimbursements, related-party transactions, deliverable mismatches | 1,500 one-way train tickets to same city; funds channeled to family companies |
| 11. Conflict of Interest Concealment | Failure to disclose relationships that could bias research | Corporate funding with one-sided conclusions, undisclosed equity, undisclosed familial reviewing | Study conclusions systematically favor sponsor; reviewer fails to recuse on friends' papers |
| 12. Research Ethics Violations | Violations of human/animal/data protection norms | Missing IRB approval, unauthorized sensitive data, animal welfare breaches | Clinical trials without informed consent; 3R principles ignored in animal studies |
| 13. Ghost Writing & AI-Assisted Authorship | Suspected use of ghost writers or AI-generated content without disclosure | Stylometric consistency, AIGC statistical features, translation plagiarism, capability consistency | Sudden style rupture in a paper; perplexity/Burstiness scores matching AI patterns; author lacks training for methods used in the paper |

### International-Specific Investigation Types

The following patterns are primarily observed in **international academic contexts** (foreign graduate advisors, overseas scholars):

| Type | Focus | Key Checks | Typical Pattern | Detection Rule |
|:---|:---|:---|:---|:---|
| I01. Predatory Journal Publishing | Papers published in journals with rapid publication + high APC + low selectivity | Publisher name (Frontiers/MDPI/Hindawi), journal name patterns, OA ratio | >3 papers in Frontiers/MDPI journals with no Q1/Q2 publications | `international/heuristics_classifier.py` |
| I02. Paper Mill Patterns | Template-title papers, ghost author sets, rapid publication clusters | Title generalization with `{WORD} for {DISEASE}`, same ghost authors across papers, >8 papers/year | "Machine Learning for X Disease" series with identical structure; author overlap >80% | `international/heuristics_classifier.py` |
| I03. Image Manipulation | Duplicated/blurred/modified figures across papers | Gel band reuse, impossible statistics, figure overlay | Identical Western blot bands in unrelated experiments | Manual visual inspection + PubPeer comments |
| I04. Citation Cartel | Self-citation rings or reciprocal citation clusters | Self-citation ratio, mutual citation within closed group | Self-citation >30%; mutual citation >30% within 3-author circle | `international/heuristics_classifier.py` + `citation_profiler.py` |
| I05. P-hacking / Data Fabrication | Pressure to produce significant results; manipulated data | P-value distribution, impossible statistics, raw data unavailability | All p-values clustered at 0.049; effect sizes inconsistent with sample size | Statistical audit + `common_heuristics.py` |
| I06. Ghost Authorship | Author lists exceed actual contribution; honorary authorship | Author count vs. contribution, >20 authors in non-big-science fields | 25+ author papers in CS without CERN/LHC-type collaboration | `international/heuristics_classifier.py` |
| I07. Rapid Publication | Unusually high publication velocity in short time windows | Papers per month, batch submissions | 5+ papers in a single month; acceptance within days of submission | `international/heuristics_classifier.py` |
| I08. Ghost Writing & AI-Assisted Authorship | Suspected use of ghost writers or undisclosed AI tools | Stylometric drift, AIGC perplexity/Burstiness, file metadata anomalies, capability mismatch | Author's writing style suddenly shifts; paper contains methods beyond author's known training; file creation timestamps suggest ultra-rapid composition | `stylometry_profiler.py` + `aigc_statistical_profiler.py` + `capability_consistency_checker.py` |

**International evaluation benchmarks** (discipline-specific):
- **STEM tenure-track (R1)**: 15+ papers, 8+ first-author, 3+ Q1, h-index ≥12 at year 6
- **Humanities tenure-track (liberal arts)**: 6+ papers, 3+ first-author, 1+ Q1, h-index ≥5 at year 6
- See `scripts/evaluation_baselines.md` for full benchmarks by discipline and institution tier.

## Case Studies

Three foundational anonymized case studies demonstrating methodology:

1. **Case A** (华东某师范大学): "Salami slicing" pattern — one dissertation fragmented into 7+ publications
2. **Case B** (华东某师范大学): "Credential inflation" pattern — claimed paper counts exceeded verified counts by ~44%
3. **Case C** (北京某国家级研究机构): "Dependency" pattern — 16-year promotion stagnation coupled with leader-dependent top-tier publications

---

---

## 扩展调查模块 A：行政职务-产出耦合分析

### 概述

行政权力可能转化为学术发表渠道、审稿便利或学生培养资源。本模块通过对比学者在**任职前、任职中、卸任后**三个时间窗口的学术产出曲线，识别是否存在疑似"权力窗口期套利"迹象。

### 调查步骤

#### 步骤 1：建立行政职务时间线
收集学者的所有行政职务及其起止时间：

| 职务类型 | 示例 | 证据来源 |
|:---|:---|:---|
| 机构内部行政职务 | 副所长、院长、系主任、研究室主任 | 机构官网任免通知、组织部公示 |
| 学术期刊职务 | 副主编、编委、特邀编辑 | 期刊官网编委会名单、年度更替公告 |
| 学术团体职务 | 学会理事长、专委会主任 | 学会官网、会议纪要 |
| 项目评审职务 | 基金项目会评专家、学科评议组成员 | 基金委公示、学科评估报告 |

#### 步骤 2：建立三窗口产出对比
以职务任职年为界，划分三个窗口（建议窗口长度一致，如各2-3年）：

| 窗口 | 时间范围 | 需统计指标 |
|:---|:---|:---|
| 任职前 | 任职起始年往前推 N 年 | 个人年均论文数、顶刊占比、独立一作占比 |
| 任职中 | 任职起始年至卸任年 | 同上 + 学生年均论文数 + 本单位期刊占比 |
| 卸任后 | 卸任年往后推 N 年 | 同上 |

**控制变量**：对比同机构、同年龄段、担任同类行政职务的其他学者的同期产出，排除"职务本身带来时间挤压"的正常波动。

#### 步骤 3：分析产出结构变化
不仅看数量，还要看**来源结构**：

- 任职期间发表的顶刊中，合著者是否包含下属、学生或关联领导？
- 本单位或关联期刊的占比是否显著上升？
- 是否存在"任职末期冲刺发表潮"（卸任前6-12个月集中录用）？

### 证据标准

- **职务时间必须精确到年月**。如果只有年份，需标注"推断"并降低置信度。
- **产出数据必须来自独立数据库**（CNKI、Wanfang、WoS），禁止仅用学者自称数据。
- **时间窗口划分需在报告中明确说明**。窗口过短（如任职仅6个月）不具备分析价值。
- **相关性不等于因果性**。发现耦合后，必须排除其他解释（如职务带来了更多团队资源、减少了教学负担）。

### 危险信号清单

| 信号 | 判定标准 | 严重程度 |
|:---|:---|:---:|
| **权力窗口期产量激增** | 任职中年均论文数比任职前增长 ≥100% | 高 |
| **顶刊渠道权力依赖** | 任职期间顶刊占比显著高于任职前和卸任后，且主要依赖领导/下属合著 | 高 |
| **学生产出同步异动** | 任职期间学生一作论文量激增，卸任后同比例下降 | 中高 |
| **任职末期冲刺发表** | 卸任前12个月内录用/见刊的论文占任职期间总量的 ≥25% | 中 |
| **卸任后产量悬崖** | 卸任后年均论文数回落至任职前水平甚至更低 | 中 |
| **行政负担与产出悖论** | 年均授课/行政工时显著高于同职级同事，但产出同样高企 | 中高 |

---

## 扩展调查模块 B：机构主场优势量化

### 概述

学者所在机构主办或实质控制的学术期刊，可能构成"主场"。本模块量化学者在该类期刊上的发文密度、编委关联度，以及离开本单位后的发表轨迹变化，识别疑似"内部人发表通道"的迹象。

### 调查步骤

#### 步骤 1：识别机构主办期刊清单
通过以下渠道确认学者所在机构（含其院系、研究所、附属机构）主办或合办的期刊：

| 查询渠道 | 查询方式 | 输出 |
|:---|:---|:---|
| 国家新闻出版署 | 期刊查询系统，按主办单位检索 | 期刊名称、CN号、主办单位 |
| 机构官网 | 科研机构"学术期刊"栏目、出版社官网 | 主办期刊列表 |
| 知网期刊导航 | 查看期刊"出版单位" | 出版单位与机构的关联关系 |
| 期刊官网 | "About Us""主办单位"页面 | 确认主办、承办、协办单位 |

**注意**：某些期刊名义上由出版社主办，但实际编委会由某机构学者垄断，这种情况需在步骤3中补充说明。

#### 步骤 2：统计主场发文密度
基于手动收集的论文清单，计算以下指标：

| 指标 | 计算公式 | 意义 |
|:---|:---|:---|
| 主场期刊发文占比 | 主场期刊论文数 ÷ 核心期刊论文总数 | 反映对内部渠道的依赖度 |
| 主场期刊集中度 | 某单一主场期刊论文数 ÷ 主场期刊论文总数 | 反映对特定内部期刊的依赖度 |
| 主场期刊年均产出 | 主场期刊论文数 ÷ 任职年数 | 与同行对比的基础 |
| 主场期刊作者排序 | 主场期刊论文中的署名位置分布 | 是否多为第一作者或通讯作者 |

#### 步骤 3： mapping 编委-作者关系网
保存期刊编委会名单截图，识别以下关联：

- 该期刊编委中是否有学者的**导师**？
- 是否有学者的**同僚**（同系/同所）？
- 是否有学者的**学生**或**曾经的合作者**？
- 学者本人是否曾在该期刊担任编委/副主编？

#### 步骤 4：横向与纵向对比
- **横向对比**：选择同领域、同级别、非本单位主办的2-3本期刊，对比学者在这些期刊上的年均发表量、审稿周期（如有公开信息）、录用难度。
- **纵向对比**：如果学者有工作调动记录，对比其**调动前、调动后**在该原单位期刊上的发文量变化。离开后若骤降，暗示主场优势消失。

### 证据标准

- **期刊主办单位信息必须来自官方渠道**（新闻出版署、期刊官网），不可用百度百科等二次来源。
- **编委名单必须标注保存日期**，因为编委会可能定期换届。
- **论文归属必须按发表时的作者单位计算**。如果学者已调离原单位，但论文仍标注原单位，则该论文计入原单位主场。
- **主场优势结论必须排除学科特殊性**。某些小众学科确实只有1-2本专业期刊，且均由头部机构主办，这种情况需降低信号权重。

### 危险信号清单

| 信号 | 判定标准 | 严重程度 |
|:---|:---|:---:|
| **主场期刊占比过高** | 主场期刊发文占核心期刊总量的 ≥30% | 高 |
| **单一主场期刊依赖** | 超过60%的主场论文集中在某一本期刊 | 中高 |
| **编委熟人网络重叠** | 该期刊编委中同时存在学者的导师+同事+学生 | 高 |
| **离开后主场发文骤降** | 调离原单位后，原主场期刊年均发文下降 ≥80% | 高 |
| **主场期刊审稿异常快** | 在本场期刊的投稿-见刊周期显著短于同领域均值（如有内部数据或同行证言） | 中高 |
| **主场专刊/专栏频繁** | 学者或其团队多次在本场期刊主持专刊、专栏 | 中 |

---

## 扩展调查模块 C：从"论文"往上下游延伸

### 概述

单一论文只是学术生产链的终端节点。向上追溯其源头（学位论文、会议报告、预印本），向下追踪其后续裂变（拆分发表、双语发表、会议转化），可以发现 salami slicing、一稿多投、疑似审稿套利等更隐蔽的问题。

本模块包含三个子方向：**学位论文裂变追踪**、**会议旅游与学术社交泡沫**、**审稿互惠网络**。

---

### C.1 学位论文裂变追踪

#### 调查目标
识别学位论文（尤其是博士论文）是否被不当地拆分为多篇期刊论文，或期刊论文的核心内容是否已在学位论文中完整呈现而缺乏增量贡献。

#### 调查步骤

1. **获取学位论文全文**。来源：CNKI 博硕论文库、万方、机构图书馆、国家图书馆。
2. **建立学位论文目录-期刊论文映射表**。将学位论文的各章标题、核心图表、主要结论，与学者后续发表的期刊论文进行逐项比对。
3. **评估增量贡献**。对每一篇由学位论文衍生出的期刊论文，判断其相对于学位论文新增了哪些内容（新数据、新案例、新理论框架、新方法）。

#### 证据标准

- **学位论文和期刊论文必须获取全文**，仅对比标题和摘要不足以支持结论。
- **增量贡献评估必须具体到章节、图表、核心论点**。禁止用"感觉重复"这样的模糊表述。
- **必须考虑学科惯例**。在某些学科，将博士论文拆分为2-3篇期刊论文是正常甚至鼓励的。

#### 危险信号

| 信号 | 判定标准 | 严重程度 |
|:---|:---|:---:|
| **一章拆多篇** | 学位论文的某一章被拆分为3篇及以上期刊论文发表 | 高 |
| **无增量拆分** | 期刊论文与学位论文某章的重合度>70%，且无明显新增数据/理论 | 高 |
| **学位论文滞后发表** | 学位论文中的核心内容已在期刊发表，但学位论文的提交日期晚于期刊发表日期（暗示一稿多投或学位论文拼凑） | 高 |
| **答辩委员后续合作** | 答辩委员会成员在答辩后2年内与学者发生高频合著 | 中 |

---

### C.2 会议旅游与学术社交泡沫

#### 调查目标
识别学者是否通过参加低质量或旅游导向的学术会议来制造"国际交流"假象，以及在会议中形成固定的互惠小圈子。

#### 调查步骤

1. **收集会议参与记录**。来源：学者个人主页、机构新闻稿、会议手册、朋友圈/微博截图（如有）。
2. **建立会议地理分布图**。标注每次会议的举办城市，区分学术中心城市与旅游城市。
3. **追踪会议论文的后续命运**。会议论文集是否有ISBN/DOI？会议论文是否在会后2年内转化为期刊论文？
4. **识别重复参会圈子**。统计每次会议中，与学者同框或同场报告的固定面孔。

#### 证据标准

- **会议信息必须有可查来源**，不能依赖模糊回忆。
- **旅游城市的界定需客观**，可参考该城市是否为主要国际学术机构所在地。
- **会议论文转化率的计算需注明分母**（即已知发表了会议论文的总数）。

#### 危险信号

| 信号 | 判定标准 | 严重程度 |
|:---|:---|:---:|
| **会议旅游化** | 过去5年中，≥50%的参会地点为非学术中心的热门旅游城市 | 中 |
| **零转化会议论文** | 会议论文集发文≥5篇，但0篇在会后转化为期刊论文 | 中高 |
| **固定飞行俱乐部** | 某3-5人的小团体在3个以上不同国际会议上重复同框且互相报告 | 中高 |
| **会议与度假时间耦合** | 参会时间总是安排在暑期/寒假，且会后停留时间≥参会天数 | 中 |
| **会议主办机构可疑** | 会议由无知名学术背景的民间公司或频繁换名机构主办 | 中高 |

---

### C.3 审稿互惠网络

#### 调查目标
通过公开可得的编委信息、致谢声明、专刊编辑记录，推断学者之间是否存在隐性的审稿互惠或编辑权力交换。

#### 调查步骤

1. **收集学者担任编委/特邀编辑的期刊清单**及任期。
2. **收集学者在论文致谢中感谢过的审稿人或编辑**（部分论文会在致谢中提及审稿建议）。
3. **追踪"客座编辑专刊"中的作者构成**。当学者A担任某期刊客座编辑时，检查该专刊的作者中是否高频出现学者A的合作者、学生或同门。
4. **交叉映射**。如果学者A的论文频繁发表在学者B担任编委的期刊，同时学者B的论文也频繁发表在学者A关联的期刊，标记为潜在互惠对。

#### 证据标准

- **编委名单和专刊信息必须截图保存**，因为这些网页可能更新。
- **互惠推断必须基于多次、双向的模式**，单次巧合不构成证据。
- **必须排除学科小领域的正常审稿关系**。如果整个领域只有20个活跃学者，互相审稿是难以避免的。

#### 危险信号

| 信号 | 判定标准 | 严重程度 |
|:---|:---|:---:|
| **客座编辑专刊熟人化** | 学者主持专刊中，≥40%的作者为其直接合作者、学生或同单位同事 | 高 |
| **双向期刊互惠** | 学者A在B编委期刊的年均发文量是A在其他同等级期刊的3倍以上，且反之亦然 | 高 |
| **审稿致谢圈** | 学者在论文中反复感谢同一批审稿人，而这些审稿人恰好在学者担任编委的期刊中发文 | 中高 |
| **异常快速录用** | 在互惠关联期刊上的投稿-录用周期显著短于该期刊公开的平均周期 | 中高 |
| ** coercive citation 迹象** | 某期刊的审稿意见中系统性地要求引用该编委的论文（需获得审稿意见或作者证言） | 高 |

---

## 模块优先级与工具映射

| 模块 | 最关键的数据来源 | 现有脚本支持 | 新增工具建议 |
|:---|:---|:---:|:---|
| 行政职务-产出耦合 | 机构任免公示 + CNKI/WoS | `data_validator.py`（时间线校验） | `timeline_matcher.py`：自动对比职务时间线与论文时间戳 |
| 机构主场优势量化 | 新闻出版署 + 期刊官网编委名单 + 论文清单 | `text_profiler.py`（PDF/Markdown/文本解析） | `journal_homefield.py`：输入论文JSON和机构名，输出疑似主场占比与编委重叠分析 |
| 论文上下游延伸 | 学位论文PDF/Markdown + 会议手册 + 期刊专刊信息 | `text_profiler.py` + `similarity_scanner.py`（建议新增） | `dissertation_mapper.py`：对比学位论文目录与期刊论文的章节映射 |

*所有新增工具均遵循半自动原则：人类负责收集原始文件和验证关键来源，脚本负责计算、比对和生成可视化表格。*

---

---

## 扩展调查模块 D：学术影响力刷量检测

### 概述

学术影响力指标（h-index、被引次数、期刊影响因子）可能被人为操纵。本模块通过分析引用来源结构、自引模式、互引卡特尔和引用者期刊质量，识别是否存在疑似"指标操纵"迹象。

### 调查步骤

#### 步骤 1：建立引用基线
收集学者在主要数据库（CNKI、Google Scholar、Web of Science）中的被引记录，提取前50-100条引用信息：

| 收集项 | 说明 | 用途 |
|:---|:---|:---|
| 引用论文标题 | 完整标题 | 判断引用者主题相关性 |
| 引用者姓名 | 第一作者或通讯作者 | 识别互引圈子和熟人网络 |
| 引用者机构 | 发表时的署名单位 | 检测机构内部互引 |
| 发表期刊 | 期刊名称及级别 | 评估引用来源质量 |
| 发表年份 | 引用论文的见刊年份 | 分析时间结构和即时性 |

#### 步骤 2：h-index 增长曲线分析
绘制学者历年的 h-index 和年均被引次数，标注以下异常点：

- **跳跃式增长**：某一年内 h-index 增量超过前3年均值的200%
- ** plateau 后突兀拉升**：长期停滞后突然因一两篇论文被大量引用而突破
- **与产出脱钩的增长**：h-index 快速增长期与论文发表量低谷期重叠

#### 步骤 3：引用来源质量扫描
对前50条引用进行质量分级：

| 质量等级 | 定义 | 正常占比参考 |
|:---|:---|:---:|
| A级 | CSSCI/SSCI Q1-Q2、学科顶刊 | 40-60% |
| B级 | 北大核心/SSCI Q3-Q4、普通SSCI | 20-40% |
| C级 | 普通省级期刊、会议论文集 | 10-20% |
| D级 | 掠夺性期刊、低质量OA期刊、明显无关期刊 | <5% |

**掠夺性期刊识别方法**：查询 Cabells 黑名单、Beall's List（存档版）、DOAJ 移除记录，或观察期刊特征（创刊时间极短、审稿周期异常快、 APC 费用高昂、编委信息模糊）。

#### 步骤 4：自引与互引结构分析
从引用记录中分离以下类型：

- **直接自引**：学者本人出现在引用论文的作者列表中
- **团队自引**：引用论文作者为学者的学生、同课题组成员或前同事
- **互引卡特尔迹象**：学者A和B在特定时间窗口内（如2年）互相引用对方论文超过阈值（如5次）
- **第三方无关引用**：与学者无直接合作关系的独立研究者引用

计算各类引用在总引用中的占比，并与同领域学者的平均水平对比。

### 证据标准

- **h-index 数据必须标注数据库和检索日期**。不同数据库（CNKI vs Google Scholar）的结果可能差异显著。
- **引用记录分析必须基于可导出的结构化数据**，禁止仅凭直觉判断"引用质量低"。
- **互引卡特尔迹象的判定必须有时间窗口和频次阈值**，单次引用不构成证据。
- **掠夺性期刊指控必须引用权威黑名单或提供具体可疑特征清单**，不可泛化打击所有OA期刊。
- **相关性不等于因果性**。h-index 突增可能有正当原因（如某篇论文恰好切中热点政策议题），需结合内容分析排除。

### 危险信号清单

| 信号 | 判定标准 | 严重程度 |
|:---|:---|:---:|
| **h-index 跳跃式增长** | 某一年内 h-index 增量超过前3年均值的300% | 高 |
| **高比例低质量引用** | 前50条引用中，D级期刊占比≥15%或C+D级占比≥40% | 中高 |
| **密集互引对子** | 与某一位学者在2年内互相引用超过10次 | 高 |
| **自引率异常** | 总被引中直接自引率超过20%（人文社科可放宽至25%） | 中高 |
| **团队自引闭环** | 学者与学生/前同事构成的5人小圈子内部互引率超过30% | 高 |
| **即时自引流水线** | 论文A发表后6个月内，论文B即引用A，且B与A主题关联度低 | 中 |
| **引用者主题无关** | 多篇引用论文的研究主题与学者领域明显不符，却无跨学科方法论引用 | 中高 |

---

## 扩展调查模块 E：语言风格计量学与代笔检测

### 概述

每位学者都有其稳定的"文字指纹"，包括虚词使用偏好、句法结构、连接词模式和特定表达方式。当某位学者的某篇论文突然出现显著的风格断裂，或与某位学生/助理的风格高度相似时，可能存在疑似代笔或团队代工后挂名的风险。本模块通过低层次语言特征对比，为疑似代笔假设提供可量化的支持或排除证据。

### 调查步骤

#### 步骤 1：构建对比语料库
选择以下文本作为分析对象：

| 语料类型 | 数量建议 | 选取标准 |
|:---|:---:|:---|
| 学者本人论文 | 5-10篇 | 不同时期、同一主题领域、独立一作或明确个人撰写的章节 |
| 目标待检论文 | 1-3篇 | 需要验证真实作者的论文（通常是顶刊合著或署名存疑的论文） |
| 学生/助理论文 | 2-5篇 | 与待检论文同期或稍早发表的毕业论文、一作期刊论文 |

**排除干扰文本**：政策评论、报纸采访、会议致辞等非学术写作不纳入语料库。

#### 步骤 2：提取语言特征向量
对每篇文本计算以下低层次语言指标。这些指标不受研究主题影响，具有较强的作者标识性：

| 特征类别 | 具体指标 | 说明 |
|:---|:---|:---|
| **句法结构** | 平均句长（字/句） | 长短句偏好 |
| | 分句复杂度 | 含多个逗号或分号的长句占比 |
| **虚词与功能词** | "的"字密度 | 每百字中"的"的出现次数 |
| | "了/着/过"密度 | 时态助词使用模式 |
| | "而/但/然而"密度 | 转折连接词偏好 |
| **连接与过渡词** | "综上所述/一言以蔽之/毋庸讳言/值得注意的是" | 个人惯用套语频次 |
| | "首先/其次/最后" vs "第一/第二/第三" | 枚举方式偏好 |
| **标点指纹** | 分号使用率 | 分号占全部标点的比例 |
| | 冒号/破折号使用率 | 解释说明类标点的偏好 |
| | 引号使用密度 | 直接引用与间接引用的比例 |
| **人称与立场** | "笔者/本文/我们"密度 | 作者自我指称方式 |
| | "认为/发现/指出/表明"密度 | 论述动词偏好 |

#### 步骤 3：风格相似度计算
将每篇论文表示为多维特征向量，计算以下距离/相似度：

- **学者本人论文之间的平均相似度**：作为个人风格稳定性的基线
- **待检论文与学者本人语料的距离**：判断是否属于同一风格簇
- **待检论文与学生语料的距离**：判断是否存在疑似代笔转移迹象

**分析方法**：可使用余弦相似度、欧氏距离或主成分分析（PCA）可视化。脚本只需输出数值和简单的二维散点图即可，最终解释由人类完成。

#### 步骤 4：定性复核
计量结果仅提供假设。对标记为"风格异常"的论文，需进行人工复核：

- 是否存在**学科惯例或期刊风格要求**导致作者改变表达？（如某期刊强制要求使用"我们"而非"笔者"）
- 是否存在**合作者主笔**的合理说明？（如某篇论文明确由合作者主导撰写）
- 待检论文与疑似代笔者论文之间，是否存在**共同数据来源或方法模板**导致的非作者性风格相似？

### 证据标准

- **语料库构建必须透明**：每篇纳入分析的论文需标注标题、年份、作者排序、选取理由。
- **分析必须基于全文而非摘要**：摘要通常由期刊编辑修改，不能代表作者原始风格。
- **必须控制主题变量**：对比文本应尽量属于同一研究领域。跨学科比较可能因术语差异导致误判。
- **计量结果只能作为支持性证据**。风格相似度高不等于存在代笔，风格差异大也不等于清白。禁止单独以此指控学术不端。
- **必须排除翻译文本的干扰**：如果论文是从英文翻译而来或由他人润色，风格可能被人为改变。

### 危险信号清单

| 信号 | 判定标准 | 严重程度 |
|:---|:---|:---:|
| **显著风格断裂** | 待检论文与学者本人语料的平均相似度低于0.3（余弦相似度），且偏离学者本人的风格簇超过2个标准差 | 中高 |
| **学生风格高度重合** | 待检论文与某位学生/助理论文的风格相似度高于学者本人论文之间的平均相似度 | 高 |
| **课题组风格同质化** | 课题组所有论文的风格一致性极高（簇内相似度>0.8），但学者独立论文的风格一致性极低（簇内相似度<0.4） | 高 |
| **同一学者双重人格** | 学者在不同时期的论文明显分裂为两个互不重叠的风格簇，且无学科转型或合作者变更的合理解释 | 中高 |
| **顶刊论文风格异常** | 学者在顶刊发表的论文风格与本人其他论文显著不同，而在普通期刊发表的论文风格回归正常 | 高 |

---

## 扩展模块汇总与工具映射

| 模块 | 核心数据源 | 分析重点 | 建议新增脚本 |
|:---|:---|:---|:---|
| 行政职务-产出耦合 | 任免公示、论文时间戳 | 权力窗口期的产出异动 | `timeline_matcher.py` |
| 机构主场优势量化 | 期刊主办信息、编委名单 | 内部人发表通道 | `journal_homefield.py` |
| 论文上下游延伸 | 学位论文、会议手册、专刊信息 | salami slicing、审稿套利 | `dissertation_mapper.py` |
| 学术影响力刷量检测 | 引用记录、h-index 时序 | 指标操纵与互引卡特尔迹象 | `citation_profiler.py`：导出引用数据并计算自引率、互引密度、来源质量分级 |
| 语言风格计量学 | 论文全文文本 | 疑似代笔迹象检测与作者真实性 | `stylometry_profiler.py`：提取虚词、句长、标点等特征向量，输出相似度矩阵、PCA可视化、词频偏差热图 |

*所有模块均遵循半自动原则：脚本负责可重复的计算与比对，人类负责数据来源验证、假说解释和最终结论。*

---

---

## 扩展调查模块 F：商业利益网络与经费 footprint 分析

### 概述

学者的学术观点、课题方向、学生论文选题是否系统性地偏向其持股或任职的企业？本模块通过工商信息、专利发明人、横向项目公告与论文结论偏向性的交叉检索，识别疑似"学术身份为企业背书"与"企业资源填充学术产出"的双向套利风险迹象。

### 调查步骤

#### 步骤 1：工商信息交叉检索
通过天眼查、企查查或国家企业信用信息公示系统，输入学者全名+所在城市，筛选同名同城的董事、监事、股东、法定代表人记录。

| 查询维度 | 输出项 | 证据保存 |
|:---|:---|:---|
| 任职企业 | 企业名称、任职类型、起止时间 | 网页截图或导出报告 |
| 持股信息 | 持股比例、认缴金额、变更记录 | 股权结构截图 |
| 关联企业 | 通过直系亲属/配偶控制的企业 | 亲属持股穿透图 |

**去重与确认原则**：若同名人数较多，需通过以下特征交叉确认：
- 企业注册地或经营范围与学者研究领域相关
- 企业专利/论文中出现学者的学生或课题组成员
- 企业联系方式或邮箱与学者所在单位存在关联

#### 步骤 2：专利发明人映射
在国家知识产权局专利检索系统、IncoPat 或 Soopat 中，以步骤1识别出的企业为申请人，检索其全部专利：

- 统计专利发明人名单，识别是否高频出现学者的学生、博士后、课题组成员
- 对比专利的技术主题与学者发表的学术论文主题，评估重叠度
- 标记"学生专利-导师论文"时间耦合：专利优先权日是否早于或同步于相关论文的投稿日期

#### 步骤 3：论文结论偏向性审查
筛选学者发表的与任职企业所在行业高度相关的论文，逐篇评估：

| 评估项 | 检查内容 | 红旗信号 |
|:---|:---|:---|
| 资助声明 | 论文致谢或脚注中是否披露企业资助 | 未披露但实际存在关联 |
| 数据来源 | 是否使用了企业的内部数据或调研样本 | 数据来源未说明或无法公开验证 |
| 结论方向 | 结论是否系统性地有利于该企业或其所在行业 | 所有相关论文结论均呈一边倒支持 |
| 风险提示 | 是否对研究对象的风险或负面效应保持沉默 | 只谈收益、回避代价 |

#### 步骤 4：横向项目 footprint 追踪
部分高校和研究机构会在官网公示横向项目立项信息。收集以下字段：

- 项目名称、合作企业名称、合同金额、到账时间
- 项目起止日期、主要参与人（特别是学生）
- 项目成果形式（论文、专利、研究报告）

**关键分析**：横向项目到账时间与相关论文发表时间是否存在6个月内的密集耦合。

### 证据标准

- **工商信息必须来自官方公示系统或权威商业数据库**，自媒体爆料不可替代。
- **同名确认必须列出排除其他同名者的推理过程**，不能简单把第一个搜索结果当作证据。
- **专利与论文的时间对比必须精确到月份**，优先权日与投稿/录用日期的先后关系是核心证据。
- **结论偏向性必须基于具体论文的逐篇内容分析**，不能用"感觉像广告"这样笼统的表述。
- **必须区分正当产学研合作与利益冲突隐瞒**。公开披露的企业资助研究本身不违规，隐瞒才是问题。

### 危险信号清单

| 信号 | 判定标准 | 严重程度 |
|:---|:---|:---:|
| **隐蔽持股/任职** | 学者在公开简历中未披露其在某企业的董事或股东身份 | 高 |
| **学生专利集中归属企业** | 某企业≥50%的发明人为学者实验室成员，且技术主题与学者论文高度重合 | 高 |
| **论文资助未披露** | 学生论文或学者论文使用了企业数据/得出了有利于企业的结论，但未声明利益冲突 | 高 |
| **结论系统性偏袒** | 学者在某行业的3篇及以上论文结论全部一边倒支持行业利益，且无负面发现 | 中高 |
| **横向项目-论文时间耦合** | 横向项目到账后6个月内，学者团队密集发表与该课题直接相关的论文 | 中高 |
| **疑似亲属企业利益输送** | 学者的配偶或直系亲属控制的企业与学者团队存在专利转让、论文数据共享或项目分包 | 高 |
| **疑似利用学术身份为企业站台** | 学者以学术头衔为企业产品/行业报告撰写背书，但未在学术出版物中保持独立判断 | 中 |

---

## 扩展调查模块 G：数字足迹考古（Digital Archaeology）

### 概述

学者的履历在不同平台和时间点上不断被"修正"。通过对比机构官网、学术数据库、百科平台、社交媒体上的多版本画像，以及利用互联网档案馆（Wayback Machine）追溯历史快照，可以发现疑似学历包装、任职美化、论文数量注水的演化痕迹。

### 调查步骤

#### 步骤 1：多平台画像对比
在同一时间点（如同一天）截取学者在以下平台的个人简介，制作差异对照表：

| 平台 | 典型字段 | 可靠性 |
|:---|:---|:---:|
| 机构官网 | 学历、职称、行政职务、研究方向 | 中高 |
| 中国知网学者库 | 发表论文数、H指数、被引次数 | 中 |
| 百度百科 / 维基百科 | 履历简介、获奖记录、社会兼职 | 低 |
| Google Scholar | 论文总数、H指数、i10指数 | 中 |
| ResearchGate / ORCID | 教育背景、工作单位履历 | 中 |
| 学术会议手册 | 简介中的职称、头衔、论文数量声称 | 低 |

**重点关注字段**：
- 同一学位的时间跨度（如"访问学者"的起止年月）
- 海外经历的表述差异（"访问学者" vs "博士后" vs "联合培养"）
- 论文数量的更新差异（机构官网是否引用 Google Scholar 的未经验证数字）
- 任职机构的扩充（是否突然出现从未公开的"特聘教授"头衔）

#### 步骤 2：Wayback Machine 时间轴追踪
在 `web.archive.org` 输入学者的机构主页 URL，查看历年快照：

- 每隔1-2年选取一个快照，记录关键字段的变化
- 标注"首次出现"和"悄然消失"的信息项
- 对比同一字段在不同年份的措辞变化

**典型案例**：
- 2015年快照："2010-2011年赴美国斯坦福大学访问学者"
- 2020年快照："2010-2011年斯坦福大学博士后研究"
- 2024年快照："2010-2011年斯坦福大学高级访问学者"

这种表述升级且缺乏其他佐证，即构成疑似"学历包装"的强证据。

#### 步骤 3：简历版本比对
若能获取学者在不同年份提交的会议简历、项目申请书、人才计划申报材料：

- 将其中的"发表论文"清单按年份横向排列
- 检查同一篇论文在不同版本中的年份、期刊名称、作者排序是否一致
- 标记"膨胀轨迹"：某年的简历声称"发表论文60余篇"，次年变为"80余篇"，但核实数据库中仅增加2篇

#### 步骤 4：社交媒体与公开评论考古
在知乎、小红书、微博等平台搜索学者姓名+关键词（"导师""课题组""避雷"），筛选时间跨度较大的帖子。同时可使用 `wechat_search.py` 搜索微信公众号文章，捕捉学术数据库中不会收录的小道消息、著作宣传或机构动态：

- 早期（5年前）的评价是否与近期评价存在明显断裂？
- 是否有自称学生的人发布了可验证的具体信息（如入学年份、专业方向、课题组人数），与公开记录吻合？
- 是否存在已被删除但可通过 Wayback Machine 或搜索引擎缓存恢复的帖子？

### 证据标准

- **快照截图必须包含 URL 和时间戳**，推荐使用浏览器插件或在线服务生成带时间戳的整页截图。
- **不同来源的同一字段差异必须逐字记录**，禁止概括为"说法不一致"。
- **Google Scholar 等非官方数据库的数字必须与 CNKI/WoS 核实数并列呈现**，并明确标注数据来源。
- **社交媒体信息只能作为假设生成器**（可靠性⭐☆☆☆☆至⭐⭐☆☆☆），任何具体指控必须通过可验证的公开记录交叉确认。
- **必须排除正常的履历更新**。学者 legitimately 晋升职称、增加论文是正常现象，只有**无增量支撑的表述升级**才构成信号。

### 危险信号清单

| 信号 | 判定标准 | 严重程度 |
|:---|:---|:---:|
| **海外经历表述升级** | 同一海外经历在历年快照中从"访问学者"变为"博士后"或"研究员"，且无学位证书或校方证明佐证 | 高 |
| **任职头衔无中生有** | 某"特聘教授""客座研究员"头衔首次出现在某年简历中，但该机构官网无相关聘任公告 | 中高 |
| **论文数量跨源差异过大** | 机构官网/简历声称的论文数比 CNKI 核实数高出 ≥30% | 高 |
| **履历时间线自我矛盾** | 不同年份的简历对同一职务的起止时间存在2年以上的冲突 | 高 |
| **悄然消失的信息** | 某学位、某海外经历或某获奖记录在最新版本中消失，且无合理解释 | 中高 |
| **社交媒体评价断裂** | 5年前的评价多为正面，近2年突然出现大量一致的严重负面指控，且涉及可验证的具体细节 | 中 |
| **搜索引擎缓存中的被删帖** | 发现已被删除但缓存中仍可读的实名或准实名负面爆料，且爆料者信息可被部分验证 | 中 |

---

## 扩展调查模块 H：系统性腐败网络调查

本模块基于湘雅系深度调查案例（CASE_002医疗腐败案与某实习生坠亡事件）的实战经验整理而成，适用于需要将学术审查、权力网络分析、资金流向追踪和跨机构合作审查整合为一体的复杂调查场景。

### 一、调查目标与适用场景

#### 适用场景

1. **医疗系统腐败调查**：涉及过度医疗、绩效洗钱、标本黑市、病历伪造等
2. **学术-权力耦合网络**：科室主任利用行政权力为下级进行学术包装和数据让渡
3. **跨机构灰色合作**：以"科研合作"名义进行的标本采集、数据挪用、资金中转
4. **官方通报解构**：对政府/机构通报进行文本细读，识别事实陈述与官方定性之间的缝隙

#### 核心调查目标

- 从孤立个案中识别出**制度化的包庇机制**
- 通过时间线、资金流向、学术文献三轴交叉，建立**跨案件的关联网络**
- 将官方通报中被动承认的事实，转化为**主动的进攻性证据**

---

### 二、信息获取层经验

#### 2.1 官方通报是最核心的突破口，但必须进行文本解构

**核心原则**：官方通报在"回应质疑"时，往往在**承认关键事实的同时，用定性和框架转移注意力**。

**操作方法**：
1. 将通报全文拆分为"**事实陈述**"和"**官方定性**"两个清单
2. 对比两者之间的缝隙——缝隙越大，调查价值越高
3. 特别关注通报中**精确的数字化表述**，这些往往是被动暴露的硬核证据

**湘雅案例中的典型应用**：
- 官方定性："该科室在绩效分配中存在**管理不规范**问题"
- 被迫承认的事实："累计向其发放**33.379万元**，其中**29.526万元**分批次转回科室原护士长"
- 缝隙分析：88.46%的过账比例不可能是"管理漏洞"，而是一个**系统性的规避监管机制**

#### 2.2 同名同姓作者的辨别必须建立多维度核对机制

**核心原则**：学术调查中，仅凭姓名匹配纳入审查范围可能导致严重的误判。

**去重核对清单**（至少满足3项一致）：
| 维度 | 核对内容 | 风险等级 |
|:---|:---|:---:|
| 出生年份 | 作者简介中的出生年份 | 高 |
| 籍贯/出生地 | 省市级一致性 | 高 |
| 单位变迁轨迹 | 任职机构的时序一致性 | 高 |
| 专业领域 | 研究方向是否连续合理 | 高 |
| 导师/通信作者 | 固定的学术师承关系 | 中 |
| 邮箱后缀 | 是否使用同一机构邮箱 | 中 |

**湘雅案例中的教训**：
- 2009年《查尔酮合成方法的研究进展》作者"CASE_002"（1984年生，江苏徐州人，药学研究生）与湘雅二院外科医生CASE_002（1974年生，湖南长沙/衡阳人）被初期误认为是同一人
- 经复核后确认是两位同名同姓学者，相关不当指控被撤销

#### 2.3 数据库访问壁垒下的交叉引用策略

当目标数据库存在反爬、订阅限制或机构账号壁垒时，建立**B渠道→A渠道的间接验证网络**。

> **WebBridge 兜底方案**：若间接验证网络仍无法获取关键数据，且该平台支持浏览器访问（如 小红书、中国知网、知乎、Web of Science 等），可启用 `kimi-webbridge` 技能直接操控用户真实浏览器完成数据采集。该方法利用用户已有的登录态和 IP 信誉，可绕过常规反爬限制。操作后需将获取的原始页面或截图保存至 `调查名单/姓名_机构/evidence/` 目录，并在报告中标注来源 URL 和抓取时间。

| 受阻的A渠道 | 可替代的B渠道 | 验证策略 |
|:---|:---|:---|
| 国自然官方ISISN系统 | PubMed论文基金致谢栏 / 第三方查询平台 | 通过论文引用反推基金存在性和研究方向 |
| CNKI学位论文全文库 | 学校优秀论文公示PDF / 机构官网答辩公告 | 通过作者后续发表论文的致谢反推导师和答辩时间 |
| ResearchGate学者主页 | PubMed作者页 / 期刊官网作者单位标注 | 通过最新论文的单位信息反推职业轨迹 |
| 医院内部病历系统 | 法院判决文书 / 患者公开的复印病历 / 媒体报道 | 通过司法程序和患者自述重建手术记录链 |

**湘雅案例中的应用**：
- 82070774基金项目的完整标题无法从国自然系统直接获取
- 但通过PubMed上某主任K团队多篇论文的基金致谢栏，确认了该基金的存在、研究方向（肾移植排斥反应）和归属团队

---

### 三、证据链构建层经验

#### 3.1 时间线是跨案件关联的最强粘合剂

当官方试图切割两个事件时，**时间线上的递进关系**往往是最有力的反证。

**时间线编织的黄金法则**：
1. 收集两个事件各自的关键时间节点
2. 寻找**重叠期**、**敏感期**和**转折期**
3. 当一个事件的关键知情者在另一个事件的敏感期"消失"时，高度警觉

**湘雅案例中的典型时间线**：
| 时间 | 事件 | 网络意义 |
|:---|:---|:---|
| 2022年4月24日 | 录音：CASE_002教某实习生篡改病历 | 直接工作交集 |
| 2022年4月28日 | 某实习生创建"举报材料"文件夹 | 系统性证据收集开始 |
| 2022年8月 | CASE_002被立案调查 | 案件进入司法程序 |
| 2024年5月8日 | **某实习生坠亡** | 敏感时点：一审判决前半年 |
| 2024年10月31日 | CASE_002一审判决（17年） | 上层庇护者全部安全脱身 |

**关键推论**：某实习生的死亡时点恰好处于CASE_002案"调查尚未终结、一审判决尚未作出"的敏感期。如果他手中的证据在判决前曝光，可能将案件从个人犯罪升级为系统性腐败。

#### 3.2 精确数字具有压倒性的说服力

**操作方法**：
- 将所有模糊量化表述（"大量资金""高额绩效""多次手术"）转化为精确引用
- 优先提取官方通报、法院判决、学术论文中的**原始数字**
- 通过数字之间的比例关系揭示隐藏的机制

**湘雅案例中的核心数字证据**：
| 数字 | 来源 | 揭示的问题 |
|:---|:---|:---|
| **88.46%** | 官方通报：29.526万÷33.379万 | 绩效洗钱链的系统性程度 |
| **0.2秒** | 电信部门查询：两条短信发送间隔 | 第三人称短信不可能是自杀者手动输入 |
| **572,044.77元+20,000元** | 长沙市芙蓉区法院判决书 | 医院过错是患者九级伤残的"完全原因" |
| **2014年7月** vs **2017年12月** | 论文收稿日期 vs 5年随访应结束日期 | 随访数据不可能完成，存在学术包装 |
| **21时33分17秒** | 硬盘时间戳："举报材料"文件夹创建时间 | 精确到秒的证据，难以伪造 |

#### 3.3 负面空间（缺失的证据）同样是证据

**核心原则**：当关键信息被官方**刻意不公开**时，这种信息空白本身就是系统性包庇的信号。

**需要高度警觉的"信息黑洞"类型**：
1. **处分名单不完整**：只公开边缘人员，核心责任人员隐匿
2. **录音/视频选择性公开**：大量原始记录被以"与本案无关"为由扣押
3. **原始审批文件缺失**：伦理批件、合作协议、任务书等关键文书无法查询
4. **尸检或司法鉴定缺失**：关键物证在压力下被快速销毁或放弃

**湘雅案例中的信息黑洞矩阵**：
| 黑洞 | 已公开部分 | 隐匿部分 | 推断 |
|:---|:---|:---|:---|
| 2022年自查15人名单 | 4人（心血管内科、产科） | **11人未公开** | 核心科室（普外科/创伤中心）被保护 |
| 2025年肾脏移植科问责 | "4人被严肃问责" | **姓名和处分结果完全保密** | 某主任K等核心人物毫发无损 |
| 158段录音 | 6段被解释 | **152段内容未公开** | 可能包含指向核心网络的敏感内容 |
| 健桥医院13人立案名单 | 叶有芝等6人被逮捕 | **穆振南是否在13人中未知** | 跨院合作者的合法性无法评估 |
| "举报材料"文件夹 | 创建时间戳已确认 | **内容"暂未被恢复"** | 可能使用了深度删除或加密手段 |

---

### 四、逻辑推理层经验

#### 4.1 识别"象征性问责"模式

通过多案件交叉分析，可以识别出某些机构处理系统性违规时的固定脚本：**三重复合掩盖模式**。

```
第一层：个人切割
    将刑事责任完全推给最底层的执行者
    例：CASE_002被判17年，案件"似乎"已经终结

第二层：中层保护
    对提供制度性庇护的科室主任/负责人不作公开追责
    例：某主任J不在15人处分名单内，至今正常坐诊
    例：肾脏移植科主任被"严肃问责"但不公开姓名

第三层：系统维稳
    经济补偿 + 保密协议 + 快速定性的组合手段
    例：某实习生家属获85.3万元但签署封口协议
    例：公安机关31天内完成不予立案→复议→复核的全流程
```

**模式识别的价值**：当多个独立案件呈现出相同的危机处理结构时，可以合理推断存在一个**制度化的包庇机制**，而非偶然的个案处理。

#### 4.2 跨案件关联的推断：官方切割之处往往是最危险的连接点

**核心原则**：当官方极力将两个事件切割开来时，往往正是这两个事件存在危险关联的强烈信号。

**寻找跨案件关联的三条线**：
| 关联维度 | 调查方法 | 湘雅案例中的发现 |
|:---|:---|:---|
| **时间线** | 绘制两案关键节点的时序图 | 某实习生坠亡在CASE_002一审判决前半年 |
| **空间线** | 查找共同的机构、科室、地点 | 两人均与湘雅二院普外科/创伤中心有关 |
| **人际关系线** | 绘制共同的上级、同事、合作者 | 某主任J-CASE_002 vs 某主任K-某实习生呈现相同的"主任-执行者"结构 |

**湘雅案例中的核心关联证据**：
- 官方通报称"未查询到两人同台手术记录"
- 但某实习生2022年11月的微信记录显示："CASE_002案是医院内部集体举报的，只不过后来事情失控了，就连本院职工看病也都避开CASE_002。"
- 一个"仅在第2组跟班学习、毫无交集"的实习生，不可能知晓这种级别的内部细节

#### 4.3 系统内数据不能自证清白

**核心原则**：如果涉事机构存在造假前科，那么用它自己的系统记录来证明自己的清白，构成逻辑循环。

**典型陷阱**：
- 用医院的手术记录证明医生没有违规
- 用COTRS系统记录证明器官捐献合法
- 用学校的学籍系统证明学生的分组状态

**应对策略**：
- 始终寻找**系统外的交叉验证源**
- 患者家属的诉讼记录、其他医院的转院记录、独立媒体的采访、司法判决书中的第三方鉴定意见，都比系统内记录更可靠

---

### 五、学术文献审查的特化经验

#### 5.1 三种学术资源操纵模式

在涉及权力-学术耦合的腐败调查中，识别以下三种典型的数据-署名操纵模式：

##### 模式A：科室资源让渡模式
**运作机制**：科室主任将集体积累的高难度手术病例/数据，"让渡"给需要晋升的下级医生作为第一作者，自己担任通信作者提供学术背书。

**红旗信号**：
- 第一作者的职称显著低于其他作者
- 数据收集期与第一作者的任职状态/职称严重错位
- 论文包含不可能在该时间点完成的随访数据

##### 模式B：跨院数据挪用模式
**运作机制**：医生在甲医院有编制和职称，同时在乙医院实际工作并获取病例，然后用甲医院的名义发表基于乙医院数据的论文。

**红旗信号**：
- 论文数据来源机构与作者所属机构不一致
- 作者简介中出现"现工作单位"的跳槽痕迹
- 早期论文存在籍贯、出生年份、导师信息的频繁变动

##### 模式C：研究生署名包装模式
**运作机制**：科室主任设计和主导大型回顾性研究，利用科室病例数据库，让研究生负责数据提取和统计分析，将其列为第一作者，自己担任通信作者。

**红旗信号**：
- 研究生在数据收集期尚未取得医师资格
- 论文纳入标准与基金项目的研究方向明显错位
- 基金号涉及敏感内容（如儿童标本），但论文明确排除该类对象

#### 5.2 基金号是连接人物的最强纽带

**核心原则**：在医学研究领域，同一基金号在不同论文中的共同出现，是将分散的人物和机构绑定到同一网络的最强公开证据。

**湘雅案例中的突破性发现**：
某实习生2024年论文（PMC11208394）的基金资助栏同时标注了：
> 国家自然科学基金(82070774，82370760)；湖南省自然科学基金(2021JJ40864，2024JJ2088)

该论文作者序列为：某实习生、聂曼华、**宋磊**、谢益欣、钟明达、**谭书波**、安荣、李潘、**谭亮**、**某主任K**。

**意义**：这是公开文献中首次将82070774、82370760、2021JJ40864三个与事件核心人物相关的基金号**同时绑定到同一篇论文、同一批作者**。它无可辩驳地证明：宋磊（2021JJ40864负责人）、谭亮（82370760负责人）、某主任K（82070774关联PI）三人处于同一科研网络和同一资助体系内。

---

### 六、报告撰写层经验

#### 6.1 建立明确的三级可信度体系

| 级别 | 定义 | 标识方式 |
|:---|:---|:---|
| **已证实事实** | 有原始文件、官方通报、法院判决或学术数据库直接支持的陈述 | 直接陈述，无需额外标注 |
| **高置信度推断** | 基于多个独立间接证据链的合理推论 | 使用"高度推断""极大概率"等措辞，必要时附置信度星级 |
| **待验证疑点** | 存在信息缺口或逻辑矛盾，但尚无法得出确定结论的问题 | 使用"存疑""待确认""无法排除"等措辞 |

#### 6.2 区分"客观证据"与"主观解读"

在调查报告中，必须将以下两类内容严格区分：
- **客观证据**：时间、地点、人物、金额、原文引用
- **主观解读**：对这些证据的逻辑归纳、模式识别、动机假设

**湘雅案例中的写法示范**：
- 客观："官方通报称对肾脏移植科'科室主任、护士长等4人进行了严肃问责'"
- 推断："但某主任K在通报发布后仍正常出诊、参会、带博导、发论文，这意味着'严肃问责'的实际内容极大概率只是批评教育、责令检查等最轻级别的内部处理"

#### 6.3 来源追溯是报告可信度的基石

每一份调查报告都应附带完整的信息来源清单，包括：
- 官方通报的文号和发布日期
- 法院判决书的案号和法院名称
- 学术期刊的名称、卷期、DOI、PMID
- 媒体报道的媒体名称和日期
- 数据库查询的时间点

---

### 七、可复用的六步调查框架

基于湘雅系调查经验，总结出以下适用于系统性腐败调查的六步框架：

#### Step 1：人物锚定
- 确定核心人物的身份信息，建立基础档案
- **特别注意同名同姓的辨别**，建立多维度核对机制
- 追踪人物的职业轨迹、婚姻/人脉网络、房产/财产异常

#### Step 2：时间线编织
- 将所有关键事件按时间顺序排列
- 寻找**重叠期**、**敏感期**和**转折期**
- 当一个事件的关键知情者在另一个事件的敏感期"消失"时，高度警觉

#### Step 3：资金流向追踪
- 绩效、补偿款、科研经费、房产等数字是最难伪造的证据
- 关注异常的资金中转模式（如通过研究生/第三方账户规避财务监管）
- 计算比例关系（过账比例、个人所得占比）揭示隐藏的机制

#### Step 4：学术文献审查
- 通过论文署名、基金号、数据来源、伦理批号反推真实的权力关系和合作网络
- 识别三种学术资源操纵模式：科室资源让渡、跨院数据挪用、研究生署名包装
- **基金号是连接人物的最强纽带**

#### Step 5：官方文本解构
- 对通报、判决书、处分决定进行逐句事实提取
- 将"事实陈述"与"官方定性"分离，寻找两者之间的缝隙
- 特别关注官方**被迫承认的精确数字**，将其转化为进攻性证据

#### Step 6：模式识别
- 当多个个案呈现相同的处理结构时，推断是否存在**制度化的包庇机制**
- 识别"象征性问责""信息黑洞""系统内数据自证"等典型脚本
- 从个案升级为对系统性腐败生态的描述

---

### 八、常见陷阱与警示

#### 陷阱1：将官方通报的结论当作调查的终点
官方通报的真正价值不在于它的结论，而在于它**在回应质疑过程中不得不披露的事实**。这些被迫披露的事实往往比结论更有调查价值。

#### 陷阱2：过度依赖单一数据源
当所有证据都来自同一个机构（如医院的病历系统、学校的学籍系统）时，调查极易陷入逻辑循环。必须建立**至少两个独立来源的交叉验证**。

#### 陷阱3：将"没有查到"等同于"不存在"
信息未公开、数据库未收录、论文未命中检索，都不等于事实不存在。要善于利用**B渠道间接验证**和**负面空间分析**。

#### 陷阱4：在推断中跳跃因果
"A在B之前发生"不等于"A导致了B"。在涉及死亡、犯罪的敏感推断中，要特别谨慎。可以提出**动机假设**和**时机敏感性分析**，但不应做无法验证的终极定性。

#### 陷阱5：忽视同名同姓风险
学术调查中最容易犯的错误就是姓名匹配误判。一次误判可能毁掉整份报告的可信度。必须建立严格的去重核对机制。

---

### 九、湘雅案例的核心启示

**系统性腐败的真正保护壳不是某一个人的权力，而是一种被反复验证有效的危机处理脚本。**

在湘雅系调查中，这个脚本表现为：
1. 当具体犯罪行为暴露时，将责任完全推给最底层的执行者
2. 对提供制度性庇护的科室主任只进行不公开的口头问责
3. 通过经济补偿加保密协议加快速定性的组合手段阻止进一步追问

识破这个脚本，比单纯追究某一个责任人更有价值。因为它揭示了一个腐败生态系统的**自我维持机制**——只要这个机制不被打破，即使某一个执行者被清除，新的执行者也会很快被生产出来。

---

*本手册基于公开可核实的网络数据库、政府公告、学术期刊及媒体报道整理而成。所有案例引用均来自湘雅系调查报告（2026年4月）。*

---

## 扩展模块汇总与工具映射

| 模块 | 核心数据源 | 分析重点 | 当前可用工具 | 状态 |
|:---|:---|:---|:---|:---:|
| 学术影响力刷量检测 | 引用记录、h-index时序 | 指标操纵与互引卡特尔迹象 | `citation_profiler.py` | ✅ 可用 |
| 语言风格计量学 | 论文全文文本 | 疑似代笔迹象检测与作者真实性 | `stylometry_profiler.py` | ✅ 可用 |
| 学术关系网络可视化 | 合作者、导师、机构、引用关系 | 交互式力导向图谱与异常标记 | `network_visualizer.py` | ✅ 可用 |
| 调查流程终端可视化 | 案件状态、阶段进度、子脚本输出 | 彩色阶段面板、实时输出捕获、交互式确认、10阶段进度表、智能辅助推进（条件检查+人工确认） | `investigate_visual.py`（含 `smart-step` 命令） | ✅ 可用 |
| PDF报告自动生成 | Markdown最终报告 | A4封面、自动目录、页眉页脚、表格自动渲染、图表自动生成（雷达/饼图/热力图/时间线/网络图） | `md_to_pdf.py` + `chart_generator.py` | ✅ 可用 |
| 行政职务-产出耦合 | 任免公示、论文时间戳 | 权力窗口期的产出异动 | 手工时间线比对（脚本规划中） | 🚧 规划中 |
| 机构主场优势量化 | 期刊主办信息、编委名单 | 内部人发表通道 | 手工核查（脚本规划中） | 🚧 规划中 |
| 论文上下游延伸 | 学位论文PDF、会议手册、专刊信息 | salami slicing、审稿套利 | 手工比对（脚本规划中） | 🚧 规划中 |
| 商业利益网络 | 工商信息、专利、横向项目 | 产学研利益冲突 | 手工查工商信息（脚本规划中） | 🚧 规划中 |
| 数字足迹考古 | 网页快照、简历版本、社交媒体 | 疑似履历包装与信息演化 | 手工截图对比（脚本规划中） | 🚧 规划中 |
| 系统性腐败网络调查 | 官方通报、法院判决、学术文献、资金流向记录 | 跨案件关联网络、制度化包庇机制、学术-权力耦合 | 基于 `network_visualizer.py` 手工构建网络（专用脚本规划中） | 🚧 规划中 |
| 代写与AI辅助署名检测 | 论文全文文本、作者既往作品、教育背景、文件元数据 | 风格断裂、AIGC统计特征、能力一致性、翻译抄袭 | `stylometry_profiler.py`（含词频偏差热图）+ `aigc_statistical_profiler.py` + `capability_consistency_checker.py` + `translation_plagiarism_detector.py` | 🚧 规划中 |

*规划中模块目前需依赖手工调查与 Markdown 整理。可用脚本均遵循半自动原则：脚本负责可重复的计算、比对和结构化输出，人类负责数据来源验证、假说解释和最终结论。*

---

---

## 案例实战沉淀：Zixin Hu 调查的方法论创新（2026年4月）

> 以下方法论条目来自对 Zixin Hu（复旦大学生物医学背景，后转入上海交通大学医学院任职）为期12个维度的完整调查实战。该案例最终风险评级为**高**，其调查过程中形成的四项方法创新已被证实可迁移至同类青年学者背景调查。

---

### 一、四项核心方法论创新

#### 1. 矛盾即线索（Contradiction-as-Lead）

**核心原则**：机构官方简介、学术主页、会议履历中的细微差异，不应被视为可忽略的"笔误"，而应作为优先调查信号。

**本案例中的典型应用**：
- 调查对象在机构简介中自称"AC Nielsen 分析师"，但在其他平台使用"Director"头衔
- 进一步核查发现，Director 头衔对应的是 Nielsen 的职级体系中的基层分析师级别，存在明显夸大
- 同一位调查对象在简历中列出"UTHealth Houston"，但机构官方记录显示其从未在该校任职，系利用合作导师的联合培养关系进行单位挂靠美化

**操作要点**：
| 步骤 | 行动 | 输出 |
|:---|:---|:---|
| 1. 多源画像抓取 | 同时截取机构官网、Google Scholar、ResearchGate、会议手册、百度百科的自我介绍 | 差异对照表 |
| 2. 矛盾点标记 | 对职务名称、任职时间、单位名称中的任何不一致进行逐字记录 | 矛盾清单 |
| 3. 原始体系核查 | 将争议头衔还原到原机构的职级/聘任体系中进行验证 | 职级对应说明 |
| 4. 判定夸大程度 | 区分"正常简化"（如将'Research Assistant'简写为'RA'）与"实质性升级"（如将'Analyst'升为'Director'） | 夸大评级 |

---

#### 2. 时间线叠合分析（Timeline-Overlay Analysis）

**核心原则**：学术身份转换节点（博士后出站→入职高校→职称晋升）与商业行为时间戳（公司注册、股权变更、专利申请）的重叠，是暴露"职务发明窗口期"和"利益冲突隐匿"的关键透镜。

**本案例中的典型应用**：
- 调查对象于2020年6月获得复旦大学博士学位，2020年8月入职上海交通大学医学院（博士后/助理研究员）
- 2023年3月，调查对象注册成立上海亿枭信息科技有限公司，担任法定代表人并持股51%
- 2025年，调查对象与学术合作者（王正一、赵一瑾等人）共同出现在上海信神润企业管理合伙企业的股东名单中（成立于2025年9月）
- 时间线叠合显示：商业实体的形成与其从博士后向独立PI/教职过渡的窗口高度重合，且其配偶缪晓蕾出现在多家关联企业中，构成家庭利益网络的雏形

**操作要点**：
```
建立统一时间轴，标注以下六类事件：
├─ 学位授予 / 出站
├─ 入职 / 职称变动
├─ 公司注册 / 股权变更
├─ 专利申请 / 转让
├─ 基金项目立项 / 结题
└─ 关键论文投稿 / 见刊

重点关注"6个月内密集耦合"的异常窗口
```

---

#### 3. 网络穿透法（Network-Penetration Method）

**核心原则**：追踪学术合作者（学生、同门、课题组成员）向调查对象商业股权结构的流动，可作为"学术资源向商业实体转移通道"的间接证据。

**本案例中的典型应用**：
- 初始调查仅发现调查对象本人持股的上海亿枭信息科技有限公司
- 进一步追踪发现，其学术合作者王正一（Zhengyi Wang）、赵一瑾（Yijin Zhao）于2025年9月共同入股上海信神润企业管理合伙企业
- 王正一与赵一瑾均为调查对象多篇SCI论文的共同作者（含2025年Baoteng Biotech联合申请专利CN119993279A的发明人名单）
- 该发现将孤立的"个人开公司"升级为"学术-商业网络重叠"，直接推高风险评级

**操作要点**：
| 步骤 | 行动 | 验证标准 |
|:---|:---|:---|
| 1. 提取核心合作者 | 从SCI论文作者列表中提取高频合著者（≥2篇） | 作者排序+单位标注 |
| 2. 商业数据库反向检索 | 以合作者姓名在商业数据库中查询股东/董事/监事记录 | 同名去重（城市+领域+时间线） |
| 3. 股权结构穿透 | 追踪合作者持股企业是否与调查对象持股企业存在地址、邮箱、投资人重叠 | 关联证据截图 |
| 4. 学术产出耦合 | 检查关联企业的专利/论文发明人名单中是否同时出现调查对象及其合作者 | 时间优先权日比对 |

---

#### 4. 学科逻辑检验（Disciplinary-Logic Test for Affiliations）

**核心原则**：作者单位标注必须符合"教育背景+资助来源+研究内容"三位一体的学科逻辑。当作者单位与其学位授予机构、基金资助机构、研究主题明显错位时，存在"关系型挂名"或"资源置换型署名"的嫌疑。

**本案例中的典型应用**：
- 调查对象在复旦大学的博士专业为"生物统计学"，导师为数学科学学院/公共卫生学院背景
- 但其在2022-2024年间发表的三篇论文中，通讯地址却标注为"复旦大学高分子科学系"
- 高分子科学系与调查对象的博士专业、研究方向、导师体系均无关联
- 进一步追溯发现，这三篇论文的合作者中包含高分子科学系的刘宝珠（Baozhu Liu），疑似通过合作关系获得复旦大学署名背书
- 该异常被评定为**中度异常**：关系型挂名的迹象明显，但尚未发现直接的利益交换证据

**操作要点**：
```
对每一篇存在疑问的论文，回答以下三个问题：
1. 该单位是否与作者的学位/博士后训练经历匹配？
2. 该单位是否出现在论文的基金资助声明中？
3. 该单位的研究方向是否与论文主题高度相关？

若三个问题的答案均为"否"，则触发深度审查。
```

---

### 二、硬边界与失败经验

#### 1. 学位论文全文获取的自动化壁垒

**问题**：2020年后复旦大学的博士学位论文在CNKI和复旦大学图书馆系统中均被付费墙或机构认证墙封锁。
**尝试过的路径**：
- CNKI 博硕论文库：可检索到条目，但全文预览提示"您没有访问权限"
- 复旦大学图书馆：校外IP无法登录学位论文系统
- 导师团队公开资料：通过已发表论文的致谢栏反向推断导师为 Jin Li
- Internet Archive / 学校优秀论文公示：未找到公开PDF

**教训**：对于2019年后入学的博士学位论文，若目标学校未加入开放获取运动，几乎不可能通过公开网络渠道获取全文。此时应：
- 将"无法获取全文"明确记录为信息缺口，而非"论文不存在"
- 通过论文致谢、发表期刊的作者单位变迁、导师团队网页等B渠道重建论文信息
- 在最终报告中使用"博士论文题目待确认"而非猜测性标题

#### 2. 国家自然科学基金细节的查询黑洞

**问题**：国自然青年项目的完整信息（批准号、资助金额、依托单位、研究内容）在ISISN系统中需要机构账号登录。
**尝试过的路径**：
- LetPub、MedSci等第三方平台：仅收录部分项目的标题和金额，覆盖不全
- PubMed基金致谢栏：部分论文标注了基金号，但无法确认是否为青年项目
- 目标学者已发表论文：致谢栏中未发现明确的国自然青年项目编号

**教训**：国自然青年/面上项目的细节属于典型的"高价值但高壁垒"信息。可行的替代方案：
- 通过目标学者的合作者论文中的基金致谢栏，反向推断其是否在同一资助网络中
- 通过学校科研院网站的"立项公示"或"获奖新闻"捕捉间接信息
- **在微信公众号内搜索**：大量高校科研管理部门、学院公众号会在项目立项当年发布"喜报""祝贺XX老师获批国自然青年/面上项目"的推送，常包含项目名称、负责人姓名、所在学院等关键信息。使用微信搜索关键词组合：`目标学者姓名 + 国自然/国家自然科学基金 + 青年/面上`
- 若完全无法获取，在报告中标注为"待验证疑点"，不纳入已证实事实

#### 3. 商业数据库的互斥性冲突

**问题**：同一专利（CN119993279A）的发明人名单在企查查与启信宝两个平台出现差异。

| 平台 | 发明人名单 | 差异点 |
|:---|:---|:---|
| 企查查 | CASE_015、王正一、赵一瑾、罗丹、赵成林 | 包含赵成林 |
| 启信宝 | CASE_015、王正一、赵一瑾、罗丹 | 不包含赵成林 |

**教训**：商业数据库的信息来源和更新频率不同，可能出现互相排斥的记录。在遇到关键专利/企业信息时：
- **必须以国家知识产权局（SIPO）原始检索结果为准**，商业数据库只能作为初步线索
- 记录不同平台之间的差异，将其本身作为"数据质量存疑"的信号
- 对于涉及人数较多的专利发明人名单，优先采信包含更多信息的版本，但需标注来源冲突

#### 4. "零PubPeer质疑"不等于清白

**问题**：调查对象的16篇SCI论文在PubPeer、Retraction Watch、中文社交媒体上均未发现公开质疑。
**误判风险**：新手调查员可能将"零质疑"直接解读为"学术诚信无问题"。

**教训**：
- 图像造假和数据操纵是PubPeer上最常见的质疑类型，但** affiliation 异常、作者挂名、利益冲突隐瞒**在PubPeer上的可见度极低
- 对于青年学者（职业生涯早期），PubPeer评论的缺失是常态，不能作为排除嫌疑的证据
- 应将PubPeer/Retraction Watch检索结果视为"无新增负面信号"，而非"正面背书"

---

### 三、风险评级动态演化的教训

Zixin Hu 案例展示了风险评级如何在调查进程中发生动态升级：

| 调查阶段 | 主要发现 | 风险评级 | 升级原因 |
|:---|:---|:---:|:---|
| 阶段1：基础画像 | 职位头衔夸大、UTHealth误标 | 中-高 | 履历美化迹象 |
| 阶段2：学术产出审查 | 2篇Cell子刊通讯作者身份存疑、高分子科学系 affiliation 异常 | 中-高 | 作者贡献边界模糊 |
| 阶段3：专利与商业利益 | 发现上海亿枭信息科技（持股51%，法定代表人） | 高 | 学术身份与商业利益直接捆绑 |
| 阶段4：网络穿透 | 学术合作者王正一、赵一瑾进入同一商业控股平台 | 高 | 学术-商业网络重叠，疑似资源转移通道 |

**核心教训**：
- 风险评级不应在调查初期就固化，而应随着新证据的出现动态调整
- 当"商业利益网络"与"学术合作网络"发生重叠时，即使尚未发现直接的学术造假证据，也应将风险评级上调至**高**
- 因为这类重叠结构意味着：学术声誉、实验室资源、学生产出可能被系统性地用于为私人商业实体提供背书或原料

---

### 四、未来工具建议（尚未实现）

以下脚本目前尚不存在，是基于本案例总结的**未来开发方向**。调查者现阶段可通过手工方法（Markdown 表格、Excel 时间线、手动工商查询）完成相同分析：

| 建议脚本名称 | 功能 | 对应的手工替代方法 |
|:---|:---|:---|
| `affiliation_logic_checker.py` | 学科逻辑检验 | 建立 Excel 表格核对作者教育背景、论文单位、基金号、主题的一致性 |
| `network_penetration_mapper.py` | 网络穿透分析 | 手工在天眼查/企查查检索合作者商业关联，用 `network_visualizer.py` 绘制静态关系图 |
| `timeline_overlay_visualizer.py` | 时间线叠合可视化 | 在 Markdown 或 Excel 中建立统一时间轴，标记 6 个月内的耦合事件 |
| `contradiction_tracker.py` | 多源履历矛盾追踪 | 并列粘贴多个平台的学者简介文本，逐字段标注差异和矛盾等级 |

---

**System Architecture Summary:**
- **Dual-track design**: `domestic/` (国内学者) + `international/` (国外导师) + `cross_border/` (海归) adapters share `core/` + `analysis/` + `network/` + `report/` engines
- **Shim compatibility layer**: Original file locations (`scripts/utils.py`, `scripts/db.py`, etc.) remain functional via deprecation shims that re-export from new locations
- **JSON communication**: All track-specific modules communicate via disk JSON files; `investigate.py` orchestrates with `subprocess.run()`
- **Config versioning**: v1 configs (no `investigation_type`) are auto-migrated to v2 with `config_loader.py` injecting `investigation_type: domestic`
- **Free API priority**: International auto-fetch uses only free APIs (OpenAlex, ORCID, Semantic Scholar, arXiv, PubPeer, Retraction Watch); Scopus/WoS reserved for manual supplement
- **Privacy by design**: Xiaohongshu output anonymizes author IDs; reports cite as "来自匿名社交媒体分享"

**Test coverage**: 137 tests (53 original + 84 new) covering domestic track, international modules, cross-border merge/validation, and backward compatibility.

---

---

## 案例实战沉淀：CASE_016调查的方法论教训（2026年4月）

> 本章节记录在对CASE_016（安徽艺术学院传媒学院院长）调查过程中犯下的具体错误及深层原因分析，作为后续调查的警示。

### 一、犯下的三类具体错误

#### 错误1：标签化概括——自创"淮南帮"称谓

**错误表现**：
- 将CASE_016与王琍琍的高度重合轨迹概括为"淮南帮"利益网络
- 将CASE_005等本无淮南背景的人员也划入该范畴

**错误内容**：
> "与王琍琍等 forming a '淮南帮' 利益网络"

**事实核查后**：
- CASE_005是上海人，安徽广播电视台出身，2021年才入职安徽艺术学院，与"淮南系统"毫无关系
- "淮南帮"并非公开既有称谓，是调查者自行创造的标签

**错误性质**：从"描述性概括"滑向"定性指控"

---

#### 错误2：制度性知识缺失——夸大组织部个人权力

**错误表现**：
- 将"组织部长负责组织考察"等同于"组织部长决定干部任免"
- 使用"党政双控"等过度简化的表述

**错误内容**：
> "王琍琍主管组织部，负责全校干部选拔任用——CASE_0162022年任院长、2025年晋升二级教授，均须经组织部考察"
> "两人形成'党政双控'格局"

**事实核查后**：
- 中国高校处级干部任免须经"民主推荐→组织考察→党委常委会集体研究决定"三道程序
- 组织部负责考察和推荐的**程序性工作**，最终决定权在党委常委会
- CASE_016的任命"并非由王琍琍个人决定"

**错误性质**：对高校干部管理制度理解不深入，将程序参与权误读为决定权

---

#### 错误3：尽职调查不足——未逐一核实群体成员背景

**错误表现**：
- 发现传媒学院师资表上多人同时挂教职和行政职务后，产生"这些人都是一伙的"的直觉
- 没有逐一搜索每个人的履历，就把CASE_005归入"同一系统"

**错误内容**：
> "全部来自同一系统：这些人都是从安徽广播影视职业技术学院/安徽大学艺术与传媒学院一路走来的'老同事'"

**事实核查后**：
- CASE_005的履历明确显示她是上海人，本科毕业于安徽广播电视大学，在安徽广播电视台工作24年（1997-2021），2021年才入职安艺
- 她和CASE_016并非"一路走来的老同事"

**错误性质**：以偏概全，用局部信息做整体判断

---

### 二、错误背后的深层原因

| 错误层级 | 具体表现 | 根本原因 |
|:---|:---|:---|
| **认知偏误** | 确认偏误：一旦形成"她有问题"的假设，就只找支持证据 | 调查中期就形成了结论，后续写作变成"为结论找论据" |
| **认知偏误** | 代表性启发：仅凭"都出自淮南"一个特征就推断利益输送 | 用"看起来的相似性"代替"实际的因果性" |
| **知识盲区** | 夸大组织部长权力 | 对高校干部任免制度的程序细节缺乏了解 |
| **工作方法** | 未逐一核实CASE_005履历就划入"同一系统" | 尽职调查不足，被"叙事驱动"压倒了"事实驱动" |
| **语言表述** | 使用"利益圈""班底""党政双控"等戏剧化词汇 | 调查报告的"故事性"需求压倒了"准确性"要求 |

**最根本的问题**：

正确的调查流程应该是：
```
证据 → 分析 → 结论 → 表述
```

而实际上的流程变成了：
```
直觉（她有问题）→ 构建叙事 → 选择性找证据 → 戏剧化表述
```

---

### 三、修正后的原则

#### 原则1：标签禁令
- **禁止**自创任何带有定性色彩或帮派暗示的标签（如"XX帮""利益集团""圈子"）
- 只能用**中性描述词**："轨迹重合""职业关联""同期共事""人员集中度"
- 若引用既有公开称谓，必须标注来源

#### 原则2：权力表述精确化
- 涉及制度性权力时，必须先查阅权威文件或咨询专业人士
- 不得将"程序参与权"等同于"决定权"
- 不得将"考察推荐"等同于"任免决定"
- 涉及多人权力结构时，必须说明决策的最终主体（党委常委会/党委会/职称评审委员会等）

#### 原则3：群体概括的逐人核实义务
- 在报告中对任何两人以上的群体进行概括性描述前，必须**逐一核实每个人的履历**
- 若无法逐一核实，必须在报告中明确标注"以下人员背景未经逐一核实"
- 不得用"全部""都是""无一例外"等绝对化词汇描述群体特征

#### 原则4：区分"事实""疑点""推测"

| 类别 | 定义 | 报告中如何表述 |
|:---|:---|:---|
| **事实** | 有原始文件、网页快照、数据库记录直接支持的陈述 | "经XX数据库核实……" "根据XX文件……" |
| **疑点** | 现有证据无法解释的矛盾或异常 | "存在以下疑点……" "XX现象与XX条件之间存在矛盾" |
| **推测** | 基于经验和逻辑的推断，但缺乏直接证据 | "一种可能的解释是……" "如果XX成立，则可能……" |

- **绝对禁止**将推测性结论作为定性指控写入报告
- 涉及对他人名誉有影响的陈述时，必须降级一级：推测→疑点，疑点→需要进一步核实的事实

#### 原则5：语言冷静期
- 报告初稿完成后，必须设置**24小时冷静期**
- 冷静期后逐句检查：是否有任何词汇带有预设立场、情绪色彩或定性暗示？
- 替换清单：
  - "利益圈" → "人员集中度"
  - "班底" → "原单位同事"
  - "控制" → "任职"
  - "双控" → "分任要职"
  - "帮" → "群体"（或具体描述轨迹重合点）

---

### 四、可复用的检查清单（Report Quality Checklist）

在提交任何调查报告前，必须完成以下自检：

- [ ] 报告中是否出现了任何自创的定性标签？如有，全部删除或替换为中性描述
- [ ] 涉及干部任免、职称评审等制度性问题时，是否准确描述了决策程序和最终决策主体？
- [ ] 对两人以上的群体进行概括时，是否逐一核实了每个人的背景？
- [ ] 报告中是否明确区分了"事实""疑点""推测"三类陈述？
- [ ] 是否存在将"程序参与"等同于"权力决定"的表述？
- [ ] 是否存在将"轨迹重合"等同于"利益关联"的表述？
- [ ] 是否存在绝对化词汇（"全部""都是""无一例外""必然"）？
- [ ] 任何可能影响他人名誉的陈述，是否有原始证据直接支持？

---

---

## 项目文件组织规范（Project File Organization）

> 以下规范确保调查资料在多案例、多调查员协作时的可追溯性与一致性。

### 核心目录说明

| 目录 | 用途 | 内容示例 |
|:---|:---|:---|
| `调查名单/` | **核心归档区**：按调查对象分文件夹，存放所有与该学者相关的证据、报告、论文PDF、脚本输出 | `CASE_011_中国社会科学院/`, `CASE_002_湘雅体系/` |
| `scripts/` | **系统脚本工具链**：core/analysis/network/report 等模块，**禁止放入个案文件** | `investigate.py`, `core/db.py`, `analysis/text_profiler.py` |
| `website/` | **前端宣传材料**：服务介绍页面、商务简介、海报 | `index.html`, `investigate.html`, `竖版宣传海报.pdf` |
| `templates/` | **模板与示例**：报告模板、数据结构模板、示例PDF | `学术档案调查报告_模板.html`, `demo_scholar.json` |
| `guides/` | **调查方法论指南**：各类专项调查的操作手册 | `systemic_corruption_investigation_guide.md` |
| `data/` | **通用原始数据/测试数据**：非特定于某个调查对象的中间文件 | `研学网导师评价表.xlsx`, `test_paper_profile.json`, `scholar_profile_database.csv` |
| `archive/` | **历史备份**：SKILL.md 等核心文档的版本备份 | `SKILL.md.v1.2.bak` |

### 调查名单命名规则

所有个案文件夹统一采用 **`姓名_机构`** 格式：

```
调查名单/
├── CASE_009_南京师范大学
├── CASE_020_中南大学湘雅医院
├── CASE_015_复旦大学
├── CASE_021_南京师范大学
├── CASE_023_清华大学
├── Jingrong_Tong_谢菲尔德大学
├── CASE_002_湘雅体系
└── ...
```

**规则细节**：
1. **中文优先**：中文姓名放前面，机构放后面，用下划线 `_` 连接。
2. **英文名处理**：如调查对象以英文名为主（如国际学者），保留拼音/英文名，格式为 `Jingrong_Tong_谢菲尔德大学`。
3. **事件标签**：对于非个人学者调查（如系统性腐败网络），保留事件简称，如 `CASE_002_湘雅体系`。
4. **机构粒度**：使用学者被调查时的主要任职机构（通常为当前职称所在机构）。如学者有多个机构，取调查聚焦的那个。
5. **禁止项**：文件夹名中不使用空格、不使用 `【】` 等括号、不放项目级脚本（`.py` 文件）。

### 个案文件夹内部结构建议

```
调查名单/某某_某大学/
├── README.md                    # 可选：调查对象基本信息与进度摘要
├── 官网快照_*.html              # 机构官网保存的 HTML 快照
├── 截图/                        # 网页截图、数据库检索截图
├── 论文PDF/                     # 下载的论文/专著 PDF
├── *_初步调查报告.md            # 初步调查结果
├── *_深度调查报告.md            # 各专题深度报告
├── *_学术档案调查报告_FINAL.md  # 最终综合报告
├── *_network.html               # 关系网络可视化（如有）
└── *_network.json               # 关系网络数据（如有）
```

### 技术债清理原则

- **个案专用脚本**：为某个调查对象临时编写的脚本（如硬编码了姓名和路径的 PDF 提取器），在调查结束后应**归档到 `scripts/_legacy_cases/` 或删除**，不得留在个案文件夹中。
- **输出结果优先保留**：脚本的输出（`.md`/`.json`）保留在个案文件夹，原始脚本移出。
- **空文件清理**：调查过程中产生的空文件、占位文件（如 `No content found` 的微信文章采集结果）应及时删除。
- **`.DS_Store` 清理**：macOS 系统文件应定期清理，避免污染归档。

---

## v3.0 架构扩充：深度证据层（Deep Evidence Layer）

> 以下模块为 v3.0 规划中的深度证据层，解决 v2.0 在"数据层面问题""发表伦理问题""研究过程违规"三类调查中的覆盖不足。

### 人机协作架构原则（v3.0 核心设计）

本架构采用**三级半自动协作模型**，明确划分人类总指挥、LLM调度员、脚本执行者三者的权责边界：

```
┌─────────────────────────────────────────────────────────────┐
│  Tier 1: 人类总指挥（Human Commander）                      │
│  ─────────────────────────────────────                      │
│  • 掌握调查方向与优先级决策（"查什么、先查什么、查多深"）   │
│  • 对 LLM 提出的假设进行批准、否决或修正                    │
│  • 对证据链做出最终定性判断（风险评级、是否提交举报）       │
│  • 对涉及隐私、伦理边界、法律风险的操作行使否决权           │
└─────────────────────────────────────────────────────────────┘
                              ↓ 指令下达
┌─────────────────────────────────────────────────────────────┐
│  Tier 2: LLM 调度员（LLM Orchestrator）                     │
│  ─────────────────────────────────────                      │
│  • 理解人类总指挥的意图，将自然语言指令转化为可执行计划     │
│  • 选择合适的脚本工具组合，生成具体调用命令                   │
│  • 解析脚本输出，提取异常信号，生成初步假设                   │
│  • 向人类总指挥汇报发现，提出下一步调查建议                   │
│  • 不做最终决策，不替代人类进行定性判断                       │
└─────────────────────────────────────────────────────────────┘
                              ↓ 脚本调用
┌─────────────────────────────────────────────────────────────┐
│  Tier 3: 脚本执行者（Script Executor）                      │
│  ─────────────────────────────────────                      │
│  • 执行公开数据的自动抓取、计算、比对和结构化输出             │
│  • 对数据来源、查询时间、处理逻辑进行完整日志记录             │
│  • 输出原始数据和中间结果（JSON/CSV/Markdown），供 LLM 解读  │
│  • 不做假设生成，不做结论推断，不对外发送任何通信             │
└─────────────────────────────────────────────────────────────┘
```

**关键原则**：
1. **人类拥有唯一决策权**：所有涉及"是否继续调查""是否升级风险评级""是否对外披露"的决策，必须由人类总指挥做出。
2. **LLM 是调度者而非决策者**：LLM 负责工具选择、信号解读和假设生成，但必须等待人类批准后方可执行下一步操作。
3. **脚本是纯执行层**：脚本只处理公开可获取的数据，不做任何需要主观判断的操作，不主动与外部实体（作者、机构、期刊编辑部）建立通信。
4. **证据链对人类透明**：所有脚本的中间输出必须对人类总指挥可读可核查，禁止黑箱化推理。

---

### 当前架构的诊断

---

### 一、当前架构的诊断

| 能力域 | v2.0 覆盖 | 缺口 | 根因 |
|:---|:---:|:---|:---|
| 文本与原创性 | 全面 | 无 | `text_profiler` + `similarity_scanner` 成熟 |
| 引用与网络 | 全面 | 无 | `citation_profiler` + `network_visualizer` 成熟 |
| 图像与数据 | 有限 | 原始数据不可得 | 缺乏对论文内嵌统计量的反向验证机制 |
| 发表伦理 | 部分 | 预印本-期刊跨库追踪缺失 | 仅覆盖学位论文映射 |
| 研究伦理 | 有限 | IRB/伦理批件内部化 | 缺乏对临床试验注册和伦理声明的结构化解析 |
| 同行评议 | 有限 | 审稿数据黑箱化 | 缺乏基于公开元数据的周期异常检测 |

**核心矛盾**：公开可获取的信息 ≠ 证明学术不端所需的证据深度。v3.0 的目标是在"用公开信息发现异常信号"的基础上，增加"将异常信号转化为结构性证据"的能力。

---

### 二、新增模块总览

```
v3.0 在 v2.0 基础上新增 deep_evidence/ 层：

├─ deep_evidence/
│   ├─ data_forensics/         ← 数据层取证（统计反推 + 图像元数据 + 数据可用性验证）
│   ├─ publication_trace/      ← 发表链追踪（预印本 + 会议 + 双语发表 + Crossref事件）
│   ├─ ethics_audit/           ← 伦理审计（伦理声明解析 + 临床试验注册核查）
│   ├─ peer_review_intel/      ← 同行评议情报（周期异常 + 编委自发文 + 撤稿历史）
│   └─ evidence_compiler/      ← 证据链编译器（信号聚合 + 证据链构建 + 举报材料生成）
│
└─ orchestration/
    └─ investigation_pipeline.yaml  ← 调查类型→模块组合映射
```

---

### 三、data_forensics/ — 数据层取证

**目标**：将"统计异常信号"升级为"可反驳的数据造假假设"。脚本不判断数据是否伪造，只做"数据可及性审计"——记录论文是否提供了足够的信息供第三方验证。

#### 3.1 stats_reverse_engineer.py — 统计反推一致性检验

**功能**：从论文表格中报告的均值、标准差、样本量反推t值/F值，检验与报告值是否一致。

**输入**：论文PDF中的统计表格（人工提取或pdfplumber解析）
**输出**：不一致性标记清单 + 置信度评级

**典型发现**：
- 报告的t值与根据均值/标准差/样本量计算出的理论t值偏差超过阈值
- 效应量与样本量明显不匹配（如n=10却报告Cohen's d > 2.0）
- p值过度聚集在0.049附近（P-hacking信号）

**人类介入点**：人类复核被标记的统计量，排除计算误差和特殊情况（如使用了校正方法）。

#### 3.2 image_metadata_extractor.py — 图像元数据提取

**功能**：提取论文PDF中嵌入图像的创建时间戳、软件指纹、分辨率历史。

**输入**：论文PDF
**输出**：图像元数据CSV + 时间异常警报

**典型发现**：
- 同一篇论文的多张"不同实验"图像具有完全相同的创建时间戳
- 图像分辨率或色彩空间与声称的实验设备不匹配
- 图像编辑软件指纹（如Photoshop历史记录未清除）

**人类介入点**：人类判断"同一天生成"是否合理（如使用了批量处理脚本）。

#### 3.3 data_availability_validator.py — 数据可用性声明验证

**功能**：解析论文Data Availability Statement，验证声称的公开数据仓库链接是否可访问。

**输入**：论文方法部分文本
**输出**：可访问 / 失效 / 未声明 / 限制获取 四级分类

**典型发现**：
- 声称"数据包含在补充材料中"但补充材料实际缺失
- 提供的Figshare/Dryad/GEO链接返回404
- 声明"数据包含在补充材料中"但补充材料缺失

**人类介入点**：对"未声明"或"链接失效"的论文，标记为"数据可及性不足"，纳入证据链。

---

### 四、publication_trace/ — 发表链追踪

**目标**：建立"预印本→会议→期刊→学位论文"的完整发表时间线，发现隐瞒重叠和重复发表。

#### 4.1 preprint_monitor.py — 预印本监控

**功能**：抓取bioRxiv/medRxiv/arXiv/ChemRxiv/Research Square上目标作者的全部预印本。

**输入**：作者姓名 / ORCID
**输出**：预印本清单（含提交日期、版本历史、与期刊论文的相似度）

**典型发现**：
- 预印本提交日期早于期刊论文投稿日期，但内容高度一致（正常）
- 预印本提交日期与另一期刊的投稿日期重叠（一稿多投嫌疑）
- 预印本在期刊拒稿后未更新，但内容被拆分投递（隐瞒历史嫌疑）

#### 4.2 conference_paper_mapper.py — 会议论文映射

**功能**：检索会议论文集，建立会议论文→期刊论文转化时间线。

**输入**：作者姓名 + 机构
**输出**：会议-期刊映射表 + 时间重叠警报

**典型发现**：
- 会议论文与期刊论文投稿时间重叠（< 3个月），构成一稿多投嫌疑
- 会议论文在会后2年内未转化为期刊论文（正常损耗）
- 同一组数据同时出现在会议和期刊，但期刊未声明" preliminary results presented at X conference"

#### 4.3 bilingual_publication_detector.py — 双语发表检测

**功能**：对国内学者，检索CNKI/Wanfang中文论文，与英文SCI论文进行图表/结论相似度比对。

**输入**：作者中文名 + 英文名
**输出**：双语论文相似度矩阵 + 重复发表嫌疑标记

**典型发现**：
- 中文论文与英文SCI论文的图表高度相似（> 70%），但未互相引用
- 中文论文发表时间晚于英文论文，构成"反向翻译发表"
- 同一组数据在中英文两个版本中使用了不同的样本量或统计方法

#### 4.4 crossref_event_tracker.py — Crossref事件追踪

**功能**：利用Crossref Event Data查询论文的更新、撤稿、更正、评论事件历史。

**输入**：DOI列表
**输出**：事件时间线 + 异常事件标记

**典型发现**：
- 论文在发表后短期内（< 6个月）发布了多次更正（Erratum/Corrigendum）
- 论文被Retraction Watch标记但尚未正式撤稿
- 论文收到了PubPeer上的公开质疑，但作者未回应

---

### 五、ethics_audit/ — 伦理审计

**目标**：将"论文中是否有伦理声明"升级为"伦理声明是否结构化、可交叉验证"。

#### 5.1 ethics_statement_parser.py — 伦理声明解析

**功能**：从论文全文提取伦理声明文本、批准号、委员会名称、知情同意说明。

**输入**：论文PDF
**输出**：结构化伦理声明JSON（含声明存在性、批准号格式、委员会名称）

**典型发现**：
- 涉及人体/动物实验的论文完全缺失伦理声明
- 伦理声明使用了模糊的措辞（如"经本单位伦理委员会批准"但无具体编号）
- 批准号格式与声称的机构不匹配（如声称"北京协和医院"但批准号为"IACUC-SH-XXX"）

#### 5.2 clinical_trial_registry_checker.py — 临床试验注册核查

**功能**：在ChiCTR/ClinicalTrials.gov检索目标作者，比对注册信息与论文一致性。

**输入**：作者姓名 + 论文标题关键词
**输出**：注册-论文一致性报告（样本量、入组标准、主要终点、注册日期 vs 论文投稿日期）

**典型发现**：
- 论文声称进行了随机对照试验，但未在任何注册平台注册
- 注册信息中的样本量与论文报告的样本量不一致
- 论文投稿日期早于临床试验注册日期（违反ICMJE规范）

---

### 六、peer_review_intel/ — 同行评议情报

**目标**：用公开可获取的期刊元数据，推断"审稿生态异常"。

#### 6.1 review_cycle_analyzer.py — 审稿周期分析

**功能**：统计目标作者在各期刊的投稿-接受-见刊周期，与期刊公开平均周期对比。

**输入**：论文DOI + Crossref日期数据
**输出**：周期异常标记（快于均值2个标准差）+ 期刊基准表

**典型发现**：
- 目标作者在某一期刊的多篇论文审稿周期显著短于该期刊平均水平
- 审稿周期与论文质量评分呈负相关（质量低的论文反而更快被接受）
- 同一期刊中，目标作者的论文总是由同一批编辑处理

#### 6.2 editorial_self_publishing_detector.py — 编委自发文检测

**功能**：检查目标作者是否在自己担任编委/客座编辑的期刊上发文，计算主场发文占比。

**输入**：编委会名单 + 论文清单
**输出**：主场占比 + 编委-作者互惠指数

**典型发现**：
- 目标作者在某期刊的发文量占其总发文量的比例，显著高于该期刊在领域内的市场份额
- 目标作者担任客座编辑期间，该专刊中出现了大量其合作者/学生的论文
- 主场发文伴随异常短的审稿周期

#### 6.3 recommended_reviewer_network.py — 推荐审稿人网络

**功能**：如论文提及推荐审稿人，追踪这些审稿人与作者的合著/同机构关系。

**输入**：论文致谢/方法部分（人工提取推荐审稿人名单）+ OpenAlex
**输出**：推荐审稿人-作者关联网络图 + 关联强度评分

**典型发现**：
- 推荐的3名审稿人均为作者过去2年内的合著者
- 推荐审稿人与作者共享同一基金项目编号
- 推荐审稿人的机构邮箱域名与作者所在机构相同（内部人审稿嫌疑）

#### 6.4 journal_retraction_history.py — 期刊撤稿历史

**功能**：检索目标作者发文期刊的Retraction Watch记录，检查是否存在"同行评议操纵"批量撤稿先例。

**输入**：期刊ISSN列表
**输出**：撤稿原因分类统计 + 风险评级

**典型发现**：
- 目标作者发文量最大的某期刊，在过去5年中因"同行评议操纵"撤稿超过5篇
- 该期刊的编委名单中出现了多名已被曝光的虚假审稿人
- 期刊的出版商被Beall's List或Cabells黑名单收录

---

### 七、evidence_compiler/ — 证据链编译器

**目标**：将分散在各模块的"异常信号"整合为"可结构性呈现的疑点包"。

#### 7.1 signal_aggregator.py — 信号聚合

**功能**：收集所有模块的异常标记，按"证据强度"和"可验证性"排序。

**输入**：各模块JSON输出
**输出**：异常信号总表（按置信度降序，含信号来源、支撑数据、已知反证）

**排序规则**：
1. **可计算异常**（统计反推不一致、图像元数据异常）> **元数据异常**（审稿周期异常、预印本重叠）> **声明缺失**（伦理声明缺失、数据可用性未声明）
2. **可独立验证**（Crossref日期、PubMed记录）> **需进一步核实**（推荐审稿人关联、编委互惠）

#### 7.2 evidence_chain_builder.py — 证据链构建

**功能**：将多个弱信号组合成证据链，标注每个环节的支撑强度和缺口。

**输入**：异常信号总表 + 统一时间线
**输出**：证据链图谱（Markdown格式，含每个环节的支撑强度、缺口、下一步验证建议）

**示例证据链**：
```
假设：论文A可能存在数据操纵
├─ 信号1：统计反推不一致（支撑强度：中）
│   └─ 缺口：可能使用了未报告的校正方法
├─ 信号2：图像创建时间戳异常（支撑强度：中高）
│   └─ 缺口：可能使用了批量导出脚本
├─ 信号3：数据可用性声明缺失（支撑强度：低）
│   └─ 缺口：期刊本身不强制要求
└─ 综合评估：三个独立来源的信号指向同一论文，建议升级为"重点审查"
```

#### 7.3 journal_submission_packager.py — 期刊提交材料生成

**功能**：按期刊/机构的concerns提交规范，生成结构化的疑点陈述材料。

**输入**：证据链图谱
**输出**：Markdown/PDF格式的举报材料草稿（含事实陈述、证据截图占位符、来源链接）

**设计原则**：
- 严格区分"已证实事实"和"推断性假设"
- 每个事实陈述后附带来源和获取时间
- 不做出"学术不端"的终极定性，只呈现"需要编辑部/机构进一步核查的异常"

---

### 八、代写与AI辅助署名专项调查流程

> **报告位置**：本节为调查执行层面的方法论说明，其产出结果应作为"二、学术成果审查"下的子章节"2.7 代写与AI辅助署名检测"呈现于最终报告中，而非独立章节。

**调查目标**：通过公开可获取的文本数据、元数据和统计特征，识别疑似代写或AI辅助署名的异常信号。本流程不追求"定罪"，只生成"需要进一步核查的疑点包"。

**适用场景**：
- 作者某篇论文的写作风格与其既往作品存在显著断裂
- 论文使用了明显超出作者教育背景的方法论
- 文件元数据显示论文在极短时间内完成
- 多篇不同作者的论文呈现共同的风格指纹

#### 8.1 调查步骤

```
Step 1: 建立作者风格基线
├─ 输入：作者既往发表的全部论文全文（建议≥3篇）
├─ 工具：stylometry_profiler.py
├─ 输出：作者个人风格特征向量（虚词密度、句长分布、标点指纹、功能词偏好）
└─ 人类介入：确认纳入分析的论文确为该作者独立撰写

Step 2: 待检论文风格比对
├─ 输入：待检论文全文
├─ 工具：stylometry_profiler.py
├─ 输出：待检论文与作者基线的风格距离（余弦相似度/欧氏距离）
└─ 异常阈值：相似度低于0.3，或偏离基线超过2个标准差

Step 3: AIGC统计特征扫描
├─ 输入：待检论文全文
├─ 工具：aigc_statistical_profiler.py
├─ 输出：困惑度（Perplexity）、Burstiness指数、句子长度变异系数
└─ 异常阈值：困惑度显著低于人类常规水平 + Burstiness波动过小

Step 4: 能力一致性检验
├─ 输入：作者教育背景 + 待检论文方法部分
├─ 工具：capability_consistency_checker.py
├─ 输出：论文使用的方法论与作者训练背景的匹配度评分
└─ 异常阈值：出现作者未接受训练的高阶方法（如单细胞测序、结构方程模型）

Step 5: 翻译抄袭检测（可选）
├─ 输入：待检中文论文 + 疑似英文源论文
├─ 工具：translation_plagiarism_detector.py
├─ 输出：语义相似度矩阵 + 图表重叠度
└─ 适用场景：怀疑作者将英文论文翻译后稍作改写发表

Step 6: 跨文档共同写手检测（可选）
├─ 输入：多篇不同作者但主题相似的论文
├─ 工具：stylometry_profiler.py（跨文档聚类模式）
├─ 输出：共同风格指纹相似度矩阵
└─ 适用场景：怀疑同一写手为多个客户代写

Step 7: 文件元数据审计（如有原始文件）
├─ 输入：论文PDF/Word原始文件
├─ 工具：image_metadata_extractor.py（扩展为通用文件元数据提取器）
├─ 输出：创建时间、修改时间、软件指纹、作者信息
└─ 异常阈值：创建时间与修改时间间隔极短；作者信息保留模板默认值

Step 8: 信号聚合与报告输出
├─ 输入：上述所有步骤的异常信号
├─ 工具：signal_aggregator.py + evidence_chain_builder.py
├─ 输出：代写/AI辅助署名疑点报告
└─ 报告原则：只呈现信号和假设，不做终极定性
```

#### 8.2 报告输出格式

代写/AI辅助署名专项调查的结果应以独立章节形式出现在最终交付报告中：

```
### 2.7 代写与AI辅助署名检测

**本节位置**："二、学术成果审查"的子章节，与"2.1 论文产出""2.4 重点论文六维细评"等并列。

**适用条件**：当调查中存在以下信号时启用本节：
- 作者某篇论文的写作风格与其既往作品存在显著断裂
- 论文使用了明显超出作者教育背景的方法论
- 文件元数据显示论文在极短时间内完成
- 多篇不同作者的论文呈现共同的风格指纹

#### 2.7.1 风格计量学分析
| 指标 | 作者基线均值 | 待检论文值 | 偏差 | 判断 |
|:---|:---:|:---:|:---:|:---|
| 虚词密度（每百字"的"数） | 4.2 | 2.8 | -33% | 显著偏离 |
| 平均句长（字/句） | 28.5 | 42.3 | +48% | 显著偏离 |
| 分号使用率 | 2.1% | 0.3% | -86% | 显著偏离 |
| 风格相似度（余弦） | — | 0.24 | — | 低于阈值0.3 |

#### 2.7.2 AIGC统计特征
| 指标 | 待检论文值 | 人类常规范围 | 判断 |
|:---|:---:|:---:|:---|
| 困惑度（Perplexity） | 12.5 | 25-60 | 显著偏低 |
| Burstiness指数 | 0.15 | 0.40-0.80 | 显著偏低 |
| 句子长度变异系数 | 0.08 | 0.20-0.50 | 显著偏低 |

#### 2.7.3 能力一致性检验
| 论文使用方法 | 作者教育背景是否覆盖 | 判断 |
|:---|:---:|:---|
| 单细胞RNA测序分析 | 否（本科为化学专业，无生物信息学训练） | 异常 |
| 结构方程模型（SEM） | 否（硕士课程未涉及统计学进阶方法） | 异常 |

#### 2.7.4 综合评估
- **信号数量**：5个独立来源的异常信号
- **信号一致性**：全部指向"待检论文的作者真实性存疑"
- **置信度**：中高（需要进一步核实）
- **建议下一步**：要求作者提供写作过程性材料（drafts、修订记录），或组织方法论答辩

> **重要声明**：以上分析仅基于公开可获取的文本数据和统计特征，不构成学术不端的确定性证明。风格断裂可能有合理解释（如期刊强制改写、合作者主笔、翻译润色），需结合过程性证据综合判断。
```

#### 8.3 与报告模板的集成

`report/report_template.md` 和 `report/international_template.md` 应在以下位置增加代写检测板块：

**Domestic report template**：在"二、学术成果审查"下增加子章节"2.7 代写与AI辅助署名检测"
**International report template**：在"2. Academic Output Review"下增加子章节"2.7 Authorship Integrity Analysis"

两个模板的代写检测板块均应引用 `deep_evidence/ghost_writing_investigation/` 目录下的JSON输出文件，由LLM自动填充分析结果。

---

### 九、与现有架构的集成

#### 8.1 CLI 扩展

`investigate.py` 新增子命令：

```bash
# 深度证据层调用
investigate.py data-forensics --scholar-data ./scholar_data.json
investigate.py publication-trace --scholar-data ./scholar_data.json
investigate.py ethics-audit --scholar-data ./scholar_data.json
investigate.py peer-review-intel --scholar-data ./scholar_data.json

# 证据链编译
investigate.py evidence-compile --signals ./signals/ --output ./evidence_pack/
```

#### 8.2 配置扩展

`config.template.yaml` 新增 `deep_evidence` 区块：

```yaml
deep_evidence:
  data_forensics:
    enabled: true
    stats_reverse_engineer: true
    image_metadata_extraction: true
    data_availability_validation: true
    
  publication_trace:
    enabled: true
    preprint_sources: [bioRxiv, medRxiv, arXiv, ChemRxiv, ResearchSquare]
    check_bilingual: true
    check_conference_overlap: true
    
  ethics_audit:
    enabled: true
    registry_sources: [ChiCTR, ClinicalTrials.gov]
    
  peer_review_intel:
    enabled: true
    cycle_benchmark_years: 3
    check_editorial_self_publishing: true
    check_recommended_reviewer_network: true
```

#### 8.3 数据流

```
v2.0 流程：
scholar_data.json → domestic/international → analysis → report

v3.0 流程：
scholar_data.json → domestic/international → analysis ─┬→ report
                                                       └→ deep_evidence → evidence_compiler → report_appendix
```

`deep_evidence` 与 `analysis` 并行运行，产出作为报告附录（Appendix: Deep Evidence Findings）附加到主报告后。

---

### 十、实施优先级

| 模块 | 开发成本 | 运行成本 | 优先级 | 理由 |
|:---|:---:|:---:|:---:|:---|
| `preprint_monitor.py` | 中 | 低（API免费） | **P0** | 预印本数据完全公开，技术可行，覆盖面广 |
| `review_cycle_analyzer.py` | 低 | 低（Crossref免费） | **P0** | 纯元数据分析，无需外部沟通，可批量运行 |
| `stats_reverse_engineer.py` | 中 | 低 | **P1** | 仅需论文表格数据，对生命科学/医学类论文价值极高 |
| `ethics_statement_parser.py` | 低 | 低 | **P1** | 文本解析为主，输出结构化伦理声明 |
| `image_metadata_extractor.py` | 中 | 低 | **P1** | 图像处理成熟，但需人工判断异常合理性 |
| `bilingual_publication_detector.py` | 中 | 低 | **P2** | 需接入CNKI/Wanfang接口，对国内学者专用 |
| `evidence_compiler/` | 中 | 低 | **P2** | 整合层，需等待前端模块稳定 |

---

**System Architecture Summary (v3.2):**
- **Dual-track design**: `domestic/` + `international/` + `cross_border/` adapters (retained from v2.0)
- **Deep evidence layer**: `deep_evidence/` adds statistical forensics, publication traceability, ethics audit, and peer-review intelligence
- **Evidence compilation**: `evidence_compiler/` aggregates signals into structured, verifiable evidence chains with confidence ratings
- **Multi-agent collaboration**: `agents/` provides 4-role collaborative investigation with Orchestrator round scheduling
- **Delivery layer**: `delivery/` provides automated material collection (Xiaotangdou) and report generation with self-check (Xiaojinjing)
- **Semi-automation principle**: Scripts handle computational verification of publicly accessible data; humans interpret signals, verify anomalies, and make final judgments
- **Free API priority**: All new modules rely on free APIs (Crossref, bioRxiv API, ClinicalTrials.gov, ChiCTR) or local PDF parsing; no paid database required
- **Privacy by design**: No email communication with subjects or institutions; all verification through public metadata and archival records

**Test coverage**: 296 tests (v3.2 baseline).

---

### 附录：v3.2 多智能体协作层 (Multi-Agent Collaboration Layer)

#### 四大 Agent 角色

| 角色 | 模块 | 人格定位 | 核心职责 |
|:---|:---|:---|:---|
| 朱先生 | `zhu_xiansheng.py` | 沉默寡言、只信输出 | 执行脚本队列、监控数据链、标记 CRITICAL |
| 嘟嘟嘟 | `dududu.py` | 冷静犀利、不信巧合 | 跨模块关联信号、评估置信度、生成推荐任务 |
| 黄毛 | `huangmao.py` | 脑洞大开、不按常理 | 自由漫游原始数据、并联思考、提出假设 |
| 老周墨 | `laozhoumo.py` | 沉稳全局、关键开口 | 唯一写入 STATE.md、人机接口、决策拦截 |

#### 回合执行流程 (Round-based)

```
Round N:
  1. 老周墨读取 STATE.md，确定任务队列
  2. 朱先生顺序执行推荐工具队列 → 写 summary.json
  3. 黄毛后台漫游原始数据 → 写 findings.json
  4. 嘟嘟嘟读取结果 + 假设 → 分析并写 recommendations.json
  5. 老周墨检测 CRITICAL
     → 有: 暂停，向人类汇报，等待决策
     → 无: 更新 STATE.md，准备下一轮
```

#### 通信协议

- **共享存储**: 案件目录下的 `STATE.md`（老周墨独占写入）+ `agent_logs/` + `outputs/`
- **事件通知**: CRITICAL 标记写入 `agent_logs/{name}/critical.json`，老周墨检测后立即暂停
- **可信度分级**: 黄毛的假设必须标记为 `wild_guess` / `plausible` / `strongly_suggested`

#### 典型协作场景

**场景1: 正常运行流**
老周墨生成任务 → 朱先生执行 → 黄毛漫游发现线索 → 嘟嘟嘟分析并推荐新工具 → 老周墨更新队列 → 循环

**场景2: 重大线索拦截**
朱先生执行中发现 MD5 重复图片 → 标记 CRITICAL → 老周墨暂停全部 agent → 向人类汇报并请求决策 → 解析指令生成新任务 → 恢复

#### CLI 入口

```bash
# 启动多 agent 协作模式（默认 manual，每轮等待确认）
python investigate.py orchestrate --case-dir ./cases/xxx/

# 自动模式（运行到 CRITICAL 或完成）
python investigate.py orchestrate --case-dir ./cases/xxx/ --mode auto

# 只启动指定 agent
python investigate.py orchestrate --case-dir ./cases/xxx/ --agents zhu,dudu
```

---

### 附录：v3.2 交付层 (Delivery Layer)

#### 交付层双Agent架构

```
delivery/
├── delivery_base.py       # 共享基类 (BaseDeliveryAgent, ChecklistRunner)
├── xiaotangdou.py         # 素材收集Agent (小糖豆)
├── xiaojinjing.py         # 报告生成Agent (小金金)
└── checklists/
    ├── ban_rules.json     # 禁止条例自检
    ├── format_rules.json  # 格式一致性自检
    └── content_rules.json # 内容完整性自检
```

**小糖豆 (Xiaotangdou)**：素材收集与整理Agent
- 遍历所有Agent日志和产出文件
- 按报告框架9章节分类素材
- 标记信息缺口和矛盾点
- 输出结构化素材包到 `delivery/` 目录

**小金金 (Xiaojinjing)**：报告生成与自检Agent
- 读取小糖豆的素材包（不读取原始日志）
- 生成Markdown报告和HTML网络图
- 执行三类自检：禁止条例、格式一致性、内容完整性
- 自检失败时输出反馈，等待小糖豆补充后重新生成

#### 自检清单核心规则

| 类别 | 规则 | 严重性 |
|:---|:---|:---:|
| 禁止条例 | 无破折号、无否定句式、无比喻修辞 | error |
| 禁止条例 | 无报告生成时间、无调查者身份、无委托人信息 | error |
| 格式一致性 | 论文必须使用具体标题指代，禁止编号 | error |
| 格式一致性 | 报告末尾必须包含免责声明 | error |
| 内容完整性 | 覆盖全部9个章节 | error |
| 内容完整性 | 内容具体不概括，两面性平衡 | warning |

#### CLI入口

```bash
# 运行小糖豆收集素材
python investigate.py collect --case-dir ./cases/xxx/

# 运行小金金生成报告
python investigate.py generate --case-dir ./cases/xxx/

# 强制交付（自检有警告时）
python investigate.py generate --case-dir ./cases/xxx/ --force

# 智能辅助推进：自动检查阶段条件，确认后自动推进
python investigate_visual.py --case-dir ./cases/xxx/ smart-step
```

#### 状态机集成

交付层扩展状态机阶段流：
```
reviewed → collected → generated → archived
```

- `collected`: 小糖豆完成素材收集
- `generated`: 小金金完成报告生成并通过自检

---

### 附录：导师蒸馏服务 (Mentor Distill)

#### 概述

导师蒸馏服务是学术侦探系统的**最终交付增强组件**。当七步调查完成、报告生成后，调查成果可被蒸馏为一个可对话的学术知识库。用户上传学者的论文、调查报告等资料，AI 现场整理并生成基于检索增强生成（RAG）的对话接口。

#### 核心能力

| 能力 | 说明 |
|:---|:---|
| **档案自动提取** | 从上传文件中自动提取学者姓名、机构、研究方向、教育背景、代表作等 |
| **本地向量检索** | 基于 TF-IDF 的纯本地向量化，无需调用 Embedding API，保护隐私 |
| **OpenAI 兼容接口** | 提供 `/v1/chat/completions` 标准接口，任何支持 OpenAI 格式的客户端均可接入 |
| **多风格对话** | 支持客观中立、普通教授、疯癫教授、老年健忘四种对话风格 |

#### 与调查工作流的集成

```
七步调查完成 → 报告生成 → 上传学者资料 → 蒸馏 → 可对话知识库
```

在调查后期，可将以下资料上传进行蒸馏：
- 学者本人论文 PDF
- 调查过程中生成的 Markdown 报告
- CNKI/Wanfang 导出的文献列表
- 机构官网保存的 HTML 快照

#### 快速启动

服务代码位于项目根目录 `mentor-distill/` 下：

```bash
cd mentor-distill

# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的 OpenAI 兼容 API Key 和接口地址

# 3. 启动服务
python app.py
```

服务启动后：
- **Web UI**: http://127.0.0.1:5050/
- **OpenAI API**: http://127.0.0.1:5050/v1/chat/completions

#### API 接口

**1. 上传文件**

```bash
curl -X POST http://127.0.0.1:5050/api/upload \
  -F "files=@论文.pdf" \
  -F "files=@调查报告.md" \
  -F "name=学者姓名" \
  -F "institution=所在机构"
```

返回 `session_id`，后续所有请求均需携带此 ID。

**2. 蒸馏处理**

```bash
curl -X POST http://127.0.0.1:5050/api/distill \
  -H "Content-Type: application/json" \
  -d '{"session_id": "abc123"}'
```

AI 自动分析文件，提取学者档案，构建 TF-IDF 向量知识库。

**3. OpenAI 格式对话（兼容接口）**

```bash
curl -X POST http://127.0.0.1:5050/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-Session-ID: abc123" \
  -d '{
    "model": "mentor-distill",
    "messages": [
      {"role": "user", "content": "这位学者的研究方向是什么？"}
    ]
  }'
```

兼容客户端：ChatGPT-Next-Web、LobeChat、OpenCat 等支持自定义 Base URL 的客户端。配置时：
- Base URL: `http://127.0.0.1:5050/v1`
- API Key: 任意值（或你的真实 Key）
- Model: `mentor-distill`
- 自定义 Header: `X-Session-ID: {你的session_id}`

#### 环境变量配置

| 变量 | 默认值 | 说明 |
|:---|:---|:---|
| `OPENAI_API_KEY` | — | LLM API Key |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | API 基础地址，支持任何 OpenAI 兼容接口 |
| `LLM_MODEL` | `gpt-4o-mini` | 对话模型 |
| `HOST` | `127.0.0.1` | 绑定地址 |
| `PORT` | `5050` | 服务端口 |

#### 技术栈

| 组件 | 选型 | 说明 |
|:---|:---|:---|
| Web 框架 | Flask | 轻量，单文件部署 |
| 向量检索 | TF-IDF + sklearn | 纯本地计算，无需外部 Embedding 服务 |
| 分词 | jieba | 中文支持 |
| LLM 调用 | httpx | OpenAI 兼容格式，支持任意兼容接口 |
| 文本提取 | pdfplumber / PyMuPDF / python-docx | 支持 PDF / TXT / DOCX / MD |

#### 文件组织

```
mentor-distill/
├── app.py                  # 主服务（Flask 单文件）
├── requirements.txt        # Python 依赖
├── .env.example            # 环境变量模板（去敏化）
├── style_templates.yaml    # 四种对话风格模板
├── README.md               # 服务说明文档
└── static/
    └── index.html          # Web UI 前端
```

---

*Skill Version: 3.2 | Multi-Agent Collaboration + Delivery Layer + Mentor Distill | Dual-track domestic/international support | Based on verified case studies*