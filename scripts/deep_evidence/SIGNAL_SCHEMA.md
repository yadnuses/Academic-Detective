# Deep Evidence Signal Schema v1.0

> 统一契约：所有 deep_evidence 子模块的输出必须包含此 Schema 中定义的 `signals` 数组，
> 以便 `evidence_compiler/signal_aggregator.py` 无歧义地消费。

---

## 顶层结构

```json
{
  "meta": {
    "script": "script_name",
    "version": "1.0",
    "timestamp": "2026-04-17T08:30:00",
    "input_file": "./data/papers.json"
  },
  "signals": [
    {
      "type": "signal_type_id",
      "description": "Human-readable description of the anomaly.",
      "confidence": 0.82,
      "paper_id": "10.1000/xyz",
      "source": "script_name",
      "evidence": {}
    }
  ],
  "details": {}
}
```

---

## 字段规范

### `meta` (Object, required)

| 字段 | 类型 | 必填 | 说明 |
|:---|:---|:---:|:---|
| `script` | string | ✅ | 脚本标识符，snake_case，如 `preprint_monitor` |
| `version` | string | ✅ | Schema 版本，当前为 `"1.0"` |
| `timestamp` | string | ✅ | ISO 8601 格式，生成时间 |
| `input_file` | string | | 输入文件路径（相对路径即可） |

### `signals` (Array, required)

每个元素为 Signal 对象。

| 字段 | 类型 | 必填 | 说明 |
|:---|:---|:---:|:---|
| `type` | string | ✅ | 信号类型标识符，snake_case，如 `duplicate_submission`、`fast_cycle` |
| `description` | string | ✅ | 人类可读描述，不超过200字 |
| `confidence` | float | ✅ | 置信度，范围 `[0.0, 1.0]`。禁止字符串（如 `"high"`） |
| `paper_id` | string | | 关联论文的 DOI、PMID 或标题。无明确关联时省略 |
| `source` | string | ✅ | 产生此信号的脚本名，与 `meta.script` 一致 |
| `evidence` | object | | 任意结构化证据，供人工复核和证据链构建 |

### `details` (Object, optional)

保留脚本的原始详细输出。此字段不参与信号聚合，仅供人工查阅和调试。

---

## 置信度分级参考

| 级别 | 数值范围 | 含义 |
|:---|:---:|:---|
| 极低 | 0.00–0.20 | 边缘信号，可能只是数据噪声 |
| 低 | 0.21–0.40 | 轻微异常，需更多上下文 |
| 中 | 0.41–0.60 | 值得关注，单一来源上限 |
| 高 | 0.61–0.80 | 较强信号，建议深入调查 |
| 极高 | 0.81–1.00 | 强信号，多源交叉验证或统计显著 |

---

## 信号类型命名规范

所有 `type` 值使用 `snake_case`，由 `<domain>_<specific>` 组成。

### 已注册的信号类型

| type | 来源脚本 | 含义 |
|:---|:---|:---|
| `duplicate_submission` | preprint_monitor | 预印本与期刊投稿日期重叠 |
| `content_reuse` | preprint_monitor | 预印本内容未经修改转投期刊 |
| `suspicious_gap` | preprint_monitor | 期刊发表早于预印本 |
| `fast_cycle` | review_cycle_analyzer | 审稿周期异常短 |
| `batch_acceptance` | review_cycle_analyzer | 批量录用模式 |
| `high_velocity` | review_cycle_analyzer | 同一期刊短期内大量发文 |
| `impossible_sd` | stats_reverse_engineer | 报告的标准差不合理 |
| `inconsistent_p_value` | stats_reverse_engineer | p值与检验统计量矛盾 |
| `integer_discrepancy` | stats_reverse_engineer | 整数计数数据不一致 |
| `test_statistic_mismatch` | stats_reverse_engineer | 检验统计量无法从原始数据导出 |
| `duplicate_image_across_papers` | image_metadata_extractor | 同一图片出现在不同论文 |
| `suspicious_resolution` | image_metadata_extractor | 图片分辨率异常 |
| `mismatched_software` | image_metadata_extractor | 图片编辑软件痕迹可疑 |
| `missing_ethics_number` | ethics_statement_parser | 提及伦理但未提供批准号 |
| `generic_ethics_statement` | ethics_statement_parser | 使用模板化伦理声明 |
| `ethics_contradiction` | ethics_statement_parser | 涉及人体/动物研究但无伦理声明 |
| `unregistered_trial` | clinical_trial_registry_checker | 临床试验未注册 |
| `late_registration` | clinical_trial_registry_checker | 试验注册晚于首例入组 |
| `undisclosed_dual_publication` | conference_paper_mapper | 会议论文与期刊论文未互相引用 |
| `salami_slicing` | conference_paper_mapper | 会议到期刊新增内容<30% |
| `bilingual_pair` | bilingual_publication_detector | 中英文双语发表配对 |
| `undisclosed_bilingual` | bilingual_publication_detector | 双语发表未互相引用 |
| `salami_bilingual` | bilingual_publication_detector | 双语版本内容高度雷同 |
| `suspicious_attention_spike` | crossref_event_tracker | 注意力在7天内集中爆发 |
| `zero_citations_high_mentions` | crossref_event_tracker | 高社媒提及但零学术引用 |
| `policy_citation_anomaly` | crossref_event_tracker | 发表后30天内被政策文件引用 |
| `high_self_journal_rate` | editorial_self_publishing_detector | 编辑在自管期刊发文占比过高 |
| `editorial_bypass_suspected` | editorial_self_publishing_detector | 自投论文审稿周期异常短 |
| `guest_editor_special_issue_selfpub` | editorial_self_publishing_detector | 客座编辑专题自投 |
| `direct_coauthor_conflict` | recommended_reviewer_network | 推荐审稿人与作者有直接合著 |
| `same_institution_conflict` | recommended_reviewer_network | 推荐审稿人与作者同机构 |
| `repeated_reviewer` | recommended_reviewer_network | 同一审稿人被反复推荐 |
| `citation_loop_conflict` | recommended_reviewer_network | 推荐审稿人与作者存在引用循环 |
| `high_retraction_journal` | journal_retraction_history | 期刊撤稿率显著高于基准 |
| `author_paper_retracted` | journal_retraction_history | 作者本人有论文被撤稿 |

---

## 向后兼容

- `signal_aggregator.py` 自 v3.0.1 起只消费 `signals` 数组。
- 旧的 `alerts` / `anomalies` / `results` 顶层键不再被聚合器识别，
  但可保留在 `details` 中供人工查阅。
