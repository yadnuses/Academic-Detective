### International Track Workflow

For **foreign graduate advisors / international scholars**, use the **International Track** with different tools and evaluation criteria:

| Step | Primary Actor | Supporting Tool | Output |
|:---|:---:|:---|:---|
| 0. Case Registry | Human | `core/case_manager.py` | Unique case ID |
| 1. Init | Human | `investigate.py init --type international` | Config + DB with `investigation_type=international` |
| 2. Auto-Fetch | Scripts (free APIs) | `international/data_fetcher.py` | `auto_fetched.json` (papers, metrics, collaborators from OpenAlex/S2/ORCID) |
| 3. Student Reviews | Scripts | `international/xiaohongshu_client.py` | Xiaohongshu reviews with sentiment/dimension extraction |
| 4. Manual Supplement | Human | `international/missing_reporter.py` | Markdown guide: what's missing + where to look |
| 5. Build | Scripts | `international/scholar_data_builder.py` | `scholar_data.json` conforming to `international_scholar.schema.json` |
| 6. Evaluate | Scripts | `international/evaluator.py` | JCR quartile table, tenure benchmark, grant portfolio assessment |
| 7. Heuristics | Scripts | `international/heuristics_classifier.py` | Flags: I01 predatory journal, I02 paper mill, I04 citation cartel, etc. |
| 8. Validate | Scripts | `international/data_validator.py` | Schema + logic validation |
| 9. Report Generation | LLM | `report/international_template.md` | International report (tenure clock, OA cost, visa/salary reviews) |
| 10. Delivery | Human | `core/watermark.py` | Watermarked report |

**Key CLI commands for international track:**
```bash
python3 scripts/investigate.py init --type international --config ./config.yaml
python3 scripts/investigate.py international-fetch --config ./config.yaml
python3 scripts/investigate.py international-build --config ./config.yaml --xiaohongshu ./data/xhs_reviews.json
python3 scripts/investigate.py missing-report --scholar-data ./scholar_data.json
python3 scripts/investigate.py review-aggregate --domestic ./reviews.json --xiaohongshu ./xhs.json --output ./merged_reviews.json
```

See `scripts/README.md` for detailed usage instructions.

### 显式工具索引与案件检查清单

为避免工具路径混乱和流程遗漏，系统提供两个配套文件：

| 文件 | 路径 | 用途 |
|:---|:---|:---|
| **显式工具索引** | `scripts/TOOLS_INDEX.md` | 列出所有脚本的真实路径（排除根目录 shim），按调查步骤分类，附带输入/输出说明和常见路径陷阱 |
| **案件检查清单模板** | `scripts/templates/CHECKLIST.md` | 每个案件初始化时必须复制到案件根目录，逐条勾选确保不跳过关键步骤 |

**强制要求**：
1. 每次启动新调查，`investigate.py init` 完成后必须将 `scripts/templates/CHECKLIST.md` 复制到案件目录，并命名为 `CHECKLIST.md`。
2. 执行任何脚本前，先在 `scripts/TOOLS_INDEX.md` 中确认该工具的真实路径。**`scripts/` 根目录下绝大多数 <500 字节的 `.py` 文件是兼容性 shim，真实实现位于 `analysis/`、`domestic/`、`international/`、`network/`、`report/` 等子目录中。**
3. Step 3 质量评估中，**每篇 PDF 必须依次经过 `analysis/text_profiler.py` → `analysis/paper_quality_rubric.py` 完整流程**，禁止跳过六维评分直接输出主观质量判断。

### 补充流程：PDF 论文直接审查

当用户直接提供论文 PDF（而非从数据库导出的结构化数据）时，使用此补充流程。此流程与主 7 步框架并行，LLM 作为主要分析者。

**适用场景**：
- 用户提供单篇论文 PDF 要求"查重"、"打假"、"检测造假"
- 用户提供 PDF 作为调查线索的一部分
- 无法获取结构化数据（如 Excel/CSV），仅有论文原文

**流程**：

| 步骤 | 动作 | 输出 |
|:---|:---|:---|
| 1. 读取 PDF | 用 `Read` 工具读取 PDF 全文，提取文本、表格、Figure caption | 论文基本信息（标题、作者、期刊、DOI） |
| 2. 六式扫描 | 按"LLM 视觉/文本检测清单"逐项检查（见 Step 5 子章节） | 每个可疑点的位置、类型、证据、严重程度 |
| 3. 数值提取 | 从表格中手动提取数值数据，保存为 CSV | 可选：喂给 `data_integrity_checker.py` 做统计验证 |
| 4. 交叉验证 | 执行 Step 5.5 内部一致性交叉验证 | 异常点关联性判断 |
| 5. 报告输出 | 按报告模板生成结构化发现 | Markdown 格式审查报告 |

**与主流程的关系**：
- PDF 直接审查的输出可作为主 7 步框架 Step 5（异常检测）的输入之一
- 如果同时有结构化数据（Excel），PDF 审查结果应与脚本分析结果交叉验证
- PDF 审查中的数值提取结果可直接喂给 `data_integrity_checker.py` 进行自动化统计检测

> **局限性声明**：LLM 对 PDF 图片的分析基于视觉理解，无法进行像素级 ELA（Error Level Analysis）或 EXIF 元数据分析。对于需要精确图像比对的情况，标注"建议使用专业工具（如 ImageTwin、Forensically）进一步验证"。

