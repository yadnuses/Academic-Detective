# Academic Detective · 学术侦探

> 开源学术背景核查引擎 · 社区共建案例数据库  
> 选导师，先查一查。

官方网站：https://www.academic-detective.top/

---

## 注意
本系统面向所有人开源，所有人可以免费使用，我们希望通过工具的民主化达到学术平权
禁止在非本人允许的情况下将项目匿名商用，代码内已嵌入指纹特征，如需商用需标注版权声明和 MIT 许可证原文
商务合作：2097135128@qq.com

## 这是什么？

一个开源的学术背景调查系统。输入导师姓名和学校，系统从公开数据中提取证据链，自动生成调查报告。

**主要功能**：
- 论文产出核实（声称 vs 实际）
- 基于Nature同行审核机制构建的六维质量评分 + 文本风格分析
- 学科基准线偏差检测
- 与已知学术不端案例的模式比对
- 研学网 7.5 万+ 条结构化学生评价匹配
- 导师关系网络可视化（D3.js）
- Markdown → 精美 PDF 报告 + 自动图表

---

## 快速开始

```bash
# 1. 克隆
git clone https://github.com/your-org/academic-detective.git
cd academic-detective

# 2. 安装依赖
pip install -r archive/flat_export_redundant_20260501/requirements.txt

# 3. 查看所有可用工具
python run_investigation.py --list-tools

# 4. 启动调查
python run_investigation.py --name "导师姓名" --school "学校名称"
```

---

## 社区共建

我们一起建立全中国最大的导师生态数据库，把学术还给学术

| 你想做什么 | 怎么做 |
|:---|:---|
| 🔍 **查导师** | 提交 [Issue] → 社区认领 |
| 📤 **贡献案例** | 跑完引擎后 `--contribute` → 提交 PR |
| 🐛 **报告问题** | 提 Issue |
| ⭐ **支持项目** | Star、Fork、分享 |

---

## 项目结构

```
academic-detective/
├── run_investigation.py          # 一键入口
├── SKILL.md                      # 完整调查方法论（7步框架）
├── archive/flat_export_redundant_20260501/  # 37个核心脚本
├── scripts/                      # 工具索引 + 可视化包装
├── data/                         # 脱敏案例数据库 + 基准线
├── mentor-distill/               # 导师蒸馏器（可选）
├── _private/                     # 研学网评价数据库（脱敏）
└── 调查名单/                     # 占位（案例数据已脱敏）
```

---

## 开源协议

本项目采用 [GPL v3](LICENSE) 协议开源。
