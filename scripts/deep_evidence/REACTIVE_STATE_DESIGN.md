# 反应式案件状态机设计草案 (v3.1)

> 核心原则: 状态机只定义阶段边界和准入条件，任务序列根据实时产出动态组装。

---

## 一、与GSD-CC的本质区别

| 维度 | GSD-CC (软件开发) | 学术调查系统 (v3.1) |
|:---|:---|:---|
| 任务来源 | 规划阶段预设，顺序固定 | 根据上一阶段的发现实时生成 |
| 切片内容 | 2-7个已知任务 | 阶段目标明确，具体工具动态选择 |
| 用户角色 | 确认/否决推荐 | 确认/否决/插单/回退 |
| 异常处理 | 任务失败则重试或跳过 | 发现新线索则插入新切片 |
| 完成标准 | 所有AC通过 | 人类判断"足够" |

---

## 二、阶段定义 (Phases)

阶段是硬边界，必须按顺序通过。但每个阶段内部的工具调用是动态的。

```
initialized → collected → validated → analyzed → deep_evidence → aggregated → reported → reviewed → archived
```

| 阶段 | 准入条件 | 退出条件 |
|:---|:---|:---|
| `initialized` | 案件目录已创建，config.yaml存在 | 用户确认基础信息已填写 |
| `collected` | config.yaml通过基础校验 | 至少一个数据源文件存在 |
| `validated` | 数据源文件已导入 | scholar_data.json通过Schema校验 |
| `analyzed` | scholar_data.json存在且有效 | analysis/所有启用模块已运行 |
| `deep_evidence` | analysis输出存在 | 推荐的deep_evidence工具全部运行 |
| `aggregated` | deep_evidence输出存在 | signal_aggregator运行完成 |
| `reported` | aggregated_signals.json存在 | 报告文件已生成 |
| `reviewed` | 报告已生成 | 人类确认报告质量合格 |
| `archived` | 报告已复核 | 案件目录打包，STATE.md标记完成 |

---

## 三、动态任务推荐引擎

### 3.1 触发点

每个阶段结束后，系统自动运行推荐引擎。

### 3.2 推荐规则示例 (analyzed → deep_evidence)

```python
RULES = [
    # 规则1: 如果发现C01-C07异常 → 预印本监控
    {
        "if": "analysis/common_heuristics.json has alerts",
        "then": ["publication_trace/preprint_monitor"],
        "priority": 1,
        "reason": "通用异常触发预印本交叉验证"
    },
    # 规则2: 如果发现引用卡特尔 → 统计反推
    {
        "if": "analysis/citation_profiler.json has citation_cartel",
        "then": ["data_forensics/stats_reverse_engineer", "data_forensics/image_metadata_extractor"],
        "priority": 1,
        "reason": "引用结构异常暗示数据问题"
    },
    # 规则3: 如果涉及临床试验关键词 → 伦理审计
    {
        "if": "scholar_data.json papers contain 'clinical trial' or 'patient'",
        "then": ["ethics_audit/ethics_statement_parser", "ethics_audit/clinical_trial_registry_checker"],
        "priority": 2,
        "reason": "临床相关研究必须验证伦理合规"
    },
    # 规则4: 如果同时有中英文论文 → 双语检测
    {
        "if": "scholar_data.json has both CJK and English titles",
        "then": ["publication_trace/bilingual_publication_detector"],
        "priority": 2,
        "reason": "双语发表是国内学者常见风险点"
    },
    # 规则5: 如果某期刊出现≥3次 → 审稿周期分析
    {
        "if": "scholar_data.json any journal count >= 3",
        "then": ["peer_review_intel/review_cycle_analyzer"],
        "priority": 2,
        "reason": "高频期刊需要审查周期异常"
    },
    # 规则6: 如果发现低质量论文集群 → 编辑自发表检测
    {
        "if": "analysis/paper_quality_rubric.json has cluster of C/D grades",
        "then": ["peer_review_intel/editorial_self_publishing_detector", "peer_review_intel/recommended_reviewer_network"],
        "priority": 3,
        "reason": "低质量集群可能暗示审稿流程被绕过"
    },
    # 规则7: 如果Crossref事件数据显示异常 → 事件追踪
    {
        "if": "papers have DOIs",
        "then": ["publication_trace/crossref_event_tracker"],
        "priority": 3,
        "reason": "DOI可查询异常注意力模式"
    },
    # 规则8: 撤稿历史基线
    {
        "if": "scholar_data.json has journal ISSNs",
        "then": ["peer_review_intel/journal_retraction_history"],
        "priority": 4,
        "reason": "建立期刊风险基准"
    },
    # 规则9: 会议论文映射
    {
        "if": "scholar_data.json has conference papers",
        "then": ["publication_trace/conference_paper_mapper"],
        "priority": 3,
        "reason": "会议论文需检查是否已转投期刊"
    },
]
```

### 3.3 推荐去重与排序

1. 收集所有触发的规则
2. 按priority排序（数字小优先）
3. 去重（同一工具被多条规则推荐只算一次）
4. 默认confidence阈值过滤（可配置）
5. 输出推荐列表，人类确认后执行

### 3.4 人类干预接口

```bash
# 接受推荐并执行
investigate.py advance

# 跳过某项推荐
investigate.py advance --skip preprint-monitor

# 手动插入额外工具
investigate.py add-task --tool data_forensics/stats_reverse_engineer --papers ./data/papers.json

# 回退到上一阶段（重新分析）
investigate.py regress --to analyzed

# 查看当前状态和推荐
investigate.py status
```

---

## 四、反馈循环设计

### 4.1 产出即反馈

每个脚本运行后，产出文件本身就是反馈源。系统不需要额外的人类输入就能评估下一步。

### 4.2 置信度传播

```
脚本A发现信号(confidence=0.8)
  → 触发规则推荐脚本B
  → 脚本B运行后信号confidence=0.75
  → 聚合器将A和B的信号关联，提升至0.85
  → 触发更高优先级的规则推荐脚本C
```

### 4.3 负反馈（什么都没发现也是信号）

如果一个工具运行后没有任何信号，这也应该被记录。例如：
- `preprint_monitor` 运行后零信号 → 说明该学者没有预印本历史
- `clinical_trial_registry_checker` 运行后零信号 → 说明没有临床相关论文

这些负记录在报告中同样有价值（"经查，未发现预印本重叠"）。

---

## 五、STATE.md 格式

```markdown
# Case State: AD-2026-04-17-001

## Phase
analyzed

## Progress
| Stage | Status | Tool | Output | Signals |
|:---|:---:|:---|:---|:---:|
| initialized | ✅ | - | - | - |
| collected | ✅ | data_importer | cnki_results.json | - |
| validated | ✅ | data_validator | scholar_data.json | - |
| analyzed | ✅ | text_profiler | text_profiles.json | 0 |
| analyzed | ✅ | citation_profiler | citation_audit.json | 3 |
| analyzed | ✅ | paper_quality_rubric | quality_scores.json | 2 |
| deep_evidence | 🔄 | preprint_monitor | preprints.json | 1 |
| deep_evidence | ⏳ | review_cycle_analyzer | (recommended) | - |
| deep_evidence | ⏳ | ethics_statement_parser | (recommended) | - |
| aggregated | ⏳ | - | - | - |
| reported | ⏳ | - | - | - |

## Recommendations (auto-generated)
1. [P1] review_cycle_analyzer — 高频期刊《XX学报》出现5次
2. [P2] ethics_statement_parser — 2篇论文涉及"患者"关键词
3. [P3] crossref_event_tracker — 全部论文有DOI，可查询

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

## 六、与现有系统的兼容

- `core/case_manager.py` 增加状态机方法
- `core/db.py` 增加 `case_state`, `slice_records`, `recommendations` 表
- `investigate.py` 的 `step`/`advance`/`status` 命令重构为状态驱动
- `deep_evidence/` 各脚本无需改动（只需产出遵循Schema v1.0）
- 新增 `investigate.py regress` 和 `investigate.py add-task` 命令
- 新增 `.case/STATE.md` 作为人类可读的状态快照（与SQLite互补）
