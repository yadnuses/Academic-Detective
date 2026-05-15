# 学科基准线数据库 — 万能服务器任务清单 v2.0

## 一、版本说明

**基于 v1.0 成果验收后发现的五大问题，制定本修正清单。**

v1.0 成果：
- 4个学科基线已建立（医学85000样本、新闻传播12000、化学65000、计算机35000）
- 46条学者档案已回填部分字段
- 10条异常规则已激活
- 批量计算完成，6个确认不端案例被正确识别（CASE_xxx57.27、CASE_yyy12.95、CASE_zzz7.28、CASE_www5.67等）

v1.0 暴露问题：
- 19个确认不端案例异常指数为0（数据回填缺失）
- A005权重过高导致分数压缩（单个规则产生428分）
- 顶尖学者CASE_019（院士，h_index=104）被误标为medium风险
- 审稿周期、合作者集中度等字段完全缺失
- 0与NULL未分离，引擎无法识别数据缺失

---

## 二、任务总览

| 优先级 | 任务 | 预期效果 | 验收标准 |
|:---:|:---|:---|:---|
| P0 | 回填19个0分不端案例的 h_index + total_citations + num_papers_verified | 让CASE_002、CASE_024等进入检测范围 | 19个案例异常指数>0 |
| P1 | 降低A005权重 + 引入分数标准化 | 分数分布均衡，区分度提升 | 最高分<20，最低分>0的不端案例>15个 |
| P2 | 顶尖学者分层基线 | 消除CASE_019等院士的误报 | CASE_019异常指数<1.0 |
| P3 | 回填 coauthor_concentration + median_review_days | 激活A003、A004规则 | A003触发>5次，A004触发>3次 |
| P4 | 0/NULL分离 + 数据质量标记 | 引擎准确识别缺失字段 | 新增 `data_quality_mask` 列 |

---

## 三、P0：回填19个0分不端案例的核心字段

### 3.1 目标案例清单

以下19个确认不端案例当前异常指数为0，需要回填 `h_index`、`total_citations`、`num_papers_verified`：

```
CASE_002  CASE_002        CASE_024  CASE_024        CASE_029  某机构匿名案例
CASE_030  对外经贸李某某  CASE_031  天津大学/厦大雷同 CASE_032  唐博/王立明
CASE_033  陈磊/陈可斌    CASE_034  周建          CASE_035  杨耀/王进进/李文彦
CASE_036  CASE_036        CASE_037  CASE_037    CASE_038  CASE_038
CASE_039  周伟/刘涛/李永峰 CASE_040 林兴/韦锦斌等   CASE_041  燕东亮
CASE_042  甘莉          CASE_043  贺聚良        CASE_044  陈岩
```

### 3.2 回填策略（按案例类型）

**类型A：有公开学术档案的案例（8个）**

| 案例 | 姓名 | 建议数据源 | 备注 |
|:---|:---|:---|:---|
| CASE_002 | CASE_002 | 知网、PubMed、湘雅二医院官网历史快照 | 临床医生，学术产出有限，h_index可能<10 |
| CASE_024 | CASE_024 | 知网、Google Scholar | 戏剧影视学，知网可查其博士论文和发表论文 |
| CASE_029 | 某机构匿名案例 | 知网、WOS | 匿名案例，可用机构+领域+时间范围检索 |
| CASE_030 | 对外经贸李某某 | 知网、WOS | 匿名案例，同上 |
| CASE_037 | CASE_037 | 知网、WOS | 化学领域，可用姓名+机构检索 |
| CASE_038 | CASE_038 | 知网、WOS | 化学领域 |
| CASE_039 | 周伟/刘涛/李永峰 | 知网、WOS | 化学领域 |
| CASE_040 | 林兴/韦锦斌等 | 知网、WOS | 化学领域 |

**类型B：NSFC通报匿名案例（7个）**

| 案例 | 说明 | 回填策略 |
|:---|:---|:---|
| CASE_032 | 唐博/王立明，1篇涉事论文 | h_index=0, total_citations=0（已撤稿），num_papers_verified=1 |
| CASE_033 | 陈磊/陈可斌，1篇涉事论文 | 同上 |
| CASE_034 | 周建，1篇涉事论文 | 同上 |
| CASE_035 | 杨耀等，批量造假 | 如无法获取，h_index=NULL，num_papers_verified=已知涉事论文数 |
| CASE_041 | 燕东亮 | 同上 |
| CASE_042 | 甘莉 | 同上 |
| CASE_043 | 贺聚良 | 同上 |

**类型C：已撤稿且无公开档案的案例（4个）**

| 案例 | 说明 | 回填策略 |
|:---|:---|:---|
| CASE_031 | 天津大学/厦大硕士论文雷同 | 学位论文无h_index，num_papers_verified=2（两篇雷同论文） |
| CASE_036 | CASE_036 | 如无法获取，h_index=NULL |
| CASE_044 | 陈岩 | 同上 |
| CASE_045/046 | Tumor Biology模式原型 | 已触发A005，无需额外回填 |

### 3.3 回填格式

在 `scholar_profile_database_complete.csv` 中更新对应行的以下字段：

```csv
profile_id,h_index,total_citations,num_papers_verified,...
CASE_002,5,120,15,...
CASE_024,3,45,8,...
```

**关键要求**：
- 确实无法获取的数据，留空（不要填0）
- 已撤稿且无历史记录的案例，h_index和total_citations留空
- num_papers_verified至少回填已知涉事论文数

---

## 四、P1：权重修正 + 分数标准化

### 4.1 当前问题

A005（撤稿历史）权重过高：
- weight=2.0, severity=3
- CASE_045有107次撤稿，z=71.5σ
- raw_score = 71.5 × 3 = 214.5
- weighted_score = 214.5 × 2.0 = 429.0
- 导致 composite_score=85.80，其他案例被压缩到0-10区间

### 4.2 修正方案

**方案A：降低权重（推荐，改动最小）**

| 规则 | 当前weight | 当前severity | 建议weight | 建议severity |
|:---|:---:|:---:|:---:|:---:|
| A001 超高产 | 1.0 | 2 | 1.0 | 2 |
| A002 引用异常 | 1.0 | 2 | 1.0 | 2 |
| A003 合作者集中 | 1.2 | 3 | 1.0 | 2 |
| A004 快速发表 | 1.5 | 3 | 1.0 | 2 |
| A005 撤稿历史 | 2.0 | 3 | 1.0 | 2 |
| A006 跨领域延伸 | 0.8 | 2 | 0.8 | 2 |
| A007 一作比例 | 0.8 | 1 | 0.8 | 1 |
| A008 基金异常 | 0.8 | 2 | 0.8 | 2 |
| A009 自引率 | 0.8 | 2 | 0.8 | 2 |
| A010 期刊层级 | 0.6 | 1 | 0.6 | 1 |

**方案B：引入分数标准化（更稳健）**

在 `composite_scores` 计算中，增加 `min-max标准化` 或 `sigmoid压缩`：

```python
# 原始composite_score可能从0到400+
# 标准化到0-100区间
normalized_score = 100 * (1 - math.exp(-composite_score / 10))
```

或者按百分位排名：

```python
percentile_score = 100 * (1 - percentile_in_discipline)
```

**建议**：同时实施方案A（降权重）和方案B（sigmoid标准化）。

### 4.3 修正后的预期分数分布

| 案例 | 当前score | 修正后预期score | 风险等级 |
|:---|:---:|:---:|:---:|
| CASE_045/046 | 85.80 | ~15 | high |
| CASE_028 | 57.27 | ~12 | high |
| CASE_025 | 12.95 | ~8 | high |
| CASE_026 | 7.28 | ~6 | medium |
| CASE_027 | 5.67 | ~5 | medium |
| CASE_019 CASE_019 | 2.20 | ~2 | low |
| 正常学者均值 | <1.0 | <1.0 | low |

---

## 五、P2：顶尖学者分层基线

### 5.1 当前问题

CASE_019（CASE_019）：中科院院士，h_index=104，年均发文66篇。
- 与普通副教授基线比较，触发A001（超高产）
- 异常指数2.20，风险等级medium

### 5.2 根因分析

基线样本中缺乏足够多的顶尖学者（院士/长江/杰青），导致顶尖产出被误判为异常。

### 5.3 修正方案

**方案A：增加 `career_tier` 字段到 researcher_baseline（推荐）**

在 `researcher_baseline` 表中新增字段 `career_tier`：

```sql
ALTER TABLE researcher_baseline ADD COLUMN career_tier TEXT;
-- 取值: normal / leading / top
-- normal: 普通学者（讲师、副教授、普通教授）
-- leading: 领军学者（杰青、长江、万人计划）
-- top: 顶尖学者（院士、国际奖项获得者）
```

CASE_019标记为 `top`，CASE_002标记为 `normal`。

**方案B：修改A001规则的检测逻辑**

增加 `career_tier` 过滤条件：

```python
detection_logic = "avg_papers_per_year > benchmark_median + z_threshold * benchmark_mad AND career_tier != 'top'"
```

或者为每个 `career_tier` 建立独立的学科基线：

```sql
-- 医学_top基线
INSERT INTO discipline_benchmarks (discipline_id, ...) VALUES ('MED_TOP_CN_2020_2024', ...)
-- 医学_normal基线
INSERT INTO discipline_benchmarks (discipline_id, ...) VALUES ('MED_NORMAL_CN_2020_2024', ...)
```

**方案C：增加分位数统计到学科基线**

在 `discipline_benchmarks` 中增加 P90、P95、P99 字段：

```sql
ALTER TABLE discipline_benchmarks ADD COLUMN p95_papers_per_year REAL;
ALTER TABLE discipline_benchmarks ADD COLUMN p99_papers_per_year REAL;
ALTER TABLE discipline_benchmarks ADD COLUMN p95_h_index REAL;
ALTER TABLE discipline_benchmarks ADD COLUMN p99_h_index REAL;
```

A001规则修改为：只有当观测值 > P99 时才触发（即真正的极端异常）。

**建议**：同时实施方案A（career_tier标记）和方案C（P99分位数）。

---

## 六、P3：回填合作者集中度 + 审稿周期

### 6.1 当前问题

| 字段 | 有值比例 | 影响 |
|:---|:---:|:---|
| coauthor_concentration | 0/46 | A003完全无法触发 |
| median_review_days | 0/46 | A004完全无法触发 |
| cross_discipline_count | 0/46 | A006完全无法触发 |
| funding_hit_rate | 0/46 | A008完全无法触发 |
| self_citation_rate | 0/46 | A009完全无法触发 |

### 6.2 回填策略

**coauthor_concentration（top3合作者发文占比）**

数据来源：
- 从WOS/Scopus/知网的合作者网络数据中提取
- 计算每位学者的top3合作者发文数 / 总发文数

简化策略（如无法获取完整合作者网络）：
- 对于已知不端案例（如导师霸凌型），手动标记为0.85-0.95
- 对于正常学者，估计为0.30-0.50
- 无法判断的，留空

**median_review_days（投稿到发表中位数天数）**

数据来源：
- 从期刊官网的审稿周期统计中获取
- 或者从学者个人投稿记录中计算

简化策略：
- 按学科估计中位数：医学120天、化学90天、新闻传播180天、计算机90天
- 对于已知异常快速发表的案例（如30天内发表），手动标记为15-20天
- 正常学者使用学科中位数

**cross_discipline_count（跨学科数量）**

数据来源：
- 从论文的学科分类码中提取
- 或者从学者发表期刊的学科分布推断

简化策略：
- 正常学者：1-2个学科
- 跨学科活跃学者：3-4个
- 论文工厂型（如Tumor Biology模式）：5+，手动标记

### 6.3 回填格式

在 `scholar_profile_database_complete.csv` 中新增列：

```csv
profile_id,coauthor_concentration,median_review_days,cross_discipline_count,funding_hit_rate,self_citation_rate
CASE_001,0.35,120,2,0.25,0.08
CASE_002,0.90,30,1,0.10,0.05
```

---

## 七、P4：0/NULL分离 + 数据质量标记

### 7.1 当前问题

CSV中缺失字段被填为0，引擎无法区分"未知"和"零值"。

例如：
- CASE_002的h_index=0：可能是真的h_index=0（无学术影响力），也可能是数据缺失
- 这导致引擎对缺失数据的案例完全不计算，而不是标记为"数据不足"

### 7.2 修正方案

**方案A：缺失字段留空（最简单）**

CSV中确实无法获取的数据，保持为空字符串，不要填0。

引擎导入逻辑已支持NULL检测：

```python
def _float(val):
    try:
        return float(val) if val and val.strip() else None
    except ValueError:
        return None
```

**方案B：新增 `data_quality_mask` 字段（推荐，更完整）**

在 `scholar_profile_database_complete.csv` 末尾新增一列 `data_quality_mask`，用JSON记录每个字段的质量：

```csv
profile_id,...,data_quality_mask
CASE_001,"{\"h_index\":\"measured\",\"total_citations\":\"measured\",\"coauthor_concentration\":\"estimated\"}"
CASE_002,"{\"h_index\":\"missing\",\"total_citations\":\"missing\",\"coauthor_concentration\":\"estimated\"}"
```

质量标记取值：
- `measured`：从数据库实测
- `estimated`：基于有限信息估计
- `missing`：完全无法获取
- `inferred`：从其他字段推断

引擎读取时，对 `missing` 字段跳过计算，对 `estimated` 字段降低权重。

### 7.3 引擎适配

修改 `benchmark_engine.py` 的 `calculate_deviation` 方法：

```python
# 如果数据质量为missing，返回特殊标记
data_quality = get_data_quality(researcher_id, metric)
if data_quality == "missing":
    return DeviationResult(
        metric=metric,
        observed_value=None,
        benchmark_value=benchmark_median,
        deviation_score=0.0,
        anomaly_probability=0.0,
        ...
    )
```

---

## 八、回传文件清单

完成上述任务后，请回传以下文件：

| 文件名 | 说明 | 变更内容 |
|:---|:---|:---|
| `scholar_profile_database_complete.csv` | 完整学者档案 | 新增/修正19个案例的h_index、citations；新增coauthor_concentration等字段；新增data_quality_mask列 |
| `discipline_benchmarks.csv` | 学科基线 | 新增P95/P99分位数字段；新增career_tier分层基线 |
| `anomaly_rules.csv` | 异常规则 | 更新A003-A005的weight和severity |
| `peer_groups.csv` | 同群定义 | 更新career_tier分组 |

或者直接回传完整的 `benchmark.db` SQLite文件（包含所有更新）。

---

## 九、验收测试方法

本地运行以下命令验证：

```bash
# 重新初始化并计算
python scripts/benchmark_demo.py

# 验收标准
# 1. P0: 确认不端案例中异常指数=0的比例 < 20%（当前39%）
# 2. P1: 最高分 < 20，区分度（max-min）> 5
# 3. P2: CASE_019(CASE_019)异常指数 < 1.0
# 4. P3: A003触发>5次，A004触发>3次
# 5. P4: 所有"未找到"的字段在CSV中显示为空，不是0
```

---

如有疑问，请联系本地负责人核对字段含义或案例细节。
