# 学术调查系统 v3.1 最终架构方案

> 设计基础: GSD-CC 项目管理方法论 + 多智能体协作思路
> 核心原则: 状态机定义阶段边界，任务序列根据实时反馈动态组装
> 日期: 2026-04-17

---

## 一、架构总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         人类决策者 (周老师)                                   │
│              最高权限: 决策、插单、回退、终止                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ↑ ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                      协调层 (Orchestrator)                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  朱先生      │  │ 嘟嘟嘟       │  │  黄毛        │  │ 老周墨       │        │
│  │ 执行师       │  │ 逻辑检查师   │  │ 漫游者       │  │ 监控师       │        │
│  │ 脚本执行     │  │ 推理分析     │  │ 并联思考     │  │ 人机接口     │        │
│  │ 数据传递     │  │ 工具选择     │  │ 头脑风暴     │  │ 决策拦截     │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│         │                │                │                │                │
│         └────────────────┴────────────────┴────────────────┘                │
│                           通过 STATE.md 通信                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
┌───────────────────────┐ ┌───────────────────────┐ ┌───────────────────────┐
│    反应式状态机        │ │   动态任务推荐引擎     │ │     案件存储层        │
│  (Phase State Machine) │ │  (Rule-based Engine)   │ │  (SQLite + STATE.md)  │
└───────────────────────┘ └───────────────────────┘ └───────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     现有 deep_evidence 脚本层 (v3.0)                         │
│  data_forensics / publication_trace / ethics_audit / peer_review_intel      │
│                    统一 Schema v1.0: {meta, signals[], details}             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、反应式状态机 (v3.1 核心)

### 2.1 阶段定义

阶段是硬边界，必须按顺序通过。每个阶段内部的工具调用是动态的。

```
initialized → collected → validated → analyzed → deep_evidence → aggregated → reported → reviewed → archived
```

| 阶段 | 准入条件 | 退出条件 | 动态性 |
|:---|:---|:---|:---|
| `initialized` | 案件目录已创建 | config.yaml通过基础校验 | 固定 |
| `collected` | config.yaml有效 | 至少一个数据源文件存在 | 固定 |
| `validated` | 数据源已导入 | scholar_data.json通过Schema校验 | 固定 |
| `analyzed` | scholar_data.json有效 | analysis/启用模块全部运行 | 固定 |
| `deep_evidence` | analysis输出存在 | **推荐工具全部运行** | **动态组装** |
| `aggregated` | deep_evidence输出存在 | signal_aggregator运行完成 | 固定 |
| `reported` | aggregated_signals.json存在 | 报告文件已生成 | 固定 |
| `reviewed` | 报告已生成 | 人类确认报告质量合格 | 固定 |
| `archived` | 报告已复核 | 案件目录打包，STATE.md标记完成 | 固定 |

### 2.2 动态阶段 deep_evidence 的任务组装逻辑

这是整个架构的核心创新点。系统不预设 deep_evidence 阶段要运行哪些工具，而是根据 `analyzed` 阶段的产出实时推荐。

**推荐引擎规则库:**

```python
RECOMMENDATION_RULES = [
    {
        "id": "R01",
        "trigger": "analysis/common_heuristics.json has alerts",
        "tools": ["publication_trace/preprint_monitor"],
        "priority": 1,
        "reason": "通用异常触发预印本交叉验证"
    },
    {
        "id": "R02",
        "trigger": "analysis/citation_profiler.json has citation_cartel",
        "tools": ["data_forensics/stats_reverse_engineer", "data_forensics/image_metadata_extractor"],
        "priority": 1,
        "reason": "引用结构异常暗示数据问题"
    },
    {
        "id": "R03",
        "trigger": "scholar_data.json papers contain 'clinical trial' or 'patient'",
        "tools": ["ethics_audit/ethics_statement_parser", "ethics_audit/clinical_trial_registry_checker"],
        "priority": 2,
        "reason": "临床相关研究必须验证伦理合规"
    },
    {
        "id": "R04",
        "trigger": "scholar_data.json has both CJK and English titles",
        "tools": ["publication_trace/bilingual_publication_detector"],
        "priority": 2,
        "reason": "双语发表是国内学者常见风险点"
    },
    {
        "id": "R05",
        "trigger": "scholar_data.json any journal count >= 3",
        "tools": ["peer_review_intel/review_cycle_analyzer"],
        "priority": 2,
        "reason": "高频期刊需要审查周期异常"
    },
    {
        "id": "R06",
        "trigger": "analysis/paper_quality_rubric.json has cluster of C/D grades",
        "tools": ["peer_review_intel/editorial_self_publishing_detector", "peer_review_intel/recommended_reviewer_network"],
        "priority": 3,
        "reason": "低质量集群可能暗示审稿流程被绕过"
    },
    {
        "id": "R07",
        "trigger": "papers have DOIs",
        "tools": ["publication_trace/crossref_event_tracker"],
        "priority": 3,
        "reason": "DOI可查询异常注意力模式"
    },
    {
        "id": "R08",
        "trigger": "scholar_data.json has journal ISSNs",
        "tools": ["peer_review_intel/journal_retraction_history"],
        "priority": 4,
        "reason": "建立期刊风险基准"
    },
    {
        "id": "R09",
        "trigger": "scholar_data.json has conference papers",
        "tools": ["publication_trace/conference_paper_mapper"],
        "priority": 3,
        "reason": "会议论文需检查是否已转投期刊"
    },
]
```

**推荐去重与排序:**

1. 评估所有规则，收集触发的工具列表
2. 按 priority 排序（1最优先，4最低）
3. 同一工具被多条规则推荐只算一次，取最高priority
4. 默认 confidence 阈值过滤（可配置）
5. 输出推荐列表，人类确认后执行

### 2.3 反馈循环

```
脚本A运行 → 产出JSON → 推荐引擎读取 → 触发新规则 → 推荐脚本B
  ↑                                                    ↓
  └────── 脚本B产出 → 推荐引擎读取 → 可能触发脚本C ────┘
```

**置信度传播:**

- 脚本A发现信号(confidence=0.8)
- 触发规则推荐脚本B
- 脚本B运行后信号confidence=0.75
- 聚合器将A和B的信号关联，提升至0.85
- 触发更高优先级规则推荐脚本C

**负反馈同样记录:**

- `preprint_monitor` 零信号 → "经查，未发现预印本重叠"
- `clinical_trial_registry_checker` 零信号 → "无临床相关论文"

---

## 三、多agent协作层 (v3.2)

### 3.1 角色定义

| 角色 | 核心职责 | 输入 | 输出 | 行为约束 |
|:---|:---|:---|:---|:---|
| **朱先生** | 脚本执行、数据链监控、联网搜索 | STATE.md任务队列 | 执行摘要JSON、反常报告 | 只执行不判断；遇CRITICAL立即上报 |
| **嘟嘟嘟** | 结果分析、推理、深度工具选择 | 执行结果、黄毛假设 | 推理报告、推荐列表 | 不过滤脑洞但评估可行性；必须给理由 |
| **黄毛** | 数据漫游、并联思考、头脑风暴 | 所有原始数据 | 假设列表（wild_guess/plausible/strongly_suggested） | 不判断对错；区分可信度等级 |
| **老周墨** | 全局监控、人机接口、决策拦截 | 所有agent状态、CRITICAL标记 | 决策请求、任务分发指令 | 唯一写入STATE.md；汇报必须简洁 |

### 3.2 通信协议

**共享存储结构:**

```
.cases/AD-2026-04-17-001/
├── STATE.md              # 权威状态（老周墨维护）
├── agent_logs/
│   ├── zhu_xiansheng/    # 执行摘要 + critical.json
│   ├── dududu/           # 推理报告 + recommendations.json
│   ├── huangmao/         # 漫游笔记 + findings.json
│   └── laozhoumo/        # 决策记录 + 广播指令
├── outputs/              # 脚本输出JSON
├── decisions/            # 人类决策存档
└── evidence_chains/      # 证据链构建结果
```

**事件驱动通知:**

- 朱先生发现CRITICAL → 写入 `agent_logs/zhu_xiansheng/critical.json`
- 老周墨检测到critical文件 → 暂停任务流，向人类汇报
- 黄毛发现strongly_suggested → 写入 `agent_logs/huangmao/findings.json`
- 嘟嘟嘟完成推理 → 写入 `agent_logs/dududu/recommendations.json`

### 3.3 典型协作场景

**场景1: 正常运行流**

```
老周墨: 读取STATE.md，生成初始任务队列
  ↓
朱先生: 执行 preprint_monitor → 输出 preprints.json
  ↓
黄毛: 漫游 preprints.json → 发现"某预印本标题与期刊论文高度相似"
  ↓
嘟嘟嘟: 读取 preprints.json + findings.json → 分析 → 推荐 crossref_event_tracker
  ↓
老周墨: 更新STATE.md任务队列
  ↓
朱先生: 继续执行 review_cycle_analyzer
  ↓ ...循环...
```

**场景2: 重大线索拦截**

```
朱先生: 执行 image_metadata_extractor → 发现MD5重复
  ↓
朱先生: 标记CRITICAL → 写入 critical.json
  ↓
老周墨: 检测到CRITICAL → 暂停所有agent任务流
  ↓
老周墨: 向周老师汇报:"发现图片重复，与已撤稿论文一致，请决策"
  ↓
周老师: "扩大搜索，检查该学者其他论文"
  ↓
老周墨: 解析指令 → 生成新任务 → 广播给所有agent
  ↓
朱先生: 接收新任务，继续执行
```

**场景3: 反馈实时调整**

```
规则引擎初始推荐: [preprint_monitor, review_cycle_analyzer]
  ↓
朱先生执行 preprint_monitor → 发现 suspicious_gap (confidence 0.85)
  ↓
嘟嘟嘟分析: "期刊早于预印本70天，物理上不可能"
  ↓
嘟嘟嘟动态插入推荐: crossref_event_tracker（验证外部质疑痕迹）
  ↓
老周墨更新STATE.md: 队列变为 [review_cycle_analyzer, crossref_event_tracker]
  ↓
黄毛漫游 review_cycle结果 → 发现"该期刊主编是作者导师的合作者"
  ↓
嘟嘟嘟分析: 新增关联假设 → 推荐 editorial_self_publishing_detector
  ↓
老周墨更新STATE.md: 队列变为 [crossref_event_tracker, editorial_self_publishing_detector]
```

---

## 四、STATE.md 格式规范

```markdown
# Case State: AD-2026-04-17-001

## Phase
deep_evidence

## Progress
| Stage | Status | Tool | Output | Signals | Notes |
|:---|:---:|:---|:---|:---:|:---|
| initialized | ✅ | - | - | - | - |
| collected | ✅ | data_importer | cnki_results.json | - | - |
| validated | ✅ | data_validator | scholar_data.json | - | - |
| analyzed | ✅ | text_profiler | text_profiles.json | 0 | - |
| analyzed | ✅ | citation_profiler | citation_audit.json | 3 | 发现引用卡特尔 |
| deep_evidence | 🔄 | preprint_monitor | preprints.json | 1 | suspicious_gap 0.85 |
| deep_evidence | ⏳ | review_cycle_analyzer | (recommended) | - | R05触发 |
| deep_evidence | ⏳ | crossref_event_tracker | (recommended) | - | 嘟嘟嘟动态插入 |
| aggregated | ⏳ | - | - | - | - |
| reported | ⏳ | - | - | - | - |

## Recommendations (auto-generated)
| Priority | Tool | Trigger Rule | Reason |
|:---:|:---|:---|:---|
| P1 | review_cycle_analyzer | R05 | 高频期刊《XX学报》出现5次 |
| P2 | crossref_event_tracker | 动态插入 | suspicious_gap需验证外部质疑 |
| P3 | ethics_statement_parser | R03 | 2篇论文涉及"患者"关键词 |

## CRITICAL
- [ ] suspicious_gap — 期刊早于预印本70天 (待人类决策)

## Human Decisions
- 2026-04-17 08:30: 跳过 bilingual_publication_detector（学者无英文论文）
- 2026-04-17 08:45: 手动插入 image_metadata_extractor（某篇论文图片可疑）

## UNIFY Records
### S01 基础数据采集
- 计划: 采集知网+万方数据
- 实际: 万方数据库无权限，仅用知网
- 偏差: 数据源减少一个
- 决策: 补充WoS数据，已在S02中完成
```

---

## 五、技术实现路径

### 5.1 第一阶段: v3.1 反应式状态机（立即实施）

**改动范围:**

| 文件 | 改动内容 | 工作量 |
|:---|:---|:---:|
| `core/case_manager.py` | 增加阶段状态机（9个状态 + 转换规则） | 中 |
| `core/db.py` | 增加 `case_state`, `recommendations`, `decisions` 表 | 小 |
| `investigate.py` | `step`/`advance` 重构为状态驱动 | 中 |
| `investigate.py` | 新增 `regress` 命令（回退阶段） | 小 |
| `investigate.py` | 新增 `add-task` 命令（手动插单） | 小 |
| `core/recommendation_engine.py` | **新增** 动态任务推荐引擎（规则库 + 评估器） | 中 |
| `.case/STATE.md` | 新增，人类可读的状态快照 | 小 |

**关键设计:**
- `recommendation_engine.py` 是纯规则引擎，读取JSON输出，评估规则触发条件，生成推荐列表
- 规则库是Python字典，可扩展，新规则只需追加到 `RECOMMENDATION_RULES`
- 负反馈自动记录（零信号也写入STATE.md）

### 5.2 第二阶段: v3.2 多agent协作层（后续规划）

**改动范围:**

| 文件/目录 | 改动内容 | 工作量 |
|:---|:---|:---:|
| `agents/` | **新增** 目录，包含4个agent模块 | 大 |
| `agents/zhu_xiansheng.py` | 执行封装 + 数据链监控 | 中 |
| `agents/dududu.py` | 推理分析 + 推荐生成 | 中 |
| `agents/huangmao.py` | 数据漫游 + 假设生成 | 中 |
| `agents/laozhoumo.py` | 协调监控 + 人机接口 | 中 |
| `agents/orchestrator.py` | 中央调度器 | 中 |
| `investigate.py` | 新增 `orchestrate` 子命令 | 小 |
| `core/db.py` | 增加 `agent_states` 表 | 小 |

**关键设计:**
- agent通过文件系统共享状态（STATE.md + agent_logs/）
- 每个agent是独立的subagent实例，可并行启动
- `orchestrator.py` 负责启动、监控、暂停agent
- 老周墨agent是唯一与周老师对话的agent

---

## 六、与现有系统的兼容

| 模块 | 是否需要改动 | 说明 |
|:---|:---:|:---|
| `deep_evidence/` 14个脚本 | ❌ 不需要 | Schema v1.0保持不变 |
| `analysis/` 7个模块 | ❌ 不需要 | 输出格式保持不变 |
| `network/` 5个模块 | ❌ 不需要 | 输出格式保持不变 |
| `domestic/` `international/` `cross_border/` | ❌ 不需要 | 轨道层保持不变 |
| `core/utils.py` | ✅ 小幅扩展 | 增加STATE.md读写辅助函数 |
| `investigate.py` | ✅ 中度重构 | step/advance/status改为状态驱动 |

---

## 七、边界与红线

1. **人类始终保有最终决策权。** 重大线索必须拦截，不能自动跳过。
2. **agent不能自我修改STATE.md。** 只有老周墨可以写入。
3. **黄毛的猜想必须标记可信度。** 防止低质量假设淹没分析带宽。
4. **所有操作保留审计trail。** 每个决策、每个推荐、每次执行都有时间戳。
5. **不替代人类判断。** 多agent架构是辅助工具，不是自动驾驶。
6. **免费API优先原则不变。** agent的联网搜索和工具调用仍只使用公开免费资源。
7. **半自动原则不变。** 不主动与外部实体通信，不做主观判断。

---

## 八、关键创新点总结

| 创新 | 来源 | 学术调查系统的适配 |
|:---|:---|:---|
| **状态驱动工作流** | GSD-CC | 阶段硬边界 + 任务动态组装 |
| **强制复盘UNIFY** | GSD-CC | 每个阶段结束记录实际vs计划 |
| **反应式任务推荐** | 原创 | 根据上一阶段产出实时生成推荐 |
| **多agent角色分工** | 周老师创意 | 执行、分析、漫游、监控四角色 |
| **反馈实时调整** | 周老师要求 | 规则引擎根据产出动态更新队列 |
| **负反馈记录** | 原创 | 零信号同样记录，构成完整审计 |
| **可信度分级** | 原创 | wild_guess / plausible / strongly_suggested |
