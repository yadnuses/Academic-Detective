#!/usr/bin/env python3
"""
text_profiler.py

Academic monograph/dissertation text profiler for semi-automatic investigation.
Converts manually acquired PDFs into structured JSON for downstream LLM analysis.

Usage:
    python text_profiler.py --input ./book.pdf --output ./book_profile.json
    python text_profiler.py --input ./book.pdf --terms ./terms.json --output ./book_profile.json
"""

import json
import re
import sys
import argparse
from pathlib import Path
from collections import Counter


def extract_text(input_path: str) -> str:
    """Extract text from PDF, Markdown, or plain text file."""
    text = ""
    p = Path(input_path)

    # Direct read for text-based formats
    if p.suffix.lower() in {".md", ".txt"}:
        with open(p, "r", encoding="utf-8") as f:
            return f.read()

    # Try pdfplumber first (best for Chinese academic layouts)
    try:
        import pdfplumber
        with pdfplumber.open(input_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        if text.strip():
            return text
    except ImportError:
        pass
    except Exception as e:
        print(f"[WARN] pdfplumber failed: {e}", file=sys.stderr)

    # Try PyMuPDF (fitz) second
    try:
        import fitz
        doc = fitz.open(str(p))
        for page in doc:
            text += page.get_text()
        doc.close()
        if text.strip():
            return text
    except ImportError:
        pass
    except Exception as e:
        print(f"[WARN] PyMuPDF failed: {e}", file=sys.stderr)

    # Try PyPDF2 last
    try:
        import PyPDF2
        with open(str(p), "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        if text.strip():
            return text
    except ImportError:
        pass
    except Exception as e:
        print(f"[WARN] PyPDF2 failed: {e}", file=sys.stderr)

    if not text.strip():
        raise RuntimeError(
            f"Failed to extract text from {input_path}. "
            "Supported formats: .pdf, .md, .txt. "
            "For PDFs, please install one of: pdfplumber, PyMuPDF (fitz), or PyPDF2."
        )
    return text


def load_terms(terms_path: str | None) -> dict:
    """Load custom term categories from JSON file."""
    if terms_path and Path(terms_path).exists():
        with open(terms_path, "r", encoding="utf-8") as f:
            return json.load(f)

    # Default term categories for Chinese humanities/social sciences
    return {
        "political_discourse": [
            "革命", "政治", "斗争", "群众", "党", "社会主义", "马克思主义",
            "阶级", "路线", "方针", "政策", "领导"
        ],
        "academic_discourse": [
            "叙事", "结构", "主题", "人物", "审美", "意境", "语言", "风格",
            "隐喻", "符号", "文本", "话语", "阐释", "批判"
        ],
        "theory_terms": [
            "亚里士多德", "阿尔托", "布莱希特", "彼得·布鲁克", "格洛托夫斯基",
            "尤内斯库", "戈登·克雷", "麦茨", "德勒兹", "本雅明", "鲍德里亚",
            "福柯", "拉康", "阿多诺", "姚斯", "伊瑟尔"
        ],
        "methodology": [
            "实证", "定性", "定量", "田野调查", "访谈", "问卷", "统计分析",
            "比较研究", "文献综述", "案例分析"
        ]
    }


def count_terms(text: str, terms: dict) -> dict:
    """Count occurrences of each term category."""
    results = {}
    for category, word_list in terms.items():
        total = 0
        details = Counter()
        for word in word_list:
            count = text.count(word)
            if count > 0:
                total += count
                details[word] = count
        results[category] = {
            "total": total,
            "details": dict(details.most_common())
        }
    return results


def count_originality_markers(text: str) -> dict:
    """Count expressions indicating original claims."""
    markers = [
        "笔者认为", "本文认为", "我们认为", "作者认为",
        "本文提出", "本文发现", "我们发现", "笔者发现",
        "本文试图", "笔者试图", "笔者的观点是", "本文的观点是",
        "笔者认为", "笔者认为", "我认为", "我发现"
    ]
    counts = Counter()
    for marker in markers:
        counts[marker] = text.count(marker)
    total = sum(counts.values())
    return {
        "total": total,
        "details": {k: v for k, v in counts.most_common() if v > 0}
    }


def extract_references(text: str) -> dict:
    """Heuristically extract reference section."""
    # Common reference headers in Chinese academic books
    patterns = [
        r"参考文献[\s:：]*\n",
        r"参考书目[\s:：]*\n",
        r"主要参考文献[\s:：]*\n",
        r"Reference[s]?[\s:：]*\n",
        r"Bibliography[\s:：]*\n"
    ]

    ref_section = ""
    for pattern in patterns:
        match = re.search(pattern + r"(.+?)(?=\n(第[一二三四五六七八九十0-9]+章|附录|后记|结语|结语))", text, re.DOTALL | re.IGNORECASE)
        if not match:
            # Try simpler: from header to end of text
            match = re.search(pattern + r"(.+)$", text, re.DOTALL | re.IGNORECASE)
        if match:
            ref_section = match.group(1).strip()
            break

    if not ref_section:
        return {
            "found": False,
            "count": 0,
            "foreign_ratio": None,
            "latest_year": None,
            "sample": ""
        }

    lines = [line.strip() for line in ref_section.splitlines() if line.strip()]
    count = len(lines)

    # Estimate foreign ratio by checking for Latin alphabet density
    foreign = 0
    for line in lines[:min(count, 200)]:
        latin_chars = len(re.findall(r"[a-zA-Z]", line))
        if latin_chars > len(line) * 0.3:
            foreign += 1
    foreign_ratio = round(foreign / count, 2) if count > 0 else None

    # Extract years
    years = []
    for line in lines:
        found = re.findall(r"(19\d{2}|20\d{2})", line)
        years.extend([int(y) for y in found])
    latest_year = max(years) if years else None

    return {
        "found": True,
        "count": count,
        "foreign_ratio": foreign_ratio,
        "latest_year": latest_year,
        "sample": "\n".join(lines[:10])
    }


def extract_chapters(text: str) -> list:
    """Heuristically extract chapter/section headings."""
    chapters = []

    # Pattern 1: 第一章 / 第1章 / Chapter 1
    p1 = re.findall(r"^\s*(第[一二三四五六七八九十1234567890]+章[\s:：.、]*.+)$", text, re.MULTILINE)
    chapters.extend(p1)

    # Pattern 2: 一、 / （一） at start of line (likely section headings)
    p2 = re.findall(r"^\s*([一二三四五六七八九十1234567890]+[、\.].+)$", text, re.MULTILINE)
    # Filter out false positives (very short or inline text)
    p2 = [x for x in p2 if len(x.strip()) > 4 and len(x.strip()) < 80]
    chapters.extend(p2[:30])  # Limit to avoid noise

    # Pattern 3: 引论 / 结论 / 绪论 / 结语 (standalone)
    p3 = re.findall(r"^\s*(引论|绪论|结论|结语|后记|附录|序|前言)\s*$", text, re.MULTILINE)
    chapters.extend(p3)

    return list(dict.fromkeys(chapters))[:50]  # deduplicate and limit


def detect_figures_and_tables(text: str) -> dict:
    """Detect figure and table captions/references in academic text."""
    # Chinese patterns: 图1, 图 1, 图一, 表1, 表 1, 表格1
    figure_patterns = [
        r"图\s*\d+",
        r"图\s*[一二三四五六七八九十]+",
        r"Figure\s*\d+",
        r"Fig\.\s*\d+",
    ]
    table_patterns = [
        r"表\s*\d+",
        r"表格\s*\d+",
        r"Table\s*\d+",
    ]

    figures = set()
    tables = set()

    for pattern in figure_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            # Normalize to extract number
            num_match = re.search(r"\d+|[一二三四五六七八九十]+", m)
            if num_match:
                figures.add(num_match.group())

    for pattern in table_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            num_match = re.search(r"\d+|[一二三四五六七八九十]+", m)
            if num_match:
                tables.add(num_match.group())

    return {
        "figure_count": len(figures),
        "table_count": len(tables),
        "has_figures": len(figures) > 0,
        "has_tables": len(tables) > 0,
        "total_visual_elements": len(figures) + len(tables),
    }


def extract_methods_section(text: str) -> dict:
    """Extract the methodology/methods section from academic text."""
    method_headers = [
        r"研究方法[\s:：]*\n",
        r"研究方法[\s:：]*\n",
        r"研究设计[\s:：]*\n",
        r"方法论[\s:：]*\n",
        r"Methodology[\s:：]*\n",
        r"Methods[\s:：]*\n",
        r"研究路径[\s:：]*\n",
        r"技术路线[\s:：]*\n",
    ]

    methods_text = ""
    for pattern in method_headers:
        # Try to extract from header to next major section
        match = re.search(
            pattern + r"(.+?)(?=\n(第[一二三四五六七八九十0-9]+章|结论|结果|讨论|参考文献|Reference|附录|结语))",
            text,
            re.DOTALL | re.IGNORECASE
        )
        if not match:
            # Try simpler: from header to next blank line + header pattern
            match = re.search(pattern + r"(.+?)(?=\n\s*\n\s*[一二三四五六七八九十0-9]+[、\.])", text, re.DOTALL | re.IGNORECASE)
        if not match:
            # Fallback: from header to 5000 chars
            match = re.search(pattern + r"(.{500,5000})", text, re.DOTALL | re.IGNORECASE)
        if match:
            methods_text = match.group(1).strip()
            break

    if not methods_text:
        return {
            "found": False,
            "length": 0,
            "preview": "",
            "has_quantitative_methods": None,
            "has_qualitative_methods": None,
        }

    # Detect method type indicators
    quantitative_markers = ["回归", "统计", "问卷", "计量", "模型", "实证", "定量", "数据", "SPSS", "Stata", "R语言", "Python", "实验", "检验", "p值", "显著性"]
    qualitative_markers = ["访谈", "田野", "案例", "文本分析", "叙事", "话语分析", "民族志", "参与观察", "定性", "质性", "内容分析"]

    has_quant = any(m in methods_text for m in quantitative_markers)
    has_qual = any(m in methods_text for m in qualitative_markers)

    return {
        "found": True,
        "length": len(methods_text),
        "preview": methods_text[:800] + ("..." if len(methods_text) > 800 else ""),
        "has_quantitative_methods": has_quant,
        "has_qualitative_methods": has_qual,
        "method_type": "mixed" if (has_quant and has_qual) else ("quantitative" if has_quant else ("qualitative" if has_qual else "unclear")),
    }


def detect_data_availability_statement(text: str) -> dict:
    """Detect data availability / reproducibility statements."""
    da_headers = [
        r"数据可用性[声明]?",
        r"Data Availability",
        r"Availability of Data",
        r"数据集",
        r"数据共享",
        r"数据获取",
        r"公开数据",
        r"开源数据",
    ]

    found = False
    statement_text = ""
    for pattern in da_headers:
        match = re.search(pattern + r"[\s:：]*(.{50,500})", text, re.IGNORECASE)
        if match:
            found = True
            statement_text = match.group(1).strip()
            break

    # Also check for supplementary material / replication package references
    has_supplementary = bool(re.search(r"补充材料| supplementary | replication | github\.com| zenodo | figshare", text, re.IGNORECASE))

    return {
        "found": found,
        "statement_preview": statement_text[:200] if statement_text else "",
        "has_supplementary_material_reference": has_supplementary,
        "reproducibility_indicators": {
            "mentions_open_data": bool(re.search(r"公开数据|开源|open data|publicly available", text, re.IGNORECASE)),
            "mentions_code": bool(re.search(r"代码|code|github|程序", text, re.IGNORECASE)),
            "mentions_replication": bool(re.search(r"复现|replicat| reproduce", text, re.IGNORECASE)),
        }
    }


def detect_author_contributions(text: str) -> dict:
    """Detect CRediT-style or narrative author contribution statements."""
    credit_headers = [
        r"作者贡献[声明]?",
        r"Author Contributions",
        r"Contributions",
        r"CRediT",
        r"作者分工",
    ]

    found = False
    statement_text = ""
    for pattern in credit_headers:
        # Use DOTALL so . can match newlines within the statement
        match = re.search(pattern + r"[\s:：\n]*(.{50,800})", text, re.IGNORECASE | re.DOTALL)
        if match:
            found = True
            statement_text = match.group(1).strip()
            break

    # Check for specific contribution types
    credit_types = ["Conceptualization", "Methodology", "Formal analysis", "Investigation", "Writing", "Funding", "Supervision", "Data curation", "Visualization"]
    chinese_types = ["构思", "方法", "分析", "调查", "写作", "资助", "指导", "数据", "可视化", "实验", "修改", "审阅"]

    detected_types = []
    for ct in credit_types + chinese_types:
        if ct.lower() in statement_text.lower() or ct in text[:50000]:
            detected_types.append(ct)

    return {
        "found": found,
        "has_formal_credit_statement": found and bool(re.search(r"CRediT|conceptualization|methodology|writing", statement_text, re.IGNORECASE)),
        "statement_preview": statement_text[:300] if statement_text else "",
        "detected_contribution_types": list(set(detected_types))[:10],
    }


def analyze_english_abstract(text: str) -> dict:
    """Extract and analyze English abstract if present."""
    # Try to find English abstract section
    en_patterns = [
        r"Abstract[\s:：]*\n(.{200,3000})\n(?:Keywords|Key words|关键词|Key Words)",
        r"Abstract[\s:：]*(.{200,3000})(?=Keywords|Key words|关键词|引言|Introduction|第[一1]章)",
        r"【Abstract】(.{200,3000})(?=【Keywords】|【关键词】)",
    ]

    abstract_text = ""
    for pattern in en_patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            abstract_text = match.group(1).strip()
            break

    if not abstract_text:
        # Try to find any substantial English paragraph at the beginning
        first_english = re.search(r"^[A-Za-z\s,.;:'\"()-]+.{200,3000}", text, re.MULTILINE)
        if first_english:
            abstract_text = first_english.group(0).strip()

    if not abstract_text or len(abstract_text) < 50:
        return {
            "found": False,
            "length": 0,
            "word_count": 0,
            "has_structure": False,
            "quality_indicators": {},
        }

    words = len(re.findall(r"[a-zA-Z]+", abstract_text))
    sentences = len(re.split(r"[.!?]+", abstract_text))

    # Quality indicators
    has_objective = bool(re.search(r"objective|aim|purpose|goal|study|research|this paper|this article|we", abstract_text[:200], re.IGNORECASE))
    has_methods = bool(re.search(r"method|approach|using|based on|by|through|via", abstract_text, re.IGNORECASE))
    has_results = bool(re.search(r"result|find|show|demonstrate|indicate|reveal", abstract_text, re.IGNORECASE))
    has_conclusion = bool(re.search(r"conclusion|conclude|suggest|imply|therefore|thus", abstract_text, re.IGNORECASE))
    has_keywords = bool(re.search(r"keywords|key words", text[text.find(abstract_text):text.find(abstract_text)+len(abstract_text)+200], re.IGNORECASE))

    # Structure score: how many IMRaD elements are present
    imrad_elements = sum([has_objective, has_methods, has_results, has_conclusion])

    return {
        "found": True,
        "length": len(abstract_text),
        "word_count": words,
        "sentence_count": sentences,
        "avg_sentence_length": round(words / sentences, 1) if sentences else 0,
        "has_structure": imrad_elements >= 3,
        "imrad_score": imrad_elements,
        "has_keywords_section": has_keywords,
        "quality_indicators": {
            "has_objective": has_objective,
            "has_methods": has_methods,
            "has_results": has_results,
            "has_conclusion": has_conclusion,
        },
        "preview": abstract_text[:400] + ("..." if len(abstract_text) > 400 else ""),
    }


def compute_basic_stats(text: str) -> dict:
    """Compute basic text statistics."""
    char_count = len(text)
    # Rough word count: Chinese chars + English words
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    english_words = len(re.findall(r"[a-zA-Z]+", text))
    lines = text.count("\n")
    return {
        "total_characters": char_count,
        "chinese_characters": chinese_chars,
        "english_words": english_words,
        "total_lines": lines,
        "estimated_words": chinese_chars + english_words
    }


def main():
    parser = argparse.ArgumentParser(description="Academic monograph text profiler")
    parser.add_argument("--input", "-i", required=True, help="Path to input PDF, Markdown, or text file")
    parser.add_argument("--output", "-o", required=True, help="Path to output JSON")
    parser.add_argument("--terms", "-t", help="Path to custom terms JSON (optional)")
    parser.add_argument("--save-text", "-s", help="Optional path to save extracted raw text (.txt)")
    args = parser.parse_args()

    print(f"[INFO] Extracting text from: {args.input}")
    text = extract_text(args.input)
    print(f"[INFO] Extracted {len(text)} characters")

    if args.save_text:
        with open(args.save_text, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"[INFO] Raw text saved to: {args.save_text}")

    terms = load_terms(args.terms)

    print("[INFO] Running analysis...")
    profile = {
        "source_file": Path(args.input).name,
        "extraction_timestamp": __import__("datetime").datetime.now().isoformat(),
        "basic_stats": compute_basic_stats(text),
        "term_frequency": count_terms(text, terms),
        "originality_markers": count_originality_markers(text),
        "references": extract_references(text),
        "chapter_structure": extract_chapters(text),
        "visual_elements": detect_figures_and_tables(text),
        "methods_section": extract_methods_section(text),
        "data_availability": detect_data_availability_statement(text),
        "author_contributions": detect_author_contributions(text),
        "english_abstract": analyze_english_abstract(text),
        "text_preview": text[:3000].replace("\n", "\n")
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)

    print(f"[INFO] Profile saved to: {args.output}")
    print(f"[SUMMARY] Source: {profile['source_file']}, Characters: {profile['basic_stats']['total_characters']}, "
          f"Originality markers: {profile['originality_markers']['total']}, "
          f"References found: {profile['references']['count']}, "
          f"Chapters/Sections: {len(profile['chapter_structure'])}, "
          f"Figures/Tables: {profile['visual_elements']['total_visual_elements']}, "
          f"Methods found: {profile['methods_section']['found']}, "
          f"Data avail. statement: {profile['data_availability']['found']}, "
          f"Author contrib. statement: {profile['author_contributions']['found']}, "
          f"English abstract: {profile['english_abstract']['found']}")


if __name__ == "__main__":
    main()
