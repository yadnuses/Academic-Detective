================================================================================
  Academic Investigation Skill — 分析架构总图 (v3.2)
================================================================================

┌─────────────────────────────────────────────────────────────────────────────┐
│  TIER 0: 用户入口层 (Entry Point)                                           │
│  ─────────────────────────────────────                                      │
│                                                                             │
│  investigate.py  (CLI 编排器, 1,399行, 36个子命令)                          │
│                                                                             │
│  v2.x 原有命令:                                                             │
│    init, step, advance, status, validate, score, prompt, watermark          │
│    wechat, xiaohongshu, visualize, timeline, grants, negative, retrospect   │
│    international-fetch, international-build, missing-report                 │
│    review-aggregate, cross-border-merge                                     │
│                                                                             │
│  v3.0 deep_evidence 命令:                                                   │
│    preprint-monitor, review-cycle, stats-reverse-engineer, image-metadata   │
│    ethics-parse, trial-registry, conference-map, bilingual-detect           │
│    crossref-events, editorial-selfpub, reviewer-network, retraction-history │
│                                                                             │
│  v3.1 状态机命令:                                                           │
│    regress, add-task, unify                                                 │
│                                                                             │
│  v3.2 多agent命令:                                                          │
│    orchestrate  ← 多智能体协作模式入口                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
┌───────────────────────┐ ┌───────────────────────┐ ┌───────────────────────┐
│ TIER 1A: 核心基础设施 │ │ TIER 1B: v3.1 状态管理│ │ TIER 1C: v3.2 Agent   │
│ core/                 │ │ core/                 │ │ agents/               │
│ ─────────────────     │ │ ─────────────────     │ │ ─────────────────     │
│                       │ │                       │ │                       │
│ case_manager.py       │ │ recommendation_engine │ │ base.py               │
│   ├─ CaseManager      │ │   ├─ RuleEngine       │ │   └─ BaseAgent        │
│   └─ CaseStateMachine │ │   ├─ Recommendation   │ │                       │
│ config_loader.py      │ │   └─ 9 built-in rules │ │ zhu_xiansheng.py      │
│ db.py                 │ │                       │ │   └─ 执行师            │
│   ├─ scholars/papers  │ │ case_manager.py       │ │ dududu.py             │
│   ├─ relationships    │ │   └─ CaseStateMachine │ │   └─ 逻辑检查师        │
│   ├─ case_states      │ │                       │ │ huangmao.py           │
│   ├─ recommendations  │ │ db.py                 │ │   └─ 漫游者            │
│   ├─ decisions        │ │   ├─ case_states      │ │ laozhoumo.py          │
│   └─ unify_records    │ │   ├─ recommendations  │ │   └─ 监控师            │
│ router.py             │ │   ├─ decisions        │ │ orchestrator.py       │
│ utils.py              │ │   └─ unify_records    │ │   └─ 中央调度器        │
│ watermark.py          │ │                       │ │                       │
└───────────────────────┘ └───────────────────────┘ └───────────────────────┘
                    │                 │                 │
                    └─────────────────┴─────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  TIER 2: 调查轨道层 (Investigation Tracks)                                  │
│  ─────────────────────────────────────────                                  │
│                                                                             │
│  ┌───────────────────────┐ ┌───────────────────────┐ ┌───────────────────┐ │
│  │ domestic/             │ │ international/        │ │ cross_border/     │ │
│  │ 国内学者              │ │ 国外导师              │ │ 海归学者          │ │
│  │ ─────────────────     │ │ ──────────────────    │ │ ────────────────  │ │
│  │ data_importer.py      │ │ data_fetcher.py       │ │ merger.py         │ │
│  │ data_validator.py     │ │ data_validator.py     │ │ validator.py      │ │
│  │ scholar_data_builder  │ │ scholar_data_builder  │ │                   │ │
│  │ review_matcher.py     │ │ evaluator.py          │ │                   │ │
│  │ wechat_search.py      │ │ heuristics_classifier │ │                   │ │
  │  │ openalex_enricher.py  │ │ xiaohongshu_client    │ │                   │ │
│  │                       │ │ xiaohongshu_client    │ │                   │ │
│  │                       │ │ missing_reporter.py   │ │                   │ │
│  └───────────────────────┘ └───────────────────────┘ └───────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼  scholar_data.json
┌─────────────────────────────────────────────────────────────────────────────┐
│  TIER 3: 共享分析引擎层 (Analysis Engines)                                  │
│  ─────────────────────────────────────────                                  │
│                                                                             │
│  analysis/                                                                  │
│  ├── text_profiler.py          PDF/文本提取 & 基础统计                      │
│  ├── paper_quality_rubric.py   六维质量评分 (A/B+/B/C/D)                    │
│  ├── hybrid_scorer.py          脚本+LLM混合评分工作流                       │
│  ├── stylometry_profiler.py    语言风格计量学 & 代笔检测                    │
│  ├── citation_profiler.py      引用结构分析 (自引/互引/卡特尔)              │
  ├── journal_credibility_checker.py 期刊可信度检查 (DOAJ/SCImago/COPE/OASPA) │
  ├── source_evaluation.py      CRAAP Test 信息源可信度评估                  │
│  ├── common_heuristics.py      共享异常规则 (C01-C07)                       │
│  └── review_aggregator.py      多源评论合并 (国内+小红书+RMP)               │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  TIER 4: 关系网络层 (Network & Timeline)                                    │
│  ───────────────────────────────────────                                    │
│                                                                             │
│  network/                                                                   │
│  ├── network_visualizer.py     D3.js 交互式力导向关系图谱                   │
  ├── citation_constellation.py OpenAlex引用网络分析 (BARON/HEROCON简化)     │
│  ├── timeline_weaver.py        统一时间线编织 & 耦合窗口检测                │
│  ├── grant_linker.py           基金号关联分析                               │
│  ├── negative_space_analyzer.py 官方通报"缺失信息"分析                      │
│  └── investigation_retrospector.py 调查复盘 & 经验提取                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    ▼                                   ▼
┌─────────────────────────────────┐ ┌───────────────────────────────────────┐
│ TIER 5A: 报告生成层 (v2.x)      │ │ TIER 5B: 深度证据层 (v3.0)            │
│ report/                         │ │ deep_evidence/                        │
│ ─────────                       │ │ ─────────────────                     │
│                                 │ │                                       │
│ report_template.md              │ │ data_forensics/                       │
│   └─ 国内学者报告模板           │ │   ├─ stats_reverse_engineer.py   P1 ✅│
│                                 │ │   └─ image_metadata_extractor.py P1 ✅│
│ international_template.md       │ │                                       │
│   └─ 国际导师报告模板           │ │ publication_trace/                    │
│                                 │ │   ├─ preprint_monitor.py         P0 ✅│
│ report_prompt_optimizer.py      │ │   ├─ conference_paper_mapper.py  P2 ✅│
│   └─ 提示词优化器               │ │   ├─ bilingual_publication_detector ✅│
│                                 │ │   └─ crossref_event_tracker.py   P2 ✅│
│                                 │ │                                       │
│                                 │ │ ethics_audit/                         │
│                                 │ │   ├─ ethics_statement_parser.py  P1 ✅│
│                                 │ │   └─ clinical_trial_registry_checker ✅│
│                                 │ │                                       │
│                                 │ │ peer_review_intel/                    │
│                                 │ │   ├─ review_cycle_analyzer.py    P0 ✅│
│                                 │ │   ├─ editorial_self_publishing_detector│
│                                 │ │   │                                P2 ✅│
│                                 │ │   ├─ recommended_reviewer_network  P2 ✅│
│                                 │ │   └─ journal_retraction_history.py P2 ✅│
│                                 │ │                                       │
│                                 │ │ evidence_compiler/                    │
│                                 │ │   ├─ signal_aggregator.py        P2 ✅│
│                                 │ │   └─ evidence_chain_builder.py   P2 ✅│
│                                 │ │                                       │
└─────────────────────────────────┘ └───────────────────────────────────────┘
                    │                         │
                    └───────────┬─────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  TIER 6: v3.1 反应式状态机 (Reactive State Machine)                         │
│  ───────────────────────────────────────────────────                        │
│                                                                             │
│  Phase 状态流:                                                              │
│  initialized → collected → validated → analyzed → deep_evidence             │
│       → aggregated → reported → reviewed → archived                         │
│                                                                             │
│  核心组件:                                                                  │
│  ├── CaseStateMachine        9阶段状态管理，STATE.md读写                    │
│  ├── RuleEngine              9条动态推荐规则，实时评估                      │
│  │   R01: common_heuristics有异常 → preprint_monitor (P1)                 │
│  │   R02: 引用卡特尔 → stats_reverse_engineer+image_metadata (P1)         │
│  │   R03: 临床关键词 → ethics_parser+trial_registry (P2)                  │
│  │   R04: 中英文论文 → bilingual_detector (P2)                            │
│  │   R05: 期刊≥3次 → review_cycle_analyzer (P2)                          │
│  │   R06: 低质量集群 → editorial_selfpub+reviewer_network (P3)           │
│  │   R07: 有DOI → crossref_event_tracker (P3)                            │
│  │   R08: 有ISSN → journal_retraction_history (P4)                       │
│  │   R09: 有会议论文 → conference_paper_mapper (P3)                      │
│  └── DB v3 schema            case_states/recommendations/decisions/unify   │
│                                                                             │
│  反馈循环:                                                                  │
│  脚本A产出 → RuleEngine评估 → 触发新规则 → 推荐脚本B                      │
│     ↑                                              ↓                        │
│     └────── 脚本B产出 → RuleEngine评估 → 可能触发脚本C ────┘              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  TIER 7: v3.2 多智能体协作层 (Multi-Agent Collaboration)                    │
│  ───────────────────────────────────────────────────────                    │
│                                                                             │
│                         ┌─────────────────────┐                             │
│                         │    人类决策者        │                             │
│                         │   (周老师)          │                             │
│                         └──────────┬──────────┘                             │
│                                    ↑ ↓                                      │
│                         ┌──────────┴──────────┐                             │
│                         │    老周墨 (LaoZhoumo)│                             │
│                         │   监控师 / 人机接口   │                             │
│                         │   唯一写入STATE.md   │                             │
│                         └──────────┬──────────┘                             │
│                                    │                                        │
│         ┌──────────────────────────┼──────────────────────────┐             │
│         │                          │                          │             │
│         ▼                          ▼                          ▼             │
│  ┌─────────────┐          ┌─────────────┐          ┌─────────────┐        │
│  │ 朱先生       │          │ 嘟嘟嘟       │          │ 黄毛         │        │
│  │ ZhuXiansheng│          │ Dududu       │          │ Huangmao    │        │
│  │ 执行师       │          │ 逻辑检查师   │          │ 漫游者       │        │
│  │ 脚本执行     │          │ 推理分析     │          │ 并联思考     │        │
│  │ 数据链监控   │          │ 跨模块关联   │          │ 头脑风暴     │        │
│  │ CRITICAL判定 │          │ 工具选择     │          │ 假设生成     │        │
│  └──────┬──────┘          └──────┬──────┘          └──────┬──────┘        │
│         │                        │                        │               │
│         └────────────────────────┼────────────────────────┘               │
│                                  │                                        │
│                    ┌─────────────┴─────────────┐                          │
│                    ▼                           ▼                          │
│         ┌─────────────────────┐  ┌─────────────────────┐                  │
│         │  Orchestrator       │  │  共享存储            │                  │
│         │  中央调度器          │  │  STATE.md            │                  │
│         │                     │  │  agent_logs/         │                  │
│         │  register_agents()  │  │  outputs/            │                  │
│         │  run_round()        │  │  decisions/          │                  │
│         │  run_until_human()  │  └─────────────────────┘                  │
│         │  run_full()         │                                           │
│         │  cleanup()          │                                           │
│         └─────────────────────┘                                           │
│                                                                             │
│  回合执行流程:                                                              │
│  Round N:                                                                   │
│    1. 老周墨读取STATE.md，确定任务                                         │
│    2. 朱先生执行推荐工具队列                                                 │
│    3. 黄毛漫游数据（独立运行）                                               │
│    4. 嘟嘟嘟分析结果 + 评估黄毛假设                                         │
│    5. 老周墨检测CRITICAL                                                    │
│       → 有: 暂停，向人类汇报，等待决策                                      │
│       → 无: 更新STATE.md，准备下一轮                                       │
│                                                                             │
│  CLI入口: investigate.py orchestrate                                       │
│    --mode manual | auto                                                     │
│    --agents all | zhu,dudu,huangmao,lao                                    │
│    --max-rounds N                                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  TIER 9: v3.2 交付层 (Delivery Layer)                                       │
│  ─────────────────────────────────────                                      │
│                                                                             │
│  delivery/                                                                  │
│  ├── delivery_base.py          共享基类 (BaseDeliveryAgent, ChecklistRunner)│
│  ├── xiaotangdou.py            素材收集Agent                                │
│  │   └─ C01-C05 五步收集流程                                                │
│  │      C01: 遍历所有agent日志和产出                                        │
│  │      C02: 按9章报告框架分类                                              │
│  │      C03: 标记信息缺口和矛盾点                                           │
│  │      C04: 排序去重                                                       │
│  │      C05: 验证框架覆盖率                                                 │
│  ├── xiaojinjing.py            报告生成Agent                                │
│  │   └─ G01-G06 六步生成流程                                                │
│  │      G01: 读取素材包                                                     │
│  │      G02: 生成Markdown报告                                              │
│  │      G03: 生成HTML网络图 (调用network_visualizer)                        │
│  │      G04: 执行自检 (禁止条例+格式+内容)                                  │
│  │      G05: 输出自检报告                                                   │
│  │      G06: 写入交付清单                                                   │
│  └── checklists/               自检清单JSON                                 │
│      ├── ban_rules.json        禁止条例 (破折号/否定/排比/比喻/时间戳等)    │
│      ├── format_rules.json     格式一致性 (论文指代/章节编号/免责声明等)    │
│      └── content_rules.json    内容完整性 (九步法/证据链/平衡性/具体性)     │
│                                                                             │
│  通信协议:                                                                  │
│  小糖豆 → delivery/*.md (素材包)                                            │
│  小金金 ← delivery/*.md (读取素材)                                          │
│  小金金 → reports/ (最终交付物)                                             │
│  小金金 → reports/self_check_report.md (自检报告)                           │
│  若自检失败 → delivery/feedback/ (反馈给小糖豆补充)                         │
│                                                                             │
│  CLI入口:                                                                   │
│    investigate.py collect    (运行小糖豆)                                   │
│    investigate.py generate   (运行小金金)                                   │
│                                                                             │
│  与状态机集成:                                                              │
│  reviewed → collected → generated → archived                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  TIER 8: Schema & 规范层                                                    │
│  ─────────────────────────                                                  │
│                                                                             │
│  schema/                                                                    │
│  ├── scholar_data.schema.json                                               │
│  ├── international_scholar.schema.json                                      │
│  └── corruption_network.schema.json                                         │
│                                                                             │
│  deep_evidence/SIGNAL_SCHEMA.md        Deep Evidence Signal Schema v1.0    │
│  deep_evidence/FINAL_ARCHITECTURE_v3.1.md  v3.1架构方案                     │
│  deep_evidence/V3_2_IMPLEMENTATION_PLAN.md v3.2实现规划                     │
│  deep_evidence/MULTI_AGENT_DESIGN.md     v3.2多agent设计草案               │
│  deep_evidence/CHANGELOG_v3.0_schema_unification.md  Schema统一化工作日志  │
│                                                                             │
│  config.template.yaml                                                       │
│  evaluation_baselines.md                                                    │
│  report_language_spec.md                                                    │
│  heuristics.md                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

================================================================================
  数据流 (Data Flow) — v3.2 完整链路
================================================================================

  人工采集 ──→  data_importer / data_fetcher  ──→  scholar_data.json
     ↑                                              │
     │                                              ▼
  CNKI/WoS/官网                              analysis/ (质量评分)
  PDF/专著/学位论文                          network/ (关系图谱)
     │                                              │
     │                    ┌─────────────────────────┘
     │                    ▼
     │              ┌─────────────────┐
     │              │ v3.1 状态机     │
     │              │ RuleEngine      │
     │              │ CaseStateMachine│
     │              └─────────────────┘
     │                    │
     │                    ▼  动态推荐
     │              ┌─────────────────┐
     │              │ v3.2 多agent层  │
     │              │ 朱先生 → 执行   │
     │              │ 黄毛 → 漫游     │
     │              │ 嘟嘟嘟 → 分析   │
     │              │ 老周墨 → 协调   │
     │              │ Orchestrator    │
     │              └─────────────────┘
     │                    │
     │                    ▼  信号聚合
     └──────────────  deep_evidence/ (14个脚本)
                           │
                           ▼
                    ┌───────────────┐
                    │ signal_aggregator
                    │ evidence_chain_builder
                    └───────────────┘
                           │
                           ▼
  最终报告 ←── report/ ←── 证据链 + 信号汇总
  (Markdown/PDF)

================================================================================
  关键数字 (v3.2 完成后)
================================================================================

  Python代码总量:     ~22,000+ 行
  测试用例:           296 个 (全部通过)
  CLI子命令:          36 个
  Python文件:         85 个 (不含测试)
  v3.0 deep_evidence: 5 个子模块, 14 个脚本
  v3.1 状态机:        3 个核心模块 (recommendation_engine, case_state_machine, db_v3)
  v3.2 多agent:       6 个模块 (4角色 + orchestrator + base)
  v3.2 交付层:         4 个模块 (小糖豆 + 小金金 + 基类 + 自检清单)
  v3.2+ 免费工具:      4 个模块 (期刊可信度 + 引用网络 + CRAAP评估 + OpenAlex补充)
  JSON Schema:        3 个
  报告模板:           2 个 (国内/国际)
  动态推荐规则:       9 条 (R01-R09)
  状态机阶段:         11 个 (initialized → archived)
  CLI子命令:          40 个

================================================================================
  版本演进
================================================================================

  v2.x  双轨调查    domestic/ + international/ + cross_border/
        ↓
  v3.0  深度证据    deep_evidence/ 5子模块14脚本, Schema v1.0统一化
        ↓
  v3.1  反应式状态机  9阶段状态机 + RuleEngine动态推荐 + 反馈实时调整
        ↓
  v3.2  多智能体协作  4角色agent + Orchestrator回合制调度 + 人机决策闭环

================================================================================
