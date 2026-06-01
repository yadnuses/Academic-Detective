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
python3 scripts/analysis/text_profiler.py --input ./pdfs/paper.pdf --output ./data/paper_profile.json
python3 scripts/analysis/paper_quality_rubric.py --profile ./data/paper_profile.json --output ./data/paper_quality.json

# 增强模式：叠加人工观察（推荐）
python3 scripts/analysis/text_profiler.py --input ./pdfs/paper.pdf --output ./data/paper_profile.json
python3 scripts/analysis/paper_quality_rubric.py \
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
python3 scripts/investigate.py score -i ./pdfs -o ./data/hybrid_scores
python3 scripts/investigate.py score -i ./pdfs -o ./data/hybrid_scores --apply
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

#### LLM 视觉/文本检测清单（PDF 直接审查）

当用户提供论文 PDF（而非结构化 Excel/CSV 数据）时，LLM 应按以下清单逐项审查。此清单与脚本自动化检测互补：脚本做数值统计，LLM 做视觉+文本判断。

**第一式：图片复用检测**
- 逐一比对论文中所有 Figure/Subfigure，关注视觉相似的面板
- 重点检查：Western blot、凝胶电泳图、显微镜图、流式细胞图
- 检查是否有旋转、翻转、裁剪后重复使用的痕迹
- 对比 Figure caption 中声称的实验条件是否与图片一致
- 同一个 control/loading control 是否在不同图中重复出现

**红旗信号**：
- 两个声称不同实验的图，背景噪点模式完全一致
- Loading control（如 β-actin、GAPDH）在不同条件下完全相同
- 图片边缘有裁切痕迹

**第二式：数据造假检测**
- 检查表格中数值数据的末位数字分布（真实数据末位 0-9 应近似均匀）
- 分析标准差/标准误：过于整齐的 SD 值（如全部为整数或固定小数位）高度可疑
- 检查重复实验的一致性：真实的三次独立重复不可能给出几乎相同的值
- 计算报告的均值±SD 是否数学自洽
- 寻找"太完美"的剂量-效应曲线——真实数据通常有噪声
- 检查同一表格的不同列是否存在可疑的数学关系（如两列差值恒定）

**红旗信号**：
- 不同实验组的数据列之间差值完全相同
- 标准差全部相同或呈现明显规律
- p 值精确到不合理的小数位数
- 数据点分布过于"教科书式完美"

**第三式：图片拼接检测**
- Western blot 泳道之间是否有不自然的分界线
- 背景灰度/纹理在图片不同区域是否一致
- 相邻泳道的曝光水平是否突变
- 图片是否有不同分辨率/压缩质量的区域

**红旗信号**：
- 泳道之间出现清晰的垂直分界线
- 背景在某条线处突然变化
- 同一 blot 不同区域的噪声模式明显不同

**第四式：统计异常检测**
- p 值分布检测（p-hacking）：大量 p 值恰好在 0.04-0.05 区间
- 样本量与效应量的匹配性：小样本却得到极显著结果
- 检查统计方法是否适合数据类型（如对非正态数据用 t-test）
- ANOVA 结果与事后比较的逻辑一致性

**红旗信号**：
- 所有比较都"恰好显著"
- 报告的 F 值/t 值与自由度不匹配
- 样本量在同一实验的不同结果中不一致

**第五式：产出异常检测**
- 检查论文的实验时间线是否合理（方法部分声称的实验周期 vs 投稿时间）
- 多篇论文是否共享高度相似的方法描述（copy-paste）

**第六式：方法矛盾检测**
- 方法部分是否存在内部矛盾（如前面说 n=5，后面表格只有 4 组数据）
- 引用的参考文献是否真的支持所声称的观点
- 试剂/设备型号是否存在（有时造假者编造不存在的试剂编号）
- 伦理审批号是否真实有效
- 时间线冲突：使用了投稿时尚未上市的试剂或设备

> **使用方式**：当用户直接提供 PDF 时，LLM 按六式逐项扫描，每发现一个可疑点立即记录（位置、异常类型、具体证据、严重程度）。此流程与脚本分析并行，结果汇总到最终报告的"核心发现"部分。

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

#### Step 5.5: 内部一致性交叉验证

在 Step 5 完成异常检测后、进入 Step 6 多源验证之前，执行**同一论文/同一学者内部**的异常点关联性判断。此步骤区分"孤立疏忽"与"系统性造假"。

**验证逻辑**：

1. **异常点聚类**：将 Step 5 发现的所有异常点按位置（Figure/Table/Page）聚类，检查是否存在多个异常点指向同一组数据或同一实验
2. **方向一致性**：多个异常是否指向同一方向？例如：
   - 尾数分布异常 + 数据重复 + 小数点一致性异常 → 三重统计信号交叉，指向同一组数据造假
   - 图片复用 + 方法矛盾（声称两批独立实验但图片相同）→ 图像+文本双重信号
3. **核心结论依赖性**：可疑数据是否支撑论文的核心结论？如果可疑数据仅出现在补充材料中，严重程度降低；如果出现在主 Figure 的关键比较中，严重程度升高
4. **排除合理解释**：
   - 计数数据的尾数偏好是否因数据类型导致？
   - 小数位一致是否因使用了同一仪器/同一格式化脚本？
   - 数据重复是否因四舍五入导致？

**判定矩阵**：

| 异常数量 | 方向一致性 | 核心结论依赖 | 综合判定 |
|:---:|:---:|:---:|:---|
| 1-2 处 | 无关联 | 否 | 🟡 存疑，可能是疏忽 |
| 3+ 处 | 指向同一问题 | 是 | 🟠 高度可疑，建议深入调查 |
| 3+ 处 | 指向同一问题 | 是 + 无法用疏忽解释 | 🔴 实锤，系统性造假 |
| 任意数量 | 不一致 | 否 | 🟡 逐条记录，不作整体判定 |

> **此步骤不引入新的检测工具**，仅对 Step 5 已有发现做逻辑关联分析。输出为"内部一致性评估"段落，附加到核心发现之前。

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
