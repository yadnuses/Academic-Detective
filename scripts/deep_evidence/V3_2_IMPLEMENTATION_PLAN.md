# v3.2 多智能体协作层 — 实现规划

> 基于 v3.1 反应式状态机 + 多agent协作测试验证结果
> 日期: 2026-04-17

---

## 一、目录结构

```
scripts/
├── agents/
│   ├── __init__.py
│   ├── base.py              # Agent基类（共享接口）
│   ├── zhu_xiansheng.py     # 执行师
│   ├── dududu.py            # 逻辑检查师
│   ├── huangmao.py          # 漫游者
│   ├── laozhoumo.py         # 监控师/协调器
│   └── orchestrator.py      # 中央调度器
├── core/                    # v3.1 已有模块
│   ├── case_manager.py
│   ├── recommendation_engine.py
│   └── db.py
├── investigate.py           # 新增 orchestrate 子命令
└── ...
```

---

## 二、模块设计

### 2.1 base.py — Agent 基类

所有agent继承的共享接口：

```python
class BaseAgent:
    def __init__(self, case_dir: Path, name: str):
        self.case_dir = case_dir
        self.name = name
        self.logger = get_logger(f"agent.{name}")
        self.log_dir = case_dir / "agent_logs" / name
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    def read_input(self, source: str) -> dict:
        """读取指定来源的输入数据。"""
        pass
    
    def write_output(self, data: dict, filename: str = "output.json"):
        """写入输出到 agent_logs/{name}/ 目录。"""
        pass
    
    def check_critical(self) -> bool:
        """检查是否有 CRITICAL 标记需要上报。"""
        pass
    
    def run(self) -> dict:
        """主执行入口，子类必须实现。"""
        raise NotImplementedError
```

### 2.2 zhu_xiansheng.py — 执行师

**职责:** 接收任务队列，按顺序执行脚本，监控运行状态，提取关键结果。

**输入:** `STATE.md` 中的任务队列
**输出:** `agent_logs/zhu_xiansheng/summary.json` + `agent_logs/zhu_xiansheng/critical.json` (如有)

**核心方法:**
- `run_task(task: dict) -> dict`: 执行单个工具，返回运行摘要
- `run_queue(queue: list[dict]) -> list[dict]`: 顺序执行任务队列
- `monitor_data_chain(input_file: Path, output_file: Path) -> bool`: 验证数据链传递
- `extract_summary(output_json: Path) -> dict`: 提取输出JSON中的关键信息
- `search_web(query: str) -> dict`: 联网搜索补充信息

**CRITICAL 判定规则:**
- 脚本返回码非零
- 输出JSON为空或Schema不匹配
- 发现 confidence ≥ 0.85 的信号
- 发现与已撤稿/已曝光论文的关联

### 2.3 dududu.py — 逻辑检查师

**职责:** 读取执行结果，深入分析，跨模块关联，生成推荐。

**输入:** 朱先生的summary.json + 黄毛的findings.json + 原始输出JSON
**输出:** `agent_logs/dududu/recommendations.json` + `agent_logs/dududu/analysis.json`

**核心方法:**
- `analyze_signals(signals: list[dict]) -> dict`: 分析信号含义
- `cross_module_correlation(outputs: list[Path]) -> list[dict]`: 跨模块关联
- `evaluate_hypothesis(hypothesis: dict) -> dict`: 评估黄毛的假设
- `generate_recommendations(analysis: dict) -> list[dict]`: 生成推荐任务
- `assess_confidence(signal: dict) -> float`: 重新评估置信度

**跨模块关联模板:**
- stats_anomaly + image_duplicate → 数据造假链
- preprint_overlap + fast_review + editorial_self_publish → 审稿流程绕过链
- missing_registry + missing_ethics_statement → 伦理违规链

### 2.4 huangmao.py — 漫游者

**职责:** 自由漫游所有原始数据，并联思考，提出假设。

**输入:** 所有原始数据文件（不经过过滤）
**输出:** `agent_logs/huangmao/findings.json`

**核心方法:**
- `roam_data(data_dir: Path) -> list[dict]`: 漫游数据，发现模式
- `cross_domain_associate(findings: list[dict]) -> list[dict]`: 跨维度联想
- `brainstorm(seed: dict) -> list[dict]`: 基于种子数据头脑风暴
- `mark_credibility(finding: dict) -> str`: 标记可信度

**漫游策略:**
- 时间线漫游：检查论文发表时间的聚类、间隔异常
- 标题漫游：检查标题相似度、关键词重复
- 作者漫游：检查合作者网络、机构变动
- 基金漫游：检查基金号重复、资助范围匹配
- 期刊漫游：检查期刊分布、审稿周期

### 2.5 laozhoumo.py — 监控师

**职责:** 全局监控、人机接口、决策拦截、任务分发。

**输入:** 所有agent的状态和输出
**输出:** 更新后的 `STATE.md` + 决策请求（向人类）

**核心方法:**
- `monitor_all_agents() -> dict`: 监控所有agent状态
- `detect_critical() -> list[dict]`: 检测CRITICAL标记
- `request_decision(context: dict) -> str`: 向人类发送决策请求
- `parse_human_response(response: str) -> dict`: 解析人类决策
- `broadcast_task_update(tasks: list[dict])`: 向所有agent广播任务更新
- `update_state_md(updates: dict)`: 更新STATE.md
- `pause_all()`: 暂停所有agent任务流
- `resume_all()`: 恢复所有agent任务流

**决策请求格式:**
```markdown
## 决策请求

**位置:** {case_id} / {phase} / {stage}

**发现:** 
{关键发现的简洁描述}

**影响评估:**
{发现意味着什么}

**建议选项:**
A. {选项A描述}
B. {选项B描述}
C. {选项C描述}

请回复选项字母，或描述您的决策。
```

### 2.6 orchestrator.py — 中央调度器

**职责:** 管理agent生命周期，协调执行顺序，处理异常。

**核心方法:**
- `start_agents(case_dir: Path, mode: str) -> dict`: 启动指定agent
- `run_round(case_dir: Path) -> dict`: 执行一个完整回合
- `run_until_human_decision(case_dir: Path) -> dict`: 运行直到需要人类决策
- `cleanup(case_dir: Path)`: 清理agent日志和临时文件

**回合执行流程:**
```
Round N:
  1. 老周墨读取STATE.md，确定当前阶段和任务队列
  2. 分发任务给朱先生
  3. 朱先生执行 → 写summary.json
  4. 同时启动黄毛漫游（后台）
  5. 朱先生完成后，嘟嘟嘟读取结果分析
  6. 黄毛提交findings.json
  7. 嘟嘟嘟综合分析和假设，生成recommendations.json
  8. 老周墨读取所有输出
  9. 检测CRITICAL → 如有则暂停并请求决策
  10. 无CRITICAL → 更新STATE.md，准备下一轮
```

---

## 三、与 v3.1 的集成

### 3.1 investigate.py 新增 `orchestrate` 子命令

```bash
# 启动多agent协作模式
investigate.py orchestrate --case-dir ./cases/zhangsan

# 选项
--mode manual      # 每轮结束后等待人类确认（默认）
--mode auto        # 自动运行直到CRITICAL或完成
--agents all       # 启动全部4个agent（默认）
--agents zhu,dudu  # 只启动指定agent
```

### 3.2 与现有命令的兼容

- `step` / `advance` / `status` / `regress` / `add-task` / `unify` 保持单agent模式可用
- `orchestrate` 是多agent模式的入口
- 单agent模式和多agent模式共享同一个STATE.md和数据库

---

## 四、实施步骤

### Step 1: 基础设施（1个agent并行）
- [ ] 创建 `agents/` 目录和 `__init__.py`
- [ ] 实现 `agents/base.py`（Agent基类）
- [ ] 实现 `agents/orchestrator.py`（中央调度器框架）

### Step 2: 朱先生（1个agent并行）
- [ ] 实现 `agents/zhu_xiansheng.py`
- [ ] 实现任务队列执行逻辑
- [ ] 实现数据链监控
- [ ] 实现CRITICAL判定

### Step 3: 嘟嘟嘟 + 黄毛（2个agent并行）
- [ ] 实现 `agents/dududu.py`
- [ ] 实现跨模块关联分析
- [ ] 实现 `agents/huangmao.py`
- [ ] 实现数据漫游策略

### Step 4: 老周墨 + 集成（1个agent）
- [ ] 实现 `agents/laozhoumo.py`
- [ ] 实现决策拦截和任务分发
- [ ] 集成所有agent到orchestrator
- [ ] 新增 `investigate.py orchestrate` 子命令

### Step 5: 测试
- [ ] 编写 agent 单元测试
- [ ] 编写 orchestrator 集成测试
- [ ] 端到端测试（模拟完整案件）
- [ ] 运行全量 pytest

---

## 五、关键技术决策

### 5.1 Agent 通信机制

**选择: 文件系统共享（已验证可行）**

理由:
- Kimi CLI 的 Agent 工具本质上是独立进程
- 文件系统是最可靠的跨进程通信方式
- STATE.md 作为中央总线，人类可直接阅读
- 审计trail自动留存

替代方案（不采用）:
- 内存共享: 不可行，agent是独立进程
- 网络socket: 过度设计，增加复杂度
- 消息队列: 需要额外依赖

### 5.2 Agent 执行模式

**选择: 回合制（Round-based）**

每个回合:
1. 老周墨确定任务
2. 朱先生执行（顺序）
3. 黄毛漫游（可与朱先生并行）
4. 嘟嘟嘟分析（依赖朱先生完成）
5. 老周墨汇总决策

理由:
- 符合学术调查的审慎性质
- 避免agent之间的竞争条件
- 人类可以在每个回合结束时干预

### 5.3 CRITICAL 拦截策略

**选择: 立即暂停全部任务流**

触发条件:
- 任何agent标记CRITICAL
- 置信度 ≥ 0.85 的异常信号
- 与已撤稿论文的关联

暂停后:
1. 老周墨向人类汇报
2. 等待人类决策
3. 解析决策，生成新任务
4. 恢复或调整任务流

---

## 六、风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|:---|:---:|:---:|:---|
| Agent超时（如investigate.py重构） | 中 | 中 | 拆分任务为更小的subagent调用 |
| Agent间状态不一致 | 低 | 高 | STATE.md由老周墨独占写入 |
| 黄毛的低质量假设淹没系统 | 中 | 中 | 可信度分级 + 嘟嘟嘟过滤 |
| 多agent增加token消耗 | 高 | 中 | 提供--agents选项，按需启动 |
| 与v3.1状态机冲突 | 低 | 高 | 共享STATE.md格式，orchestrator只调度不修改状态机逻辑 |

---

## 七、验收标准

1. [ ] 可以并行启动4个agent，无冲突
2. [ ] 朱先生能顺序执行推荐工具队列
3. [ ] 黄毛能在后台漫游并提出假设
4. [ ] 嘟嘟嘟能分析结果并生成推荐
5. [ ] 老周墨能检测CRITICAL并暂停任务流
6. [ ] 人类决策后能正确恢复任务流
7. [ ] 所有操作保留审计trail
8. [ ] pytest 296个用例全部通过
9. [ ] 单agent模式（v3.1）不受多agent模式影响
