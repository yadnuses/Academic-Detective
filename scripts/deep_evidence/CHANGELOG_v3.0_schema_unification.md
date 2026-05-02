# Deep Evidence Layer — Schema 统一化工作日志

> 日期: 2026-04-17
> 操作人: 小y (AI Agent)
> 背景: v3.0 deep_evidence 层 14 个脚本由 3 个 subagent 并行实现，audit 发现风格和数据传递渠道不统一，需重构。

---

## 一、问题发现

### 1.1 风格偏差

| 偏差 | 涉及脚本数 | 具体表现 |
|:---|:---:|:---|
| 缺少 `--verbose` | 2 | preprint_monitor.py, review_cycle_analyzer.py |
| 缺少输入存在性检查 | 2 | editorial_self_publishing_detector.py, review_cycle_analyzer.py |
| `build_parser()` 返回类型不一致 | 10 | 多数脚本缺少 `-> argparse.ArgumentParser` |

### 1.2 数据传递渠道断裂（核心问题）

`signal_aggregator.py` 原设计意图是统一消费所有 deep_evidence 信号，但实际只能识别 `signals` / `alerts` / `anomalies` / `results` 四个顶层键。各脚本输出结构差异导致以下问题：

| 脚本 | 原顶层键 | 聚合器能否消费 | 问题 |
|:---|:---|:---:|:---|
| clinical_trial_registry_checker.py | `papers` + `summary` | ❌ | 信号藏在 `papers[*].alerts` 里 |
| ethics_statement_parser.py | `results` | ⚠️ | 消费了但内容是完整记录而非信号 |
| evidence_chain_builder.py | `chains` | ❌ | 完全不可见 |
| bilingual_publication_detector.py | `pairs` | ❌ | 完全不可见 |
| conference_paper_mapper.py | `matches` | ❌ | 完全不可见 |
| recommended_reviewer_network.py | `conflicts` | ❌ | 完全不可见 |
| editorial_self_publishing_detector.py | `results` + `alerts` | ❌ | `results` 先被匹配，但里面是统计数据 |

字段名同样混乱：
- 信号类型: `alert_type` / `flag_type` / `overlap_type`
- 置信度: `float` vs 字符串 `"low"` / `"medium"` / `"high"`
- 描述: `explanation` / `reason` / `detail`

---

## 二、解决方案

### 2.1 制定统一契约

定义 **Deep Evidence Signal Schema v1.0**（见 `SIGNAL_SCHEMA.md`），要求所有脚本输出包含：

```json
{
  "meta": {
    "script": "snake_case_name",
    "version": "1.0",
    "timestamp": "ISO-8601",
    "input_file": "..."
  },
  "signals": [
    {
      "type": "snake_case_signal_id",
      "description": "人类可读描述，≤200字",
      "confidence": 0.82,
      "paper_id": "DOI或标题（可选）",
      "source": "与 meta.script 一致",
      "evidence": {}
    }
  ],
  "details": { ... 原始详细数据保留 ... }
}
```

关键规则：
- `confidence` 必须是 `[0.0, 1.0]` 范围内的 `float`，禁止字符串
- `type` 必须使用 `snake_case`
- `source` 必须与 `meta.script` 一致
- `signal_aggregator.py` 只消费 `signals` 数组

### 2.2 修改策略

每个脚本：
1. 将检测到的异常转换为统一格式的 `signals` 数组
2. 原始详细数据保留在 `details` 中供人工查阅
3. 修复风格小偏差（`--verbose`、输入检查、返回类型）
4. CLI 接口保持向后兼容

---

## 三、执行过程

### 3.1 分三组并行重构

| 组 | 负责脚本 | subagent 状态 |
|:---|:---|:---:|
| Group A | stats_reverse_engineer.py, image_metadata_extractor.py, signal_aggregator.py, evidence_chain_builder.py | ✅ 完成 |
| Group B | ethics_statement_parser.py, clinical_trial_registry_checker.py, conference_paper_mapper.py, bilingual_publication_detector.py, preprint_monitor.py, crossref_event_tracker.py | ✅ 完成 |
| Group C | review_cycle_analyzer.py, editorial_self_publishing_detector.py, recommended_reviewer_network.py, journal_retraction_history.py | ✅ 完成 |

### 3.2 各脚本变更详情

#### data_forensics/

| 脚本 | 变更前 | 变更后 |
|:---|:---|:---|
| `stats_reverse_engineer.py` | 顶层 `anomalies` | 顶层 `signals` + `details.anomalies` |
| `image_metadata_extractor.py` | 顶层 `alerts` | 顶层 `signals` + `details.images` + `details.alerts` |

#### publication_trace/

| 脚本 | 变更前 | 变更后 |
|:---|:---|:---|
| `preprint_monitor.py` | 顶层 `alerts` + `preprints` | 顶层 `signals` + `details.preprints` + `details.alerts` |
| `crossref_event_tracker.py` | 顶层 `alerts` + `summaries` | 顶层 `signals` + `details.summaries` + `details.alerts` |
| `conference_paper_mapper.py` | 顶层 `matches` | 顶层 `signals` + `details.matches` |
| `bilingual_publication_detector.py` | 顶层 `pairs` | 顶层 `signals` + `details.pairs` |

#### ethics_audit/

| 脚本 | 变更前 | 变更后 |
|:---|:---|:---|
| `ethics_statement_parser.py` | 顶层 `results` | 顶层 `signals` + `details.results` |
| `clinical_trial_registry_checker.py` | 顶层 `papers` + `summary` | 顶层 `signals` + `details.papers` + `details.summary` |

#### peer_review_intel/

| 脚本 | 变更前 | 变更后 |
|:---|:---|:---|
| `review_cycle_analyzer.py` | 顶层 `alerts` + `timelines` + `benchmarks` | 顶层 `signals` + `details.timelines` + `details.benchmarks` + `details.alerts` |
| `editorial_self_publishing_detector.py` | 顶层 `results` + `alerts` | 顶层 `signals` + `details.results` + `details.alerts` |
| `recommended_reviewer_network.py` | 顶层 `conflicts` + `summaries` | 顶层 `signals` + `details.conflicts` + `details.summaries` |
| `journal_retraction_history.py` | 顶层 `alerts` + `profiles` | 顶层 `signals` + `details.profiles` + `details.alerts` |

#### evidence_compiler/

| 脚本 | 变更前 | 变更后 |
|:---|:---|:---|
| `signal_aggregator.py` | 扫描 `signals`/`alerts`/`anomalies`/`results` 四个键 | 只扫描 `signals` 键；大幅简化 `_normalize_signal()` |
| `evidence_chain_builder.py` | 顶层 `chains` | 顶层 `signals` + `details.chains`；每条链生成一个 `evidence_chain` 信号 |

### 3.3 信号类型注册表

重构后统一使用的 `type` 值（部分示例）：

| type | 来源脚本 | 含义 |
|:---|:---|:---|
| `duplicate_submission` | preprint_monitor | 预印本与期刊投稿日期重叠 |
| `fast_cycle` | review_cycle_analyzer | 审稿周期异常短 |
| `impossible_sd` | stats_reverse_engineer | 报告的标准差不合理 |
| `duplicate_image_across_papers` | image_metadata_extractor | 同一图片出现在不同论文 |
| `missing_ethics_number` | ethics_statement_parser | 提及伦理但未提供批准号 |
| `unregistered_trial` | clinical_trial_registry_checker | 临床试验未注册 |
| `undisclosed_dual_publication` | conference_paper_mapper | 会议与期刊未互相引用 |
| `bilingual_pair` | bilingual_publication_detector | 中英文双语发表配对 |
| `suspicious_attention_spike` | crossref_event_tracker | 注意力在7天内集中爆发 |
| `high_self_journal_rate` | editorial_self_publishing_detector | 编辑在自管期刊发文占比过高 |
| `direct_coauthor_conflict` | recommended_reviewer_network | 推荐审稿人与作者有直接合著 |
| `high_retraction_journal` | journal_retraction_history | 期刊撤稿率显著高于基准 |
| `evidence_chain` | evidence_chain_builder | 多源信号编织的证据链 |

完整列表见 `SIGNAL_SCHEMA.md`。

---

## 四、验证结果

### 4.1 语法检查

```
14/14 脚本通过 python3 -m py_compile
investigate.py 通过语法检查
```

### 4.2 测试套件

```
pytest: 296 passed, 3 warnings in 3.73s
```

3 个 warnings 为预期的向后兼容 DeprecationWarning，属于设计行为。

### 4.3 Schema 覆盖率验证

所有 14 个脚本均包含 `meta` + `signals` + `details` 三个顶层键：

```
./data_forensics/image_metadata_extractor.py:  signals=1 details=1 meta=2
./data_forensics/stats_reverse_engineer.py:    signals=1 details=1 meta=1
./ethics_audit/clinical_trial_registry_checker.py: signals=1 details=1 meta=1
./ethics_audit/ethics_statement_parser.py:     signals=1 details=1 meta=1
./evidence_compiler/evidence_chain_builder.py: signals=2 details=1 meta=1
./evidence_compiler/signal_aggregator.py:      signals=2 details=1 meta=1
./peer_review_intel/editorial_self_publishing_detector.py: signals=1 details=1 meta=1
./peer_review_intel/journal_retraction_history.py: signals=1 details=1 meta=1
./peer_review_intel/recommended_reviewer_network.py: signals=2 details=2 meta=2
./peer_review_intel/review_cycle_analyzer.py:  signals=1 details=1 meta=1
./publication_trace/bilingual_publication_detector.py: signals=1 details=1 meta=1
./publication_trace/conference_paper_mapper.py: signals=1 details=1 meta=1
./publication_trace/crossref_event_tracker.py:  signals=1 details=1 meta=1
./publication_trace/preprint_monitor.py:        signals=1 details=1 meta=1
```

`signal_aggregator.py` 消费者逻辑确认：
```python
candidates = data.get("signals", [])  # 仅消费 signals 键
```

---

## 五、数据流图（重构后）

```
┌─────────────────────────────────────────────────────────────┐
│  14 个 deep_evidence 脚本                                   │
│  每个输出: {meta, signals[], details{}}                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼  统一 Schema v1.0
┌─────────────────────────────────────────────────────────────┐
│  signal_aggregator.py                                       │
│  消费逻辑: data.get("signals", [])                          │
│  去重 → 置信度提升 → 排序                                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  evidence_chain_builder.py                                  │
│  读取聚合信号 → 匹配链模板 → 生成叙事摘要                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  报告附录 (report_appendix)                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 六、向后兼容说明

- CLI 接口（argparse 参数）未做任何破坏性变更
- `details` 字段保留了所有原始详细数据，人工可直接查阅
- `signal_aggregator.py` 不再消费旧的 `alerts` / `anomalies` / `results` 顶层键
- 外部调用 `investigate.py` 的 deep_evidence 子命令行为不变

---

## 七、待办

- [ ] 为 12 个新脚本补充单元测试（当前测试覆盖率仅限已有模块）
- [ ] 编写 signal_aggregator + evidence_chain_builder 的集成测试
- [ ] 实际运行 end-to-end 测试验证信号从生产到消费的全链路
