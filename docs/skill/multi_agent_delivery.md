### 附录：v3.2 多智能体协作层 (Multi-Agent Collaboration Layer)

#### 四大 Agent 角色

| 角色 | 模块 | 人格定位 | 核心职责 |
|:---|:---|:---|:---|
| 朱先生 | `zhu_xiansheng.py` | 沉默寡言、只信输出 | 执行脚本队列、监控数据链、标记 CRITICAL |
| 嘟嘟嘟 | `dududu.py` | 冷静犀利、不信巧合 | 跨模块关联信号、评估置信度、生成推荐任务 |
| 黄毛 | `huangmao.py` | 脑洞大开、不按常理 | 自由漫游原始数据、并联思考、提出假设 |
| 老周墨 | `laozhoumo.py` | 沉稳全局、关键开口 | 唯一写入 STATE.md、人机接口、决策拦截 |

#### 回合执行流程 (Round-based)

```
Round N:
  1. 老周墨读取 STATE.md，确定任务队列
  2. 朱先生顺序执行推荐工具队列 → 写 summary.json
  3. 黄毛后台漫游原始数据 → 写 findings.json
  4. 嘟嘟嘟读取结果 + 假设 → 分析并写 recommendations.json
  5. 老周墨检测 CRITICAL
     → 有: 暂停，向人类汇报，等待决策
     → 无: 更新 STATE.md，准备下一轮
```

#### 通信协议

- **共享存储**: 案件目录下的 `STATE.md`（老周墨独占写入）+ `agent_logs/` + `outputs/`
- **事件通知**: CRITICAL 标记写入 `agent_logs/{name}/critical.json`，老周墨检测后立即暂停
- **可信度分级**: 黄毛的假设必须标记为 `wild_guess` / `plausible` / `strongly_suggested`

#### 典型协作场景

**场景1: 正常运行流**
老周墨生成任务 → 朱先生执行 → 黄毛漫游发现线索 → 嘟嘟嘟分析并推荐新工具 → 老周墨更新队列 → 循环

**场景2: 重大线索拦截**
朱先生执行中发现 MD5 重复图片 → 标记 CRITICAL → 老周墨暂停全部 agent → 向人类汇报并请求决策 → 解析指令生成新任务 → 恢复

#### CLI 入口

```bash
# 启动多 agent 协作模式（默认 manual，每轮等待确认）
python3 scripts/investigate.py orchestrate --case-dir ./cases/xxx/

# 自动模式（运行到 CRITICAL 或完成）
python3 scripts/investigate.py orchestrate --case-dir ./cases/xxx/ --mode auto

# 只启动指定 agent
python3 scripts/investigate.py orchestrate --case-dir ./cases/xxx/ --agents zhu,dudu
```

---

### 附录：v3.2 交付层 (Delivery Layer)

#### 交付层双Agent架构

```
delivery/
├── delivery_base.py       # 共享基类 (BaseDeliveryAgent, ChecklistRunner)
├── xiaotangdou.py         # 素材收集Agent (小糖豆)
├── xiaojinjing.py         # 报告生成Agent (小金金)
└── checklists/
    ├── ban_rules.json     # 禁止条例自检
    ├── format_rules.json  # 格式一致性自检
    └── content_rules.json # 内容完整性自检
```

**小糖豆 (Xiaotangdou)**：素材收集与整理Agent
- 遍历所有Agent日志和产出文件
- 按报告框架9章节分类素材
- 标记信息缺口和矛盾点
- 输出结构化素材包到 `delivery/` 目录

**小金金 (Xiaojinjing)**：报告生成与自检Agent
- 读取小糖豆的素材包（不读取原始日志）
- 生成Markdown报告和HTML网络图
- 执行三类自检：禁止条例、格式一致性、内容完整性
- 自检失败时输出反馈，等待小糖豆补充后重新生成

#### 自检清单核心规则

| 类别 | 规则 | 严重性 |
|:---|:---|:---:|
| 禁止条例 | 无破折号、无否定句式、无比喻修辞 | error |
| 禁止条例 | 无报告生成时间、无调查者身份、无委托人信息 | error |
| 格式一致性 | 论文必须使用具体标题指代，禁止编号 | error |
| 格式一致性 | 报告末尾必须包含免责声明 | error |
| 内容完整性 | 覆盖全部9个章节 | error |
| 内容完整性 | 内容具体不概括，两面性平衡 | warning |

#### CLI入口

```bash
# 运行小糖豆收集素材
python3 scripts/investigate.py collect --case-dir ./cases/xxx/

# 运行小金金生成报告
python3 scripts/investigate.py generate --case-dir ./cases/xxx/

# 强制交付（自检有警告时）
python3 scripts/investigate.py generate --case-dir ./cases/xxx/ --force

# 智能辅助推进：自动检查阶段条件，确认后自动推进
python3 scripts/investigate_visual.py --case-dir ./cases/xxx/ smart-step
```

#### 状态机集成

交付层扩展状态机阶段流：
```
reviewed → collected → generated → archived
```

- `collected`: 小糖豆完成素材收集
- `generated`: 小金金完成报告生成并通过自检

---

