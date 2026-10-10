#!/usr/bin/env python3
"""
citation_verifier — Citation extraction and verification module.

Academic-Detective is operated by an LLM agent.  The verification workflow:

  1. Extract citations from a document  (parser → JSON)
  2. Operating LLM verifies each citation using web search + reasoning
  3. Generate structured report          (reporter → JSON/CSV)

Usage:
    from analysis.citation_verifier import extract_citations, build_task, merge_results, save_report

    citations = extract_citations("paper.docx")
    task = build_task(citations, "task.json")
    # ... LLM fills in verification fields ...
    results = merge_results(task)
    save_report(results, "report.json")
"""

from analysis.citation_verifier.parser import extract_from_docx, extract_from_tex
from analysis.citation_verifier.verifier import build_task, merge_results
from analysis.citation_verifier.reporter import save_report, generate_summary


def extract_citations(file_path: str, bib_path: str = None) -> list:
    """Extract citations from a document.

    Args:
        file_path: Path to .docx or .tex file.
        bib_path: Path to .bib file (required for .tex, ignored for .docx).

    Returns:
        List of citation dicts with keys: key, ref_text, usages, context_block.
    """
    from pathlib import Path

    p = Path(file_path)
    ext = p.suffix.lower()

    if ext == ".docx":
        return extract_from_docx(file_path)
    elif ext == ".tex":
        if not bib_path:
            raise ValueError("--bib is required when processing .tex files")
        return extract_from_tex([file_path], bib_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}. Use .docx or .tex")


__all__ = [
    "extract_citations",
    "extract_from_docx",
    "extract_from_tex",
    "build_task",
    "merge_results",
    "save_report",
    "generate_summary",
]
