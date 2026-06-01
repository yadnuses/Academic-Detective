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
│   ├─ data_forensics/         ← 数据层取证（统计反推 + 图像元数据 + 数据可用性验证 + 数据统计指纹检测）
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

#### 3.4 data_integrity_checker.py — 数据统计指纹检测（耿同学方法论）

**功能**：通过三种独立的统计方法检测实验数据中的可疑模式，基于"耿同学"统计学打假方法论。

**输入**：论文图表中的原始数值数据（Excel/CSV，通常几十到几百个数值）
**输出**：0-100 风险评分 + 每项发现的严重程度（HIGH/MEDIUM/LOW）+ JSON 信号

**三种检测方法**：
1. **尾数分布分析**：真实实验数据的尾数（0-9）应近似均匀分布，人工编造数据时会产生尾数偏好
2. **小数点一致性检测**：真实数据的小数位精度应有随机性，固定小数位模式是人工构造的痕迹
3. **数据重复检测**：独立生物实验中，完全重复的数据值应极为罕见

**判定标准**：
- 尾数分析：p < 0.05 且 Cramer's V > 0.3 → 异常
- 小数点一致性：重复组数 > 5 或最高重复 ≥ 3 次 → 异常
- 数据重复：重复值 > 5 个或最高重复 ≥ 3 次 → 异常

**典型发现**：
- 多个数据列中特定尾数出现频率是期望值的 3 倍以上
- 17-20% 的数据小数点后 2 位完全重复（正常应 < 5%）
- 关键数据列出现 3-4 次完全相同的数值

**人类介入点**：统计异常只是筛查工具，需排除特殊实验设计、数据预处理等合理解释后才能作为证据。

**红旗信号速查表**：

| 检测方法 | 红旗信号 | 严重程度 |
|:---|:---|:---:|
| 尾数分布 | 某尾数出现频率 ≥ 期望值的 3 倍 | HIGH |
| 尾数分布 | p < 0.001 且 Cramer's V > 0.5 | HIGH |
| 尾数分布 | 尾数 0 或 5 占比 > 20%（人工偏好"整数"） | MEDIUM |
| 小数点一致性 | 最高重复次数 ≥ 3（独立实验几乎不可能） | HIGH |
| 小数点一致性 | 小数点后 2 位重复率 > 15% | MEDIUM |
| 小数点一致性 | 所有数据的小数位数完全一致（如全部 .00） | HIGH |
| 数据重复 | 某数值出现 ≥ 4 次（极强造假证据） | HIGH |
| 数据重复 | ≥ 5 个不同数值各出现 ≥ 2 次 | HIGH |
| 数据重复 | 两组"独立实验"的原始数据完全相同 | HIGH |

> **注意**：上述红旗信号需结合实验背景判断。例如，计数数据（如细胞计数）的尾数分布可能天然不均；使用同一仪器的重复测量小数位可能一致。单一信号不足以定性，多信号交叉验证才有意义。

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

