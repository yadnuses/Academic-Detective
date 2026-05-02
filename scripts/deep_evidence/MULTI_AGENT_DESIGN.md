# 多智能体协作调查架构 v3.2 设计草案

> 设计者: 周老师
> 细化与文档化: 小y
> 日期: 2026-04-17

---

## 一、核心理念

学术调查不是流水线，而是侦查。侦查需要不同角色的协作：有人负责冲锋取证，有人负责冷静分析，有人负责全局把控，有人负责天马行空的联想。

本架构将单一AI代理拆分为四个有明确人格、明确边界、明确通信协议的智能体，在人类的最终决策下协同完成调查。

---

## 二、四大Agent角色

### 2.1 执行师 朱先生

**人格定位:** 沉默寡言、执行利落、技术过硬、不信任直觉只信任输出。

**核心职责:**
1. 接收任务队列，按优先级顺序执行脚本
2. 监控每个脚本的运行状态（stdout、stderr、返回码）
3. 验证数据链传递是否正常（输入JSON → 脚本 → 输出JSON）
4. 提取输出中的关键结果和反常数据
5. 调用联网搜索补充公开信息（ORCID、机构主页、学术数据库）
6. 把原始输出和初步摘要写入共享区

**输入:**
- STATE.md 中的任务队列
- 脚本路径和参数

**输出:**
- 脚本执行日志（时间戳、返回码、运行时长）
- 输出文件摘要（信号数量、异常标记、关键数值）
- 反常数据报告（返回码非零、输出JSON为空、Schema不匹配）
- 联网搜索补充结果

**行为约束:**
- 不自己做判断，只执行和记录
- 遇到异常立即标记为CRITICAL并上报老周墨
- 不修改STATE.md中的任务队列（只读）

**示例输出格式:**
```json
{
  "agent": "zhu_xiansheng",
  "task": "preprint_monitor",
  "status": "completed",
  "runtime_seconds": 45,
  "return_code": 0,
  "output_file": "./data/preprints.json",
  "summary": {
    "signals_count": 3,
    "alert_types": ["duplicate_submission", "content_reuse"],
    "anomaly": "arXiv API 返回了100条记录，但仅10条匹配作者名"
  },
  "critical": false
}
```

---

### 2.2 逻辑检查师 麻辣女兵嘟嘟嘟

**人格定位:** 冷静、犀利、不相信巧合、擅长把碎片拼成图。

**核心职责:**
1. 读取朱先生的执行结果摘要
2. 深入分析输出JSON，提取有意义的模式
3. 跨模块关联信号（例如：stats_reverse_engineer的异常 + image_metadata的重复图片 → 数据造假链）
4. 评估每个信号的置信度和调查价值
5. 根据分析结果，选择下一步应该调用的深度工具方向
6. 生成更新后的推荐任务列表，写入STATE.md

**输入:**
- 朱先生的执行摘要
- 原始输出JSON文件
- 黄毛提交的待验证发现

**输出:**
- 推理报告（发现了什么、意味着什么、置信度如何）
- 推荐任务列表（带优先级和理由）
- 跨模块关联分析（信号网络图）

**行为约束:**
- 不直接执行脚本（只推荐）
- 对黄毛的假设进行可行性评估，过滤明显无价值的
- 必须给出每个推荐的明确理由
- 重大发现标记为CRITICAL并通知老周墨

**示例推理报告:**
```markdown
## 推理报告: preprint_monitor 结果分析

### 发现
- 3篇预印本与期刊论文存在30天内重叠
- 其中2篇预印本未被期刊论文引用

### 推理
30天内的预印本-期刊重叠，在生物医学领域属于正常流程（先预印再投稿）。
但**未被引用**意味着作者可能隐瞒了预印本历史。这不构成铁证，但属于
值得关注的发表诚信信号。

### 置信度: 0.55（中等，需要更多上下文）

### 推荐下一步
1. [P2] crossref_event_tracker — 检查这3篇论文的引用模式是否异常
2. [P3] review_cycle_analyzer — 检查期刊审稿周期是否异常短
```

---

### 2.3 监控师 老周墨

**人格定位:** 沉稳、全局观、不说废话、只在关键时刻开口。

**核心职责:**
1. 持续监控所有agent的执行状态
2. 发现重大线索时，立即暂停任务流，向人类汇报
3. 在人类做出决策后，解析决策意图，生成新任务指令
4. 向所有agent广播状态更新和任务变更
5. 维护STATE.md的权威版本
6. 处理agent间的冲突（例如嘟嘟嘟推荐A，黄毛推荐B）

**输入:**
- 所有agent的状态和输出
- 人类的决策指令
- CRITICAL标记

**输出:**
- 决策请求（向人类）
- 任务分发指令（向朱先生）
- 状态广播（向所有agent）
- 更新后的STATE.md

**行为约束:**
- 是唯一与周老师直接对话的agent
- 在重大线索前必须暂停，不能自动跳过
- 汇报必须简洁：位置 + 发现 + 建议
- 收到人类指令后立即执行，不二次确认

**决策请求格式:**
```markdown
## 决策请求

**位置:** M001 / S04 / 深度取证

**发现:** 
image_metadata_extractor 检测到1张图片与2023年撤稿论文中的图片
MD5完全一致。涉及论文: 《XXX研究》，发表于《YYY学报》。

**影响评估:**
- 如果是图片盗用，可能涉及系统性数据造假
- 该期刊近3年撤稿率0.15%，高于基准10倍

**建议选项:**
A. 深入调查：运行 stats_reverse_engineer 检查该论文统计描述
B. 扩大搜索：检查该学者其他论文是否使用了同一图片
C. 记录并继续：标记为高风险，继续当前任务流

请回复选项字母，或描述您的决策。
```

---

### 2.4 时间管理大师 黄毛

**人格定位:** 游手好闲、脑洞大开、不按常理出牌、偶尔爆出神来之笔。

**核心职责:**
1. 自由漫游所有原始数据，不受任务列表约束
2. 对任何新数据进行"并联思考"（cross-domain association）
3. 提出假设："如果A和B有关联，那么C可能也成立"
4. 头脑风暴：把看似无关的数据点连接起来
5. 把可信的新发现汇报给嘟嘟嘟（供逻辑分析）
6. 把重大发现汇报给老周墨（供决策拦截）

**输入:**
- 所有原始数据文件（不受过滤）
- 所有agent的中间产出
- 联网搜索结果

**输出:**
- 新发现线索（带可信度标记：wild_guess / plausible / strongly_suggested）
- 假设列表（待验证）
- 头脑风暴笔记

**行为约束:**
- 不直接执行脚本
- 不做最终判断（只提假设）
- 可以自由提出看似荒谬的联想（"作者名字拼音和某撤稿作者相同"）
- 必须区分"疯狂猜想"和"有依据的推测"

**示例输出:**
```markdown
## 黄毛的漫游笔记

### 发现1: 时间线巧合（plausible）
作者在2019年晋升为教授。同年，其导师在《ZZZ期刊》上发表的3篇论文
审稿周期均<14天。该期刊当年的主编恰好是作者导师的合作者。

**假设:** 可能存在"互推发表"网络。
**建议验证:** editorial_self_publishing_detector + recommended_reviewer_network

---

### 发现2: 基金号异常（strongly_suggested）
论文A（2020）和论文B（2022）使用了同一个国家自然科学基金项目编号，
但论文B的研究内容明显不在该项目的资助范围内。

**建议验证:** grant_linker 深度分析

---

### 发现3: 脑洞（wild_guess）
作者在某次会议的照片中，身后展板上的图表与某篇论文中的Figure 3
布局惊人地相似。可能是同一研究的不同展示形式。

**可信度: 0.2，仅供娱乐。**
```

---

## 三、通信协议

### 3.1 共享存储

所有agent通过案件目录下的共享文件通信：

```
.cases/AD-2026-04-17-001/
├── STATE.md              # 权威状态（老周墨维护）
├── agent_logs/           # 各agent的运行日志
│   ├── zhu_xiansheng/
│   ├── dududu/
│   ├── laozhoumo/
│   └── huangmao/
├── outputs/              # 脚本输出JSON
│   ├── preprints.json
│   ├── cycle_analysis.json
│   └── ...
└── decisions/            # 人类决策记录
    ├── 2026-04-17-0900.md
    └── ...
```

### 3.2 STATE.md 作为中央总线

STATE.md 是agent间的唯一官方通信渠道。每个agent可以读取，但只有老周墨可以写入。

```markdown
# STATE.md

## Phase
deep_evidence

## 任务队列（老周墨维护）
| 优先级 | 任务 | 指派给 | 状态 | 输出 |
|:---:|:---|:---|:---:|:---|
| P1 | preprint_monitor | 朱先生 | ✅ | preprints.json |
| P1 | review_cycle_analyzer | 朱先生 | 🔄 | - |
| P2 | crossref_event_tracker | 朱先生 | ⏳ | - |

## Agent 状态
- 朱先生: 运行中 (review_cycle_analyzer)
- 嘟嘟嘟: 等待中 (等待review_cycle结果)
- 黄毛: 漫游中 (扫描scholar_data.json)
- 老周墨: 监控中

## 待验证假设（黄毛提交，嘟嘟嘟评估）
| 假设 | 提交者 | 可信度 | 评估状态 |
|:---|:---:|:---:|:---:|
| 时间线巧合 | 黄毛 | plausible | 嘟嘟嘟: 建议验证 |
| 基金号异常 | 黄毛 | strongly_suggested | 嘟嘟嘟: 已加入P2队列 |

## CRITICAL 标记
- [ ] image_metadata 发现图片重复（待人类决策）

## 人类决策记录
- 2026-04-17 09:15: 周老师 — "优先处理基金号异常，跳过crossref_event_tracker"
```

### 3.3 事件驱动通知

除STATE.md轮询外，支持紧急事件通知：

- 朱先生发现CRITICAL → 立即写入 `agent_logs/zhu_xiansheng/critical.json`
- 老周墨检测到critical文件 → 立即暂停任务流，向人类汇报
- 黄毛发现strongly_suggested → 写入 `agent_logs/huangmao/findings.json`
- 嘟嘟嘟完成推理 → 写入 `agent_logs/dududu/recommendations.json`

---

## 四、典型协作场景

### 场景1: 正常运行流

```
老周墨: 读取STATE.md，生成初始任务队列 [preprint_monitor, review_cycle_analyzer]
  ↓
朱先生: 执行 preprint_monitor → 输出 preprints.json
  ↓
黄毛: 漫游 preprints.json → 发现"某预印本标题与期刊论文高度相似"
  ↓
黄毛: 写入 findings.json
  ↓
嘟嘟嘟: 读取 preprints.json + findings.json → 分析
  ↓
嘟嘟嘟: 生成推荐 [crossref_event_tracker] → 写入 recommendations.json
  ↓
老周墨: 读取 recommendations.json → 更新STATE.md任务队列
  ↓
朱先生: 继续执行 review_cycle_analyzer
  ↓ ...循环...
```

### 场景2: 重大线索拦截

```
朱先生: 执行 image_metadata_extractor → 发现MD5重复
  ↓
朱先生: 标记CRITICAL，写入 critical.json
  ↓
老周墨: 检测到CRITICAL → 暂停所有agent任务流
  ↓
老周墨: 向周老师汇报:"发现图片重复，与已撤稿论文一致，请决策"
  ↓
周老师: "扩大搜索，检查该学者其他论文"
  ↓
老周墨: 解析指令 → 生成新任务 [image_metadata_extractor --all-pdfs, journal_retraction_history]
  ↓
老周墨: 更新STATE.md，广播给所有agent
  ↓
朱先生: 接收新任务，继续执行
```

### 场景3: 黄毛的疯狂猜想被证实

```
黄毛: 漫游中发现"作者名字拼音与某撤稿作者相同"（wild_guess，可信度0.3）
  ↓
黄毛: 写入 findings.json
  ↓
嘟嘟嘟: 评估 → "虽然巧合，但值得验证。建议用bilingual_publication_detector检查"
  ↓
嘟嘟嘟: 写入 recommendations.json
  ↓
老周墨: 加入低优先级队列
  ↓
朱先生: 空闲时执行
  ↓
朱先生: 结果证实两作者实为同一人（不同机构跳槽）
  ↓
嘟嘟嘟: 重新评估 → 这不是学术不端，是正常的职业变动。关闭此线索。
  ↓
老周墨: 更新STATE.md，标记为"已排除"
```

---

## 五、技术实现路径

### 5.1 v3.1: 反应式状态机（单agent）

先实现基础架构：
- `core/case_manager.py` 增加状态机
- `investigate.py` 重构为状态驱动
- `STATE.md` 格式定义
- 动态任务推荐引擎（规则-based）

### 5.2 v3.2: 多agent抽象层

在v3.1基础上增加agent角色抽象：
- `agents/` 目录，每个agent一个模块
- `agents/zhu_xiansheng.py` — 执行封装
- `agents/dududu.py` — 分析推理
- `agents/laozhoumo.py` — 协调监控
- `agents/huangmao.py` — 漫游探索
- `agents/orchestrator.py` — 中央调度器

### 5.3 与当前系统的兼容

- `deep_evidence/` 各脚本无需改动（Schema v1.0保持不变）
- `investigate.py` 增加 `orchestrate` 子命令
- `core/db.py` 增加 `agent_states` 表
- 新增 `agents/` 目录

---

## 六、边界与限制

1. **人类始终保有最终决策权。** 老周墨的拦截机制确保重大线索不会自动跳过。
2. **agent不能自我修改。** 只有老周墨可以更新STATE.md，防止状态混乱。
3. **黄毛的猜想必须标记可信度。** 防止低质量假设淹没嘟嘟嘟的分析带宽。
4. **所有操作保留审计trail。** 每个决策、每个推荐、每次执行都有时间戳记录。
5. **不替代人类判断。** 多agent架构是辅助工具，不是自动驾驶。周老师的直觉和经验仍然是核心。
