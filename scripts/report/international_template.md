# {{name}} 学术档案调查报告（国际版）

**调查对象**：{{name}}（{{institution}} {{current_title}}）  
**调查时间**：{{investigation_date}}  
**调查性质**：基于公开信息的国际学术档案核查  
**调查类型**：{{investigation_type}}

**交付物清单**：
- `{{name}}_international_report.md` — 本报告（Markdown 格式）
- `{{name}}_network.html` — 交互式学术关系网络图谱

---

## 执行摘要

### 核心发现

{{executive_summary}}

### 关键证据等级

| 证据类型 | 置信度 | 关键发现 |
|:---|:---:|:---|
{{evidence_table}}

---

## 一、基本信息与教育背景

### 1.1 个人履历

| 项目 | 内容 | 来源 |
|:---|:---|:---|
| 姓名 | {{name}} | {{name_source}} |
| ORCID | {{orcid}} | {{orcid_source}} |
| 现任职务 | {{current_title}} | {{current_title_source}} |
| 职称/职级 | {{academic_title}} | {{academic_title_source}} |
| 所在院系 | {{department}} | {{department_source}} |
| 学科领域 | {{discipline}} | {{discipline_source}} |
| Tenure 状态 | {{tenure_status}} | {{tenure_status_source}} |

### 1.2 教育经历

{{education_timeline}}

### 1.3 职业履历

{{career_timeline}}

> 国外学术职位通常经历：Postdoc → Assistant Professor（tenure-track，约6年）→ Associate Professor（tenured）→ Full Professor。Tenure-clock 内的 Assistant Professor 尚未获得终身教职，其产出压力通常较大。

---

## 二、学术成果审查

### 2.1 论文产出

#### 声称情况

> {{claimed_papers_statement}}

#### 核实情况

| 检索条件 | 结果 |
|:---|:---:|
{{paper_verification_table}}

**差距分析**：{{paper_gap_analysis}}

> **分析说明**：论文数量评估需结合学科大类和 career stage。例如：人文社科 tenure-track 年均 1.0-2.5 篇为正常区间，STEM tenure-track 年均 3.0-6.0 篇为正常区间。OpenAlex、Semantic Scholar 等免费数据库覆盖范围有限，建议手动补充 Scopus/WoS 检索。

### 2.2 期刊质量分布（JCR / CiteScore）

> **评估方法**：以下分区基于 JCR Quartile 或 CiteScore Percentile。免费 API（OpenAlex/Semantic Scholar）的期刊指标可能不完整，需手动在 Scopus/Journal Citation Reports 中核实。

| 分区 | 论文数 | 占比 | 判断基准 |
|:---:|:---:|:---:|:---|
| Q1 (Top 25%) | {{q1_count}} | {{q1_pct}}% | 高影响力，国际顶尖 |
| Q2 (25-50%) | {{q2_count}} | {{q2_pct}}% | 良好，主流期刊 |
| Q3 (50-75%) | {{q3_count}} | {{q3_pct}}% | 一般，部分 OA 期刊 |
| Q4 / 未分区 | {{q4_count}} | {{q4_pct}}% | 影响力有限或新刊 |
| 未知 | {{unknown_q_count}} | {{unknown_q_pct}}% | 免费 API 未收录该期刊指标 |

**开放获取（OA）分析**：

| OA 类型 | 论文数 | 占比 | APC 估算（USD） |
|:---|:---:|:---:|:---|
| Gold OA | {{gold_oa_count}} | {{gold_oa_pct}}% | {{gold_oa_apc_avg}} |
| Green OA | {{green_oa_count}} | {{green_oa_pct}}% | 0 |
| Hybrid | {{hybrid_oa_count}} | {{hybrid_oa_pct}}% | {{hybrid_oa_apc_avg}} |
| Closed | {{closed_count}} | {{closed_pct}}% | 0 |

> **OA 费用警示**：若 Gold OA 论文比例过高（>40%）且集中于 Frontiers/MDPI/Hindawi 等出版商，需关注是否存在"付费即发"模式。正常 STEM 领域 Gold OA 比例约为 20-30%。

### 2.3 学术影响力指标

| 指标 | 数值 | 来源 | 判断基准 |
|:---|:---:|:---:|:---|
| h-index | {{h_index}} | {{h_index_source}} | 从业 {{years_active}} 年预期 {{expected_h_index}} |
| i10-index | {{i10_index}} | {{i10_index_source}} | — |
| 总被引 | {{total_citations}} | {{citations_source}} | — |
| 年均被引 | {{avg_citations_per_year}} | — | — |
| 高被引论文数 | {{highly_cited_count}} | — | 被引 > 领域均值 10 倍 |

> h-index 数据来源优先级：Google Scholar（覆盖最广）> Scopus（质量筛选）> OpenAlex（免费）。不同来源的 h-index 可能相差 20-50%，报告中应注明来源。

### 2.4 批量论文质量评分汇总

> **评估方法**：以下评分采用六维量表（A/B+/B/C/D），量化方式参考 Nature/Springer/ACM 同行评审标准。六维量表及权重如下：
>    - **原创性与重要性**（权重 0.25）
>    - **技术严谨性**（权重 0.20）
>    - **数据与证据质量**（权重 0.20）
>    - **逻辑结构与结论稳健性**（权重 0.15）
>    - **文献综述与引用规范**（权重 0.10）
>    - **表达清晰度与可及性**（权重 0.10）
>
> **评级标准**：A（≥85，优秀，具有国际发表潜力）、B+（75-84，良好，需少量修改）、B（65-74，中等，专业期刊可接受但需修改）、C（55-64，及格或边缘，存在明显缺陷）、D（<55，不合格，重大修改或拒稿）。

**统计摘要**
- 评分论文总数：{{hybrid_paper_count}} 篇
- 平均分：{{hybrid_avg_score}} / 100
- 最高分：{{hybrid_max_score}} | 最低分：{{hybrid_min_score}}
- 评级分布：{{hybrid_rating_distribution}}

**评分前五**

| 排名 | 论文标题 | 评分 | 评级 |
|:---:|:---|:---:|:---:|
| 1 | {{hybrid_top1_title}} | {{hybrid_top1_score}} | {{hybrid_top1_rating}} |
| 2 | {{hybrid_top2_title}} | {{hybrid_top2_score}} | {{hybrid_top2_rating}} |
| 3 | {{hybrid_top3_title}} | {{hybrid_top3_score}} | {{hybrid_top3_rating}} |
| 4 | {{hybrid_top4_title}} | {{hybrid_top4_score}} | {{hybrid_top4_rating}} |
| 5 | {{hybrid_top5_title}} | {{hybrid_top5_score}} | {{hybrid_top5_rating}} |

**质量结构判断**：{{hybrid_quality_verdict}}

> 在评价整体质量结构时，应使用有参照的量化表述（如"平均分 68.3，处于专业期刊可接受水平"），避免无基准的相对判断（如"质量较高/较低"）。
>
> 所有负面判断必须使用置信度分级措辞（疑似/存在迹象/高度疑似/经查证），禁用绝对化表述。

### 2.5 Tenure 时钟评估（如适用）

> **评估背景**：Tenure-track Assistant Professor 通常在入职后 5-7 年内接受 tenure review。评审标准因 institution tier 而异。

| 评估维度 | 实际值 | 机构预期 | 达标状态 |
|:---|:---:|:---:|:---:|
| 论文总数 | {{tenure_total_papers}} | ≥ {{tenure_min_papers}} | {{tenure_papers_status}} |
| 一作/通讯论文 | {{tenure_first_author}} | ≥ {{tenure_min_first_author}} | {{tenure_first_status}} |
| Q1 论文 | {{tenure_q1_papers}} | ≥ {{tenure_min_q1}} | {{tenure_q1_status}} |
| h-index | {{tenure_h_index}} | ≥ {{tenure_expected_h}} | {{tenure_h_status}} |
| 基金项目 | {{tenure_grant_count}} | ≥ {{tenure_min_grants}} | {{tenure_grant_status}} |
| 年均产出 | {{tenure_annual_output}} | {{tenure_expected_annual}} | {{tenure_annual_status}} |

**Tenure 评估结论**：{{tenure_assessment}}

> Tenure 评估仅针对 tenure-track 职位。已获 tenure 的学者不适用此评估。免费 API 可能无法完整获取基金信息，需手动补充 NSF/NIH/ERC 等数据库检索。

### 2.6 国际特有问题检测

| 规则 ID | 问题类型 | 严重度 | 置信度 | 描述 |
|:---:|:---|:---:|:---:|:---|
{{heuristics_table}}

> 国际学术界常见异常类型包括：掠夺性期刊发表（I01）、论文工厂代写嫌疑（I02）、引用操纵（I04）、幽灵作者（I06）、发表速度异常（I07）。以上检测基于启发式规则，具体指控需人工核实。

---

## 三、学生评价汇总

> **数据来源**：{{review_source}}  
> **样本量**：{{review_count}} 条评价  
> **平均评分**：{{review_average_rating}} / 5.0  
> **平均可信度分**：{{review_credibility_score}} / 1.0  
> **可靠性声明**：本部分内容为匿名学生主观评价，仅用于生成假设线索。小红书来源存在明显的负向偏差（负面体验更倾向于被分享）。

### 3.1 多源评价维度雷达图

以下分数基于情感极性分析（正面=5，中性=3，负面=1），按提及次数加权计算。缺失维度表示该数据源无对应标签：

```
{{review_radar_diagram}}
```

| 维度 | 得分 | 提及次数 | 主导情感 | 数据来源 |
|:---|:---:|:---:|:---:|:---|
{{review_radar_table}}

### 3.2 小红书特有维度

> 以下维度主要来源于中国留学生在小红书平台的分享，反映了中国学生的特定关注点：

| 维度 | 平均评分 | 涉及评价数 | 说明 |
|:---|:---:|:---:|:---|
| 毕业难度 | {{xhs_graduation_difficulty}} / 5 | {{xhs_graduation_count}} | 5=极难毕业，1=非常容易 |
| 工作强度 | {{xhs_workload}} / 5 | {{xhs_workload_count}} | 5=极度push，1=放养 |
| 导师支持度 | {{xhs_supportiveness}} / 5 | {{xhs_support_count}} | 5=非常supportive，1=完全不管 |
| 推荐率 | {{xhs_recommendation_ratio}}% | {{xhs_recommend_count}} | 愿意推荐该导师的比例 |

### 3.3 各维度摘要

| 维度 | 提及次数 | 主导情感 | 代表性摘要 |
|:---|:---:|:---:|:---|
{{review_dimension_table}}

### 3.4 由评价生成的待验证线索

以下线索来自结构化评价数据库的关键词提取，需与可验证的公开记录对照：

{{review_leads_list}}

> 将线索转化为可验证假设时，应参照标准学制（硕士 1-2 年、博士 4-6 年为正常）。所有来自匿名评价的线索必须标注为"有匿名评价反映…""部分受访者提及…"，严禁将其作为确认事实呈现。

### 3.5 线索验证状态

| 线索 | 验证结果 | 证据来源 |
|:---|:---|:---|
{{review_leads_verification_table}}

### 3.6 高可信度评价摘录

{{high_credibility_quotes}}

---

## 四、核心发现

> 每一条核心发现应同时包含：现象描述、证据来源、置信度等级、基准线对照。负面发现须同时指出一条可确认的正面信息（两面性原则）。

### 4.1 {{finding_1_title}}

{{finding_1_content}}

### 4.2 {{finding_2_title}}

{{finding_2_content}}

### 4.3 {{finding_3_title}}

{{finding_3_content}}

---

## 五、综合评价

### 5.1 学术产出的整体结构

```
{{output_structure_diagram}}
```

### 5.2 两面性分析

**应予肯定的方面**：
{{positive_aspects}}

**值得关注的问题**：
{{concerns}}

> "值得关注的问题"部分的所有表述必须使用置信度分级措辞（如"疑似""存在差异"）。即使是数据明确的问题（如数量差异），也应使用"核实数与声称数存在 X% 差异"而非"虚报 X%"。

### 5.3 一句话定性

> {{one_sentence_conclusion}}
>
> 一句话定性必须是中性的、概括性的，不得包含负面定性标签。例如："该学者的学术履历总体上符合其职位和机构的正常预期，但在期刊质量分布和声称/核实差异方面值得关注。"

---

## 六、调查局限性

| 局限 | 影响 |
|:---|:---|
| 免费 API 覆盖不全 | OpenAlex/Semantic Scholar 可能遗漏部分论文，尤其非英文发表 |
| 期刊指标缺失 | JCR Q 分区、CiteScore 需手动在 Scopus/WoS 中核实 |
| 基金信息有限 | 免费 API 不覆盖 NSF/NIH/ERC 等基金数据库 |
| 小红书样本偏差 | 负面体验更倾向于被分享，正面评价被低估 |
| 时间滞后 | API 数据更新有延迟，最新发表可能未收录 |
| 非英语论文 | 免费 API 对中文/日文/德文等非英语文献覆盖较差 |
{{limitations_table}}

---

## 七、后续建议

### 7.1 需手动补充的信息

{{manual_supplement_list}}

### 7.2 建议查询的数据库

| 数据库 | 查询目的 | 访问方式 |
|:---|:---|:---|
| Scopus / WoS | 完整论文清单 + JCR 分区 | 机构订阅 |
| Journal Citation Reports | 期刊影响因子和分区 | 机构订阅 |
| NSF Award Search / NIH RePORTER | 基金项目核实 | 公开免费 |
| PubPeer | 同行质疑和学术讨论 | 公开免费 |
| Retraction Watch | 撤稿记录 | 公开免费 |
| ORCID | 身份和教育背景核实 | 公开免费 |

---

## 免责声明

**服务收取费用为信息整理费**。本服务仅对公开可获取的信息进行收集、整理和结构化呈现，不涉及任何形式的调查取证、法律代理或投资顾问服务。

**信息来源与时效性**：本报告基于截至 {{investigation_date}} 的公开信息编制。公开信息的时效性、完整性和准确性受原始发布方控制，本团队不对原始信息的真实性承担担保责任。

**性质边界**：报告中的"评价"部分为基于事实的分析判断，仅供委托方内部参考使用。本报告不构成法律意见、投资建议或任何形式的官方结论。任何基于本报告内容做出的决策，其风险由决策方自行承担。

**责任限制**：在适用法律允许的最大范围内，本团队对因使用或依赖本报告内容而产生的任何直接、间接、附带或后果性损失不承担赔偿责任。

**使用范围**：未经本团队书面同意，本报告不得用于公开传播、媒体发布、诉讼举证或向任何第三方披露。委托方对本报告的使用应限于内部决策参考。

**数据保护**：本报告中涉及的社交媒体评价数据已进行匿名化处理，不暴露可追溯到个人的信息。原始数据在处理完成后将按约定周期销毁。

**知识产权**：本报告的著作权归本团队所有。委托方获得的是本报告的使用权，而非所有权或再分发权。

**纠错机制**：如 {{name}} 本人或相关方对报告内容有异议，欢迎提供可核实的补充材料。本团队将在收到材料后的合理时间内进行复核，并根据复核结果决定是否更新报告内容。

---

## 八、报告水印与溯源声明

> **⚠️ 安全声明**：本报告已嵌入隐形数字水印，包含案件编号、委托方标识及生成时间戳。水印信息不可见但可通过专用工具提取，任何未经授权的复制、传播或截图均可能暴露来源。如需验证水印完整性，请联系调查团队。
>
> **案件编号**：`{{case_id}}`
> **生成时间**：`{{generation_timestamp}}`
> **哈希校验**：`{{report_hash}}`

---

*报告完*
