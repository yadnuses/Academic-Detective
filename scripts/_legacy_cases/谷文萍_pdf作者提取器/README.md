# 谷文萍案 PDF 作者提取器（历史脚本归档）

## 来源
原存放于 `调查名单/谷文萍_中南大学湘雅医院/`，为个案专用脚本，硬编码了谷文萍的姓名和路径。

## 脚本用途
- `analyze_pdfs_v5.py`：从 PDF 论文第一页提取作者列表，识别目标学者排序、判断通讯/第一作者身份、提取标题/期刊/年份/基金信息，输出 JSON + Markdown。
- `fix_results.py`：基于人工逐页核对，对自动提取结果进行手动修正，输出最终版报告。

## 迭代历史
v1→v5 为作者提取策略的逐步优化：
- v1：基础提取
- v2：增加相邻行合并
- v3：增加机构前缀过滤
- v4：增加全文本回退策略
- v5：增加 PDF 页序异常检测、专家共识分类

## 可复用逻辑（待提取）
- `preprocess_line` / `parse_names_from_line`：中文作者姓名清洗与解析
- `is_likely_author_line`：作者行启发式判断
- `extract_title` / `extract_journal` / `extract_year`：论文元数据提取
- `find_sections`：基金/通讯作者章节定位
- `generate_markdown`：结构化报告生成

## 状态
已归档，个案文件夹中已删除原始副本。输出结果（`谷文萍论文作者分析_最终.md/json`）保留在调查名单中。
