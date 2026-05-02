-- ============================================================
-- 学科基准线数据库 Schema v1.0
-- 五层架构：学科维度 / 期刊维度 / 个体基线 / 异常规则 / 案例关联
-- ============================================================
-- 设计原则：
--   1. 所有数值字段使用 REAL（IEEE 754 双精度浮点）
--   2. 基线统计量使用稳健统计量（中位数 + IQR + MAD）
--   3. 时间戳统一使用 ISO-8601 TEXT 格式
--   4. 兼容 SQLite，扩展注释标注 PostgreSQL 适配点
-- ============================================================

-- ------------------------------------------------------------
-- Layer 1: 学科维度基线 (Discipline Benchmarks)
-- 描述：某个学科在特定区域、特定时间段内的"正常"统计分布
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS discipline_benchmarks (
    discipline_id   TEXT PRIMARY KEY,       -- 如 "MED_CN_2020_2024"
    discipline_name TEXT NOT NULL,          -- 如 "医学"
    discipline_code TEXT,                   -- 如 "MED"
    region          TEXT NOT NULL,          -- 如 "CN", "US", "GLOBAL"
    period_start    TEXT,                   -- ISO-8601, 如 "2020-01-01"
    period_end      TEXT,                   -- ISO-8601, 如 "2024-12-31"

    -- 发文行为基线
    avg_papers_per_year     REAL,           -- 年均发文量
    median_papers_per_year  REAL,           -- 中位数（稳健）
    std_papers_per_year     REAL,           -- 标准差
    iqr_papers_per_year     REAL,           -- IQR（四分位距）
    mad_papers_per_year     REAL,           -- MAD（中位数绝对偏差）

    -- 引用影响力基线
    median_h_index          REAL,
    mean_h_index            REAL,
    std_h_index             REAL,
    median_citations_per_paper REAL,
    mean_citations_per_paper    REAL,

    -- 合作网络基线
    median_coauthor_count   REAL,           -- 中位数合作者数量
    avg_coauthor_count      REAL,
    coauthor_concentration_threshold REAL,  -- 合作集中度警戒线（如 top3 占比 > 80%）

    -- 跨学科行为基线
    median_cross_discipline_count REAL,     -- 中位数跨领域数
    cross_discipline_rate       REAL,       -- 跨学科研究者占比

    -- 基金资助基线
    avg_funding_rate        REAL,           -- 基金命中率均值
    median_funding_rate     REAL,

    -- 审稿周期基线
    median_review_days      REAL,           -- 中位数审稿天数
    mean_review_days        REAL,
    std_review_days         REAL,

    -- 撤稿率基线
    retraction_rate         REAL,           -- 撤稿率（每万篇）

    -- 分位数统计（用于顶尖学者分层基线）
    p95_papers_per_year     REAL,           -- 年均发文P95分位数
    p99_papers_per_year     REAL,           -- 年均发文P99分位数
    p95_h_index             REAL,           -- h-index P95分位数
    p99_h_index             REAL,           -- h-index P99分位数

    -- 元数据
    sample_size             INTEGER NOT NULL DEFAULT 0,
    data_source             TEXT,           -- 数据来源，如 "WOS", "CNKI", "Scopus"
    update_date             TEXT,           -- ISO-8601
    notes                   TEXT            -- 备注
);

-- 学科名称索引（加速模糊匹配）
CREATE INDEX IF NOT EXISTS idx_discipline_name ON discipline_benchmarks(discipline_name);
CREATE INDEX IF NOT EXISTS idx_discipline_region ON discipline_benchmarks(region);

-- ------------------------------------------------------------
-- Layer 2: 期刊维度基线 (Journal Benchmarks)
-- 描述：某本期刊在特定时间段的"正常"统计分布
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS journal_benchmarks (
    journal_id      TEXT PRIMARY KEY,       -- 如 "NATURE_2024"
    journal_name    TEXT NOT NULL,          -- 期刊全称
    journal_issn    TEXT,                   -- ISSN
    discipline_id   TEXT,                   -- FK -> discipline_benchmarks.discipline_id

    -- 期刊基本属性
    impact_factor   REAL,
    jcr_quartile    TEXT,                   -- Q1/Q2/Q3/Q4
    tier            INTEGER,                -- 自定义层级：1=顶刊, 2=权威, 3=核心, 4=普通

    -- 审稿周期基线
    median_review_days  REAL,
    mean_review_days    REAL,
    std_review_days     REAL,
    min_review_days     INTEGER,
    max_review_days     INTEGER,

    -- 接受率基线
    acceptance_rate     REAL,               -- 0.0 ~ 1.0

    -- 撤稿率基线
    retraction_rate     REAL,               -- 撤稿率（每万篇）
    total_retractions   INTEGER,

    -- 发文量基线
    annual_publication_count    INTEGER,    -- 年发文量
    publication_growth_rate     REAL,       -- 发文量年增长率

    -- 国别分布（JSON 存储）
    country_distribution    TEXT,           -- JSON: {"CN": 0.35, "US": 0.25, ...}

    -- 元数据
    period_start    TEXT,
    period_end      TEXT,
    data_source     TEXT,
    update_date     TEXT,
    notes           TEXT,

    FOREIGN KEY (discipline_id) REFERENCES discipline_benchmarks(discipline_id)
);

CREATE INDEX IF NOT EXISTS idx_journal_name ON journal_benchmarks(journal_name);
CREATE INDEX IF NOT EXISTS idx_journal_discipline ON journal_benchmarks(discipline_id);

-- ------------------------------------------------------------
-- Layer 3: 个体研究者基线 (Researcher Baseline)
-- 描述：某个研究者的个体统计画像，用于与同群/学科基线比较
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS researcher_baseline (
    researcher_id       TEXT PRIMARY KEY,
    profile_id          TEXT,               -- FK -> scholar_profile_database.profile_id
    name                TEXT NOT NULL,
    institution         TEXT,
    department          TEXT,
    current_title       TEXT,
    career_stage        TEXT,               -- early / mid / senior / emeritus
    discipline_id       TEXT,               -- FK -> discipline_benchmarks.discipline_id

    -- 学术产出画像
    h_index                 REAL,
    total_citations         INTEGER,
    avg_papers_per_year     REAL,           -- 年均发文
    median_papers_per_year  REAL,
    first_author_ratio      REAL,           -- 一作比例 0.0~1.0
    corresponding_author_ratio REAL,        -- 通讯比例

    -- 合作网络画像
    coauthor_count          INTEGER,        -- 总合作者数
    coauthor_concentration  REAL,           -- top3 合作者发文占比
    median_coauthor_per_paper REAL,         -- 每篇论文中位数合作者数
    solo_author_ratio       REAL,           -- 独作比例

    -- 跨学科画像
    cross_discipline_count  INTEGER,        -- 涉及领域数
    primary_discipline      TEXT,           -- 主领域
    secondary_disciplines   TEXT,           -- JSON 数组

    -- 基金资助画像
    funding_hit_rate        REAL,           -- 申请命中率
    total_grants            INTEGER,
    total_grant_amount      REAL,           -- 总金额（万元）

    -- 审稿周期画像
    median_review_days      REAL,           -- 个人投稿的中位数审稿天数
    min_review_days         INTEGER,
    max_review_days         INTEGER,
    suspicious_fast_track_count INTEGER,    -- 异常快速发表次数（<30天）

    -- 撤稿画像
    retraction_count        INTEGER DEFAULT 0,
    expression_of_concern_count INTEGER DEFAULT 0,

    -- 被引画像
    median_citations_per_paper  REAL,
    highly_cited_paper_count    INTEGER,    -- 被引前10%论文数
    self_citation_rate          REAL,       -- 自引率

    -- 标记
    is_confirmed_misconduct   INTEGER DEFAULT 0,  -- 0=正常, 1=确认不端
    investigation_status      TEXT,               -- normal / suspicious / confirmed_misconduct

    -- 分层标记
    career_tier             TEXT DEFAULT 'normal', -- normal / leading / top

    -- 元数据
    data_path               TEXT,
    update_date             TEXT,
    notes                   TEXT,

    FOREIGN KEY (discipline_id) REFERENCES discipline_benchmarks(discipline_id)
);

CREATE INDEX IF NOT EXISTS idx_researcher_name ON researcher_baseline(name);
CREATE INDEX IF NOT EXISTS idx_researcher_discipline ON researcher_baseline(discipline_id);
CREATE INDEX IF NOT EXISTS idx_researcher_status ON researcher_baseline(investigation_status);

-- ------------------------------------------------------------
-- Layer 4: 异常模式规则 (Anomaly Rules)
-- 描述：可运行的异常检测规则，每条规则对应一种学术不端模式
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS anomaly_rules (
    rule_id             TEXT PRIMARY KEY,
    rule_name           TEXT NOT NULL,      -- 如 "A001_超高产"
    rule_name_zh        TEXT,               -- 中文名称
    rule_description    TEXT NOT NULL,      -- 规则描述
    detection_logic     TEXT NOT NULL,      -- 检测逻辑（Python 表达式模板）
    comparison_mode     TEXT NOT NULL,      -- individual / peer_group / global

    -- 阈值参数（JSON 存储）
    threshold_params    TEXT,               -- JSON: {"z_threshold": 2.5, "direction": "high"}

    -- 统计分布假设
    distribution_assumption TEXT,           -- normal / lognormal / t
    confidence_level    REAL DEFAULT 0.95,  -- 置信水平

    -- 权重与评分
    weight              REAL DEFAULT 1.0,   -- 规则权重（用于综合异常指数）
    severity_level      INTEGER,            -- 1=提示, 2=警告, 3=严重

    -- 学科适用性
    applicable_disciplines  TEXT,           -- JSON 数组或 "ALL"
    excluded_disciplines    TEXT,           -- JSON 数组

    -- 参考案例
    reference_cases     TEXT,               -- JSON 数组: ["CASE_001", "CASE_002"]
    false_positive_rate REAL,               -- 已知误报率

    -- 元数据
    created_date        TEXT,
    updated_date        TEXT,
    version             TEXT,
    is_active           INTEGER DEFAULT 1,  -- 0=停用, 1=启用
    notes               TEXT
);

CREATE INDEX IF NOT EXISTS idx_anomaly_rule_active ON anomaly_rules(is_active);

-- ------------------------------------------------------------
-- Layer 5: 案例-异常关联 (Case Anomaly Links)
-- 描述：每个案例触发了哪些异常规则，偏离程度如何
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS case_anomaly_links (
    link_id                 TEXT PRIMARY KEY,
    case_id                 TEXT NOT NULL,  -- 对应 researcher_baseline.researcher_id
    rule_id                 TEXT NOT NULL,  -- FK -> anomaly_rules.rule_id

    -- 原始观测值
    observed_value          REAL,
    benchmark_value         REAL,           -- 基线中位数/均值

    -- 偏离度
    deviation_score         REAL,           -- Z-score 或标准化偏离度
    deviation_direction     TEXT,           -- high / low
    deviation_magnitude     REAL,           -- 绝对偏离值 |observed - benchmark|

    -- 异常概率
    anomaly_probability     REAL,           -- P(anomaly | observed_value), 0.0~1.0

    -- 置信区间
    confidence_interval_lower   REAL,
    confidence_interval_upper   REAL,
    confidence_level            REAL DEFAULT 0.95,

    -- 比较基线
    comparison_baseline_id  TEXT,           -- 使用的学科/期刊/同群基线ID
    comparison_mode         TEXT,           -- individual / peer_group / global
    peer_group_size         INTEGER,        -- 同群样本量

    -- 元数据
    calculation_date        TEXT,
    algorithm_version       TEXT,
    notes                   TEXT,

    FOREIGN KEY (case_id) REFERENCES researcher_baseline(researcher_id),
    FOREIGN KEY (rule_id) REFERENCES anomaly_rules(rule_id)
);

CREATE INDEX IF NOT EXISTS idx_link_case ON case_anomaly_links(case_id);
CREATE INDEX IF NOT EXISTS idx_link_rule ON case_anomaly_links(rule_id);
CREATE INDEX IF NOT EXISTS idx_link_prob ON case_anomaly_links(anomaly_probability);

-- ------------------------------------------------------------
-- 辅助表：同群定义 (Peer Groups)
-- 描述：用于 peer_group 比较模式的同群划分
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS peer_groups (
    group_id        TEXT PRIMARY KEY,
    group_name      TEXT NOT NULL,
    discipline_id   TEXT,
    career_stage    TEXT,
    title_level     TEXT,                   -- 职称层级
    region          TEXT,
    age_range       TEXT,                   -- 如 "30-40"
    institution_tier TEXT,                  -- 机构层级
    member_count    INTEGER,
    member_ids      TEXT,                   -- JSON 数组
    update_date     TEXT
);

-- ------------------------------------------------------------
-- 辅助表：异常综合评分 (Composite Scores)
-- 描述：每个案例的综合异常指数，汇总所有规则结果
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS composite_scores (
    score_id            TEXT PRIMARY KEY,
    case_id             TEXT NOT NULL,
    calculation_date    TEXT NOT NULL,

    -- 各模式得分
    individual_score    REAL,               -- 与学科基线比较的综合得分
    peer_group_score    REAL,               -- 与同群基线比较的综合得分
    global_score        REAL,               -- 全局百分位得分

    -- 加权综合
    composite_score     REAL,               -- 加权综合异常指数
    score_formula       TEXT,               -- 使用的公式

    -- 置信度
    confidence_level    REAL,
    confidence_interval_lower REAL,
    confidence_interval_upper REAL,

    -- 排名
    percentile_in_discipline REAL,          -- 在学科内的百分位
    risk_level          TEXT,               -- low / medium / high / critical

    -- 触发的规则
    triggered_rules     TEXT,               -- JSON: [{"rule_id": "A001", "prob": 0.92}, ...]
    active_feature_count INTEGER,           -- 激活的特征数

    FOREIGN KEY (case_id) REFERENCES researcher_baseline(researcher_id)
);

CREATE INDEX IF NOT EXISTS idx_composite_case ON composite_scores(case_id);
CREATE INDEX IF NOT EXISTS idx_composite_score ON composite_scores(composite_score);

-- ------------------------------------------------------------
-- 视图：异常案例总览
-- ------------------------------------------------------------
CREATE VIEW IF NOT EXISTS v_anomaly_overview AS
SELECT
    r.researcher_id,
    r.name,
    r.institution,
    r.discipline_id,
    r.investigation_status,
    c.composite_score,
    c.risk_level,
    c.triggered_rules,
    c.active_feature_count,
    c.calculation_date
FROM researcher_baseline r
LEFT JOIN composite_scores c ON r.researcher_id = c.case_id
WHERE c.composite_score IS NOT NULL
ORDER BY c.composite_score DESC;

-- ------------------------------------------------------------
-- 视图：规则触发统计
-- ------------------------------------------------------------
CREATE VIEW IF NOT EXISTS v_rule_trigger_stats AS
SELECT
    a.rule_id,
    a.rule_name,
    a.rule_name_zh,
    COUNT(l.link_id) AS trigger_count,
    AVG(l.anomaly_probability) AS avg_probability,
    MAX(l.anomaly_probability) AS max_probability,
    AVG(l.deviation_score) AS avg_deviation
FROM anomaly_rules a
LEFT JOIN case_anomaly_links l ON a.rule_id = l.rule_id
WHERE a.is_active = 1
GROUP BY a.rule_id
ORDER BY trigger_count DESC;
