# Academic Investigation Scripts

Semi-automatic tool chain for scholar background investigation.

**Core principle**: Scripts handle repetitive computation and PDF parsing. Human judgment remains central for database search, source verification, and final interpretation.

---

## Quick Start

### 1. Configure the investigation

```bash
cp config.template.yaml config.yaml
# Edit config.yaml with scholar info and file paths
```

### 2. Manual data collection (Human)

| Task | Action | Output |
|:---|:---|:---|
| **Database search** | Log into CNKI/Wanfang/WoS, search scholar, export results | `data/cnki_results.json` or CSV |
| **Institutional pages** | Visit official bio pages, save HTML or snapshot | `data/official_page_*.html` |
| **Monographs** | Purchase/borrow PDFs of key books | `pdfs/monograph_*.pdf` |
| **Dissertation** | Download from CNKI dissertations or library | `pdfs/dissertation.pdf` |
| **WeChat articles** | Run `wechat_search.py` for supplementary leads | `data/wechat_articles/*.md` |

### WeChat article search (supplementary leads)

```bash
# Standard run (requires playwright + camoufox in the Python environment)
python scripts/wechat_search.py --keyword "学者姓名" --limit 10 --download --output ./data/wechat_articles

# If camoufox is only available via the wechat-article-to-markdown uv tool
uv tool run --from wechat-article-to-markdown python scripts/wechat_search.py \
  --keyword "学者姓名" --limit 10 --download --output ./data/wechat_articles

# Or via the CLI wrapper
python investigate.py wechat --keyword "学者姓名" --limit 10
```

**What it does**:
- Searches Sogou WeChat for articles matching the keyword
- Resolves Sogou redirect links to real `mp.weixin.qq.com` URLs using Playwright + camoufox
- Fetches article text via direct HTTP and saves each article as a single Markdown file (no images)
- Outputs a JSON summary of titles, dates, URLs, and saved file paths

**Important caveats**:
- WeChat articles are **unofficial sources**. They may contain rumors, gossip, and unverified claims.
- Treat findings as **hypothesis generators** or supplementary color, not standalone evidence.
- Cross-check any specific allegation against verifiable public records before inclusion in the main findings.

### 3. Run text profiling on PDFs / Markdown / text files

```bash
# Basic usage (PDF)
python text_profiler.py --input ./pdfs/monograph_1.pdf --output ./data/monograph_1_profile.json

# Markdown or plain text files are also supported directly
python text_profiler.py --input ./texts/paper_1.md --output ./data/paper_1_profile.json

# With custom term categories
python text_profiler.py --input ./pdfs/monograph_1.pdf \
  --terms ./custom_terms.json \
  --output ./data/monograph_1_profile.json \
  --save-text ./data/monograph_1_text.txt
```

**What it does**:
- Extracts full text from PDF (tries `pdfplumber` → `PyMuPDF` → `PyPDF2`) or reads Markdown / plain text directly
- Counts term frequencies by category (political/academic/theory/methodology)
- Counts originality markers (e.g. "笔者认为", "本文发现")
- Extracts reference section and counts foreign ratio / latest year
- Extracts chapter structure heuristically
- Outputs structured JSON for LLM downstream analysis

### 3b. Run peer-review-aligned quality scoring

#### Single paper (manual)

```bash
python paper_quality_rubric.py \
  --profile ./data/monograph_1_profile.json \
  --observations ./data/monograph_1_observations.json \
  --output ./data/monograph_1_quality.json
```

#### Batch hybrid scoring (script + LLM)

```bash
# Step 1: Script extracts profiles and builds LLM review pack
python scripts/hybrid_scorer.py prepare \
  -i ./pdfs \
  -o ./data/hybrid_scores \
  -e 3000

# Step 2: Human/LLM reviews llm_review_request.md and writes llm_observations_batch.json

# Step 3: Script applies observations and outputs ranked table
python scripts/hybrid_scorer.py apply \
  -i ./pdfs \
  -o ./data/hybrid_scores
```

Or use the CLI wrapper:

```bash
python investigate.py score -i ./pdfs -o ./data/hybrid_scores
# ... after LLM review ...
python investigate.py score -i ./pdfs -o ./data/hybrid_scores --apply
```

**What it does**:
- Ingests `text_profiler.py` output and optional human/LLM observations
- Scores the paper across 6 dimensions aligned with Nature/Springer/ACM peer-review criteria
- Outputs A/B+/B/C/D ratings and red-flag alerts
- Provides a standardized vocabulary for cross-paper quality comparison
- **Hybrid mode** allows LLM to correct script blind spots (authorship role, paper type, missing references due to formatting, etc.)

### 4. Assemble structured data (Human + LLM)

Create a `scholar_data.json` that aggregates:
- Manually verified counts from CNKI
- `text_profiler.py` JSON outputs
- Institutional timeline facts
- Relationship network observations

Use the LLM to assist with qualitative assessments (quality, anomalies, interpretation).

### 5. Validate data before report generation

```bash
# Check for missing fields and logic errors
python data_validator.py --input ./scholar_data.json

# Auto-fill missing defaults
python data_validator.py --input ./scholar_data.json --fix
```

Validation rules include:
- Required field presence
- Numeric consistency (claimed vs verified papers)
- Red-flag detection (>20% discrepancy)
- Multi-source evidence check (≥2 sources per anomaly)
- Confidence rating format check

### 6. Build unified data file

```bash
python scholar_data_builder.py --config ./config.yaml --data-dir ./data --output ./scholar_data.json --fix
```

This aggregates `config.yaml`, `text_profiler.py` outputs, `citation_profiler.py` outputs, and any other script JSONs into a single `scholar_data.json` ready for validation and report generation.

### 7. Generate final report prompt

```bash
python report_prompt_optimizer.py --data ./scholar_data.json --template ./report_template.md --llm claude --output ./report_prompt.md
```

This adapts the generic template for your target LLM (Claude/GPT/Kimi) and injects a summarized data context for better adherence.

### 8. Generate final Markdown report

Feed `report_prompt.md` to the LLM. The LLM fills in each `{{placeholder}}` and writes the balanced, two-sided Markdown report. **The output layer is strictly Markdown**; no additional formats (PDF, poster, slides) are produced by the core workflow.

---

## Script Reference

### `text_profiler.py`

**Input**: PDF, Markdown (.md), or plain text (.txt) file path  
**Output**: JSON profile + optional raw text file

Key output fields:
- `basic_stats`: character count, word count, line count
- `term_frequency`: categorized term counts
- `originality_markers`: presence of first-person scholarly claims
- `references`: count, foreign ratio, latest cited year, sample
- `chapter_structure`: extracted headings
- `text_preview`: first 3000 characters for quick LLM inspection

### `hybrid_scorer.py`

**Input**: Folder of papers (PDF / .md / .txt)  
**Output**: `llm_review_pack.json` + `_final_ranked_report.json`

Two-stage orchestrator for batch scoring:
1. `prepare`: runs `text_profiler.py` on every paper, extracts ~3000-char excerpts, builds `llm_review_request.md`
2. `apply`: reads `llm_observations_batch.json`, runs `paper_quality_rubric.py` for each paper, prints ranked table and saves JSON

Key design: scripts handle counting and formatting; LLM handles qualitative judgment (paper type, authorship role, originality override).

### `data_validator.py`

**Input**: `scholar_data.json`  
**Output**: Validation report in terminal

Run with `--fix` to inject placeholder values for missing required fields.

### `network_visualizer.py`

**Input**: `scholar_data.json` (must have populated `relationship_network` fields)  
**Output**: `{prefix}_network.html` + `{prefix}_network.json`

Generates an interactive D3.js force-directed graph of the scholar's academic relationship network:
- **Nodes**: scholar (center), advisor, key collaborators, editorial board connections, institutional dependencies, citation red-flag citers
- **Edges**: advisor_of, collaborates_with, editorial_board, affiliated_with, cites (anomaly links dashed)
- **Interactivity**: drag nodes, zoom/pan, click for details, layer filters

**CLI usage**:
```bash
python scripts/network_visualizer.py --input ./scholar_data.json --output-dir ./reports
# Or via the orchestrator
python investigate.py visualize --data ./scholar_data.json --output-dir ./reports
```

**Auto-generation**: When running `scholar_data_builder.py` with `--fix`, if `relationship_network` contains data, the visualization is generated automatically into `./reports/`.

### `wechat_search.py`

**Input**: Keyword (usually scholar name) + result limit  
**Output**: `data/wechat_articles/*.md` + JSON summary

Supplementary search channel for WeChat Official Account articles. Useful for finding:
- Book or course promotions that confirm authorship claims
- Institutional party-branch or faculty news that verify titles/roles
- Informal gossip or rumors that may generate investigation leads

**Reliability**: ⭐☆☆☆☆ — every finding must be corroborated.

### `report_template.md`

Markdown template matching the established case-study format (based on three anonymized verified case studies). Use as prompt material for the LLM report generation step.

### `config.template.yaml`

Central configuration for a single investigation: scholar identity, manual source file paths, claims to verify, peer cohort for comparison, and output settings. Includes a `wechat_articles` section for recording search parameters and fetched article paths.

### `business_network.py` (planned — not yet implemented)

> **Status**: 该脚本目前尚未实现。调查者现阶段需通过手工方法完成商业利益网络分析。

**手工替代方法**：
1. 在天眼查/企查查检索学者姓名 + 城市，保存截图和 CSV 导出。
2. 在国家专利数据库检索公司申请人，提取发明人名单。
3. 用 Excel 或 Markdown 表格建立「公司-股权-专利发明人-论文时间」对照表，标记 6 个月内的时间耦合。

**未来脚本设计目标**（供参考）：
- **Input**: Manually collected business registration snapshots, patent lists, and horizontal project records
- **Output**: JSON report mapping corporate affiliations, inventor overlaps, and project-publication time coupling
- Key functions: Normalize business registration data; cross-match patent inventors against scholar team members; flag project funding dates that cluster within 6 months of related paper submissions.
3. Manually record horizontal project metadata (company, amount, start date, participants).
4. Run the script to generate overlap tables and coupling alerts.

### `digital_archaeologist.py` (planned)

**Input**: Web archive snapshots, CV versions, and cross-platform biography extracts  
**Output**: JSON diff report tracking field-level changes across time and platforms

Key functions:
- Parse multiple versions of a scholar bio into structured fields (degrees, positions, paper counts)
- Generate year-over-year diffs with before/after highlighting
- Compare claimed numbers against verified database counts

**Typical workflow**:
1. Capture Wayback Machine snapshots of the scholar's institutional page.
2. Collect CV/bio versions from different years (conference programs, grant applications).
3. Export platform bios (CNKI, Baidu Baike, Google Scholar) on the same day.
4. Run the script to produce a cross-platform inconsistency table.

### `citation_profiler.py`

**Input**: Structured citation records JSON (exported manually from CNKI, Google Scholar, or Web of Science)  
**Output**: JSON report with h-index anomalies, self-citation rates, mutual-citation cartel signals, and journal quality breakdown

Key output fields:
- `h_index_analysis`: year-over-year growth rates and anomaly flags
- `citation_structure`: self/team/mutual/third-party ratios, tier breakdown, top citing authors/institutions
- `red_flags`: triggered signals (h-index jump, high self-citation, dense mutual citation, predatory journal concentration)

**Typical workflow**:
1. Manually export the scholar's top 50-100 citing papers from a database.
2. Classify each journal into tier A/B/C/D (human judgment or institutional list).
3. Save as JSON following the schema in the script docstring.
4. Run the script for quantitative analysis.

### `stylometry_profiler.py`

**Input**: Manifest JSON mapping PDF/text files to labels (`scholar`, `target`, `student`)  
**Output**: JSON report with stylometric feature vectors, cosine-similarity matrix, PCA 2D projection, and red flags

Key output fields:
- `features` per document: sentence length, clause complexity, function-word densities, punctuation fingerprints, self-reference density
- `similarity_matrix`: pairwise cosine similarity across the entire corpus
- `pca_projection`: 2D coordinates for visual clustering (requires `numpy`)
- `red_flags`: style-break alerts, student-style overlap, dual-personality detection

**Typical workflow**:
1. Select 5-10 baseline papers by the scholar (`scholar` label).
2. Select 1-3 target papers to test (`target` label).
3. Optionally add suspected ghostwriter papers (`student` label).
4. Run the script; inspect similarity matrix and PCA coordinates; interpret with human judgment.

---

## Dependencies

`text_profiler.py` and `stylometry_profiler.py` (for PDF inputs) require external libraries for text extraction. They will try backends in this order:

1. `pdfplumber` (recommended for Chinese academic PDFs)
2. `PyMuPDF` (fitz, fast and reliable)
3. `PyPDF2` (fallback, usually pre-installed)

Install the preferred backend if you work with PDFs:

```bash
pip install pdfplumber
# or
pip install PyMuPDF
```

For `.md` and `.txt` inputs, no extra dependencies are required.

`stylometry_profiler.py` optionally uses `numpy` for PCA projection. If `numpy` is not installed, it will skip PCA and still output the similarity matrix and feature vectors.

`citation_profiler.py` uses only the Python standard library.

---

## Workflow Diagram

```
┌─────────────────┐
│  Manual search  │  ← Human: CNKI, Wanfang, official sites
│  & PDF download │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ text_profiler.py│  ← Script: parse PDFs / read Markdown & text → JSON profiles
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│paper_quality_rubric.py  │  ← Script: peer-review-aligned ratings
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│   hybrid_scorer.py      │  ← Script + LLM: batch review pack → ranked scores
│   (prepare → apply)     │
└────────┬────────────────┘
         │
         ▼
┌─────────────────┐
│  LLM-assisted   │  ← Human + LLM: assemble scholar_data.json
│  data assembly  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│data_validator.py│  ← Script: validate schema & logic
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│  scholar_data_builder   │  ← Script: unify config + script outputs
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  report_prompt_optimizer│  ← Script: adapt prompt for target LLM
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│     LLM + prompt        │  ← LLM: generate final Markdown report
└─────────────────────────┘
```

---

## Design Decisions

- **No black-box database crawlers**: Paywalled academic databases require manual login and export. This avoids legal risk and institutional IP dependency.
- **Graceful degradation**: `text_profiler.py` tries multiple PDF backends. `data_validator.py` surfaces missing data instead of fabricating it.
- **Evidence chain**: Every JSON output links back to original PDF filenames and manually verified source paths.
- **LLM-First for qualitative work**: Term interpretation, anomaly explanation, and balanced conclusions are delegated to the LLM. Scripts only do what they do best: counting, parsing, and validating structure.
