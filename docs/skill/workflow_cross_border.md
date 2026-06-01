# 海归学者调查流程 (Cross-Border Track)

## 适用条件

当调查对象**同时满足**以下条件时，使用海归 track：
- 当前在国内机构任职（或曾任职）
- 具有海外学位（硕/博）或海外教职经历（访问学者、博后、tenure-track）

## 核心理念

海归 track 不是国内 track 和国际 track 的简单叠加，而是**以跨境一致性验证为核心**的融合流程。重点关注：
1. 国内外履历的时间线是否自洽
2. 海外学历/教职是否可验证
3. 国内外发表记录是否存在双语重复发表
4. 回国后的学术产出是否与海外积累匹配

## 调查流程

### Step 0: 案件初始化

```bash
python3 scripts/investigate.py init --type cross_border --config ./config.yaml
```

`config.yaml` 中需同时填写国内和国际信息源配置。

### Step 1: 双轨数据收集（并行）

同时启动国内和国际数据收集：

| 数据源 | 工具 | 输出 |
|--------|------|------|
| CNKI/万方/WoS（国内发表） | `domestic/data_importer.py` | 国内论文清单 JSON |
| OpenAlex/ORCID/S2/GS（海外发表） | `international/data_fetcher.py` | 海外论文清单 JSON |
| 小红书（学生评价） | `international/xiaohongshu_client.py` | 评价 JSON |
| 研学网（国内学生评价） | `domestic/review_matcher.py` | 结构化评价 |
| 微信公众号 | `domestic/wechat_search.py` | 补充线索 |

### Step 2: 数据合并

```bash
python3 scripts/cross_border/merger.py \
  --domestic ./data/domestic_scholar_data.json \
  --international ./data/international_scholar_data.json \
  --output ./data/merged_scholar_data.json
```

合并逻辑：
- 论文去重（基于 DOI/标题相似度）
- 时间线拼接（国内外履历合并为统一 timeline）
- 合作者网络合并

### Step 3: 跨境一致性验证

```bash
python3 scripts/cross_border/validator.py \
  --scholar-data ./data/merged_scholar_data.json \
  --output ./data/cross_border_validation.json
```

验证项：
- 时间线重叠检测（国内任职期与海外学位期是否冲突）
- 学历真伪核实（海外学位是否可在官方数据库查询）
- 双语发表检测（同一研究是否以中英文分别发表且未互相引用）

### Step 4: 海归特有检测项

| 检测项 | 工具 | 对应启发式签名 |
|--------|------|---------------|
| 海外学历真伪 | 人工核实 + `cross_border/validator.py` | heuristics S10 |
| 访问学者时长核实 | 人工核实（签证记录/接收函） | heuristics S10 |
| 双语发表检测 | `deep_evidence/publication_trace/bilingual_publication_detector.py` | — |
| 回国后产出断崖 | `analysis/common_heuristics.py` (C05 publication_burst) | — |
| 海外合作者网络真实性 | `international/data_fetcher.py` + `network/network_visualizer.py` | — |

### Step 5: 质量评估 + 异常检测

同时使用两套评估基准：
- **国内基准**：CSSCI/北大核心、国内同行对比（via `benchmark_engine.py`）
- **国际基准**：JCR quartile、tenure benchmark（via `international/evaluator.py`）
- **数据取证**：如有论文原始数据，运行 `data_integrity_checker.py`

### Step 6: 多源交叉验证

| 来源 | 适用场景 |
|------|----------|
| 研学网评价 | 国内学生对海归导师的评价 |
| 小红书评价 | 曾在海外读书的中国学生对该导师的评价 |
| RateMyProfessors | 海外学生的英文评价 |
| PubPeer | 论文质疑记录 |
| Retraction Watch | 撤稿记录 |

使用 `analysis/review_aggregator.py` 合并多源评价。

### Step 7: 报告生成

海归 track 报告综合两个模板的要素：
- 国内部分：按 `report/report_template.md` 格式
- 国际部分：按 `report/international_template.md` 格式
- 跨境特有章节：学历验证结论、时间线一致性分析、双语发表检测结果

## 与国内/国际 Track 的区别

| 维度 | 国内 Track | 国际 Track | 海归 Track |
|------|-----------|-----------|-----------|
| 数据源 | CNKI/万方/WoS | OpenAlex/ORCID/S2 | 两者并行 |
| 评价来源 | 研学网/微信 | 小红书/RMP | 全部 |
| 评估基准 | CSSCI/北大核心 | JCR/tenure clock | 双基准对比 |
| 特有检查 | 行政职务耦合 | predatory journal/citation cartel | 跨境一致性 + 学历真伪 |
| 合并步骤 | 无 | 无 | `cross_border/merger.py` |
| 验证步骤 | `domestic/data_validator.py` | `international/data_validator.py` | `cross_border/validator.py` |

## CLI 命令速查

```bash
# 初始化
python3 scripts/investigate.py init --type cross_border --config ./config.yaml

# 国内数据导入
python3 scripts/investigate.py import --config ./config.yaml --source cnki --file ./data/cnki_export.txt

# 国际数据抓取
python3 scripts/investigate.py international-fetch --config ./config.yaml

# 合并
python3 scripts/cross_border/merger.py --domestic ./data/domestic.json --international ./data/international.json --output ./data/merged.json

# 跨境验证
python3 scripts/cross_border/validator.py --scholar-data ./data/merged.json --output ./data/validation.json

# 双语发表检测
python3 scripts/deep_evidence/publication_trace/bilingual_publication_detector.py --input ./data/merged.json --output ./data/bilingual_check.json

# 报告生成
python3 scripts/investigate.py generate --config ./config.yaml --type cross_border
```
