# 案件调查检查清单

> 案件：`{{CASE_NAME}}`
> 创建日期：`{{DATE}}`
> 调查类型：`domestic / international / cross_border`
> 调查深度：`quick / standard / exhaustive`

---

## Step 0: 案件初始化

- [ ] 运行 `investigate.py init` 创建标准目录结构
- [ ] 编辑 `config.yaml`，填写学者基本信息和待验证声明
- [ ] 确认案件ID格式：`AD-YYYY-MM-DD-NNN`
- [ ] 确认 `.case/STATE.md` 已生成，当前阶段为 `initialized`

---

## Step 1: 基本信息建立

- [ ] 机构官网快照已保存到 `data/`
- [ ] 教育背景（学位、毕业年份、导师）已核实
- [ ] 职业时间线（入职、晋升、职务变动）已记录
- [ ] 海外经历（如有）已核实
- [ ] 基本信息交叉验证：至少2个独立来源

---

## Step 2: 数据采集与导入

### 数据库搜索（人工操作）
- [ ] CNKI 导出已放入 `data/`
- [ ] 万方导出已放入 `data/`（如适用）
- [ ] WoS 导出已放入 `data/`（如适用）

### 脚本导入
- [ ] 运行 `archive/flat_export_redundant_20260501/domestic_data_importer.py` 生成 `data/unified_papers.json`
- [ ] 检查去重结果和导入日志
- [ ] 确认数据库 `case.db` 已记录导入信息

### 补充来源
- [ ] 微信公众号文章搜索（`archive/flat_export_redundant_20260501/domestic_wechat_search.py`）
- [ ] 小红书评价抓取（`archive/flat_export_redundant_20260501/international_xiaohongshu_client.py`，国际轨道适用）
- [ ] 导师评价网数据匹配

---

## Step 3: 质量评估（核心：必须使用六维评分系统）

### ⚠️ 强制检查项

> **重要**：`scripts/` 根目录的同名文件均为 shim（<500字节）。**必须使用 `archive/flat_export_redundant_20260501/` 目录中的真实实现。**
> 参考 `scripts/TOOLS_INDEX.md` 获取正确路径。

#### 单篇论文评分（PDF 数量 ≤ 10 时适用）

对每篇 PDF 依次执行：

```bash
# 1. 文本画像
python archive/flat_export_redundant_20260501/analysis_text_profiler.py --input ./pdfs/论文.pdf --output ./data/论文_profile.json

# 2. 人工编码 observations（基于阅读）
# 创建 ./data/论文_obs.json，包含 originality_score / conclusion_robustness / has_fatal_flaw 等

# 3. 六维评分
python archive/flat_export_redundant_20260501/analysis_paper_quality_rubric.py \
  --profile ./data/论文_profile.json \
  --observations ./data/论文_obs.json \
  --output ./data/论文_quality.json
```

- [ ] 每篇 PDF 已生成 `*_profile.json`
- [ ] 每篇 PDF 已生成 `*_observations.json`（人工编码）
- [ ] 每篇 PDF 已生成 `*_quality.json`（六维评分）
- [ ] 所有评分已汇总到 `data/six_dim_summary.json`

#### 批量评分（PDF 数量 > 10 时适用）

```bash
# Stage 1: 脚本自动提取
python archive/flat_export_redundant_20260501/analysis_hybrid_scorer.py prepare -i ./pdfs -o ./data/hybrid_scores

# Stage 2: LLM 审阅 llm_review_request.md，输出 llm_observations_batch.json

# Stage 3: 应用评分
python archive/flat_export_redundant_20260501/analysis_hybrid_scorer.py apply -i ./pdfs -o ./data/hybrid_scores
```

- [ ] `prepare` 阶段完成
- [ ] LLM observations 已生成
- [ ] `apply` 阶段完成
- [ ] `_final_ranked_report.json` 已生成

#### 引用与风格分析
- [ ] 运行 `analysis/citation_profiler.py`（如有引用数据）
- [ ] 运行 `analysis/stylometry_profiler.py`（如有多篇可比文本）

#### 质量评估总结
- [ ] 六维评分平均分已计算
- [ ] 评分分布模式已分析（对照 evaluation_baselines.md 7.3 节）
- [ ] 红旗信号已审查
- [ ] 低分论文（< 65 分）已标注原因

---

## Step 4: 关系网络

- [ ] 导师信息已记录
- [ ] 主要合作者已识别
- [ ] 期刊编委/审稿关联已记录（如有）
- [ ] 机构依赖关系已记录
- [ ] 运行 `archive/flat_export_redundant_20260501/network_network_visualizer.py` 生成关系图谱（如数据充足）

---

## Step 5: 异常检测

- [ ] 运行 `archive/flat_export_redundant_20260501/domestic_data_validator.py` / `archive/flat_export_redundant_20260501/international_data_validator.py`
- [ ] 检查 anomalies 列表是否为空
- [ ] 运行 `archive/flat_export_redundant_20260501/benchmark_engine.py`（如已有基准数据）
- [ ] 运行 `archive/flat_export_redundant_20260501/scholar_profile_matcher_v2.py`（如已有46例数据库）
- [ ] 检查 claims_vs_reality 差异是否 > 20%

---

## Step 6: 深度证据（如启用）

根据 `config.yaml` 中的 `deep_evidence` 配置逐项检查：

- [ ] `data_forensics.stats_reverse_engineer` 已运行（如启用）
- [ ] `data_forensics.image_metadata_extraction` 已运行（如启用）
- [ ] `publication_trace.preprint_sources` 已监控（如启用）
- [ ] `publication_trace.check_bilingual` 已运行（如启用）
- [ ] `ethics_audit.registry_sources` 已核对（如启用）
- [ ] `peer_review_intel.check_editorial_self_publishing` 已运行（如启用）

---

## Step 7: 报告生成

- [ ] `scholar_data.json` 已通过 `data_validator.py` 验证
- [ ] `archive/flat_export_redundant_20260501/report_report_prompt_optimizer.py` 已生成 `report_prompt.md`
- [ ] 报告已由 LLM 生成并通过人工审阅
- [ ] 两面性分析已平衡
- [ ] 证据链完整
- [ ] 免责声明已包含
- [ ] `archive/flat_export_redundant_20260501/core_watermark.py` 已嵌入水印
- [ ] 最终报告已保存到 `reports/`

---

## 交付前最终检查

- [ ] 所有脚本输出文件已归档到 `data/`
- [ ] 所有 PDF 证据已保存到 `pdfs/`
- [ ] 所有截图已保存到 `screenshots/`
- [ ] `scholar_data.json` 包含完整证据链
- [ ] 报告无个人信息泄露风险
- [ ] `.case/STATE.md` 已更新为 `archived`

---

## 常见错误预防

| 错误 | 正确做法 |
|:---|:---|
| 使用 `scripts/text_profiler.py` | 使用 `archive/flat_export_redundant_20260501/analysis_text_profiler.py` |
| 使用 `scripts/paper_quality_rubric.py` | 使用 `archive/flat_export_redundant_20260501/analysis_paper_quality_rubric.py` |
| 跳过六维评分直接写质量评估 | 每篇论文必须经过 `text_profiler` → `paper_quality_rubric` 完整流程 |
| 忽略 observations.json | 六维评分必须包含人工/LLM 编码的 observations |
| 忘记设置 PYTHONPATH | 运行脚本前执行 `export PYTHONPATH="/path/to/scripts:$PYTHONPATH"` |

---

*本清单基于 academic-investigation skill v3.2*
*参考文件：`scripts/TOOLS_INDEX.md`、`scripts/evaluation_baselines.md`*
