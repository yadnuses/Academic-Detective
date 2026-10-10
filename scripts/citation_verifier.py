#!/usr/bin/env python3
"""
citation_verifier.py — CLI entry point for citation extraction and report generation.

Academic-Detective is operated by an LLM agent.  The verification workflow:

  Step 1  LLM runs this script with --extract-only to get a task JSON
  Step 2  LLM fills in verification fields for each citation
  Step 3  LLM runs this script with --report to generate the final report

Usage:
    # Extract citations (LLM does this first)
    python citation_verifier.py -i paper.docx -o task.json --extract-only

    # Generate report from filled task (LLM does this after verifying)
    python citation_verifier.py --report task.json -o report.json

    # Extract and produce empty task template (same as --extract-only)
    python citation_verifier.py -i paper.docx -o task.json
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure scripts/ is on the path so relative imports work
sys.path.insert(0, str(Path(__file__).resolve().parent))

from analysis.citation_verifier.parser import extract_from_docx, extract_from_tex
from analysis.citation_verifier.verifier import build_task, merge_results
from analysis.citation_verifier.reporter import save_report, generate_summary


def main():
    parser = argparse.ArgumentParser(
        description="Citation extraction and verification for academic documents"
    )
    parser.add_argument(
        "--input", "-i",
        help="Path to .docx or .tex file (for extraction)",
    )
    parser.add_argument(
        "--bib", "-b",
        help="Path to .bib file (required for .tex input)",
    )
    parser.add_argument(
        "--output", "-o", required=True,
        help="Path to output file",
    )
    parser.add_argument(
        "--extract-only", action="store_true",
        help="Only extract citations, output task template (no verification)",
    )
    parser.add_argument(
        "--report",
        help="Generate report from a filled verification task JSON",
    )
    args = parser.parse_args()

    # Mode 1: Generate report from filled task
    if args.report:
        task_path = Path(args.report)
        if not task_path.exists():
            print(f"[ERROR] Task file not found: {args.report}", file=sys.stderr)
            sys.exit(1)
        with open(task_path, "r", encoding="utf-8") as f:
            task = json.load(f)
        results = merge_results(task)
        report = save_report(results, args.output)
        summary_text = generate_summary(results)
        print(summary_text)
        print(f"\n[INFO] Report saved to: {args.output}")
        return

    # Mode 2: Extract citations
    if not args.input:
        print("[ERROR] --input is required for extraction", file=sys.stderr)
        sys.exit(1)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERROR] Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    ext = input_path.suffix.lower()
    print(f"[INFO] Extracting citations from: {input_path}")

    if ext == ".docx":
        citations = extract_from_docx(str(input_path))
    elif ext == ".tex":
        if not args.bib:
            print("[ERROR] --bib is required for .tex files", file=sys.stderr)
            sys.exit(1)
        bib_path = Path(args.bib)
        if not bib_path.exists():
            print(f"[ERROR] Bib file not found: {args.bib}", file=sys.stderr)
            sys.exit(1)
        citations = extract_from_tex([str(input_path)], str(bib_path))
    else:
        print(f"[ERROR] Unsupported file type: {ext}", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] Found {len(citations)} unique citations")
    if not citations:
        print("[WARN] No citations found. Check if the document has a reference list.")
        sys.exit(0)

    # Build and save task template
    task = build_task(citations, args.output)
    print(f"[INFO] Verification task saved to: {args.output}")
    print(f"[INFO] Next: fill in 'verification' fields for each citation, then run:")
    print(f"       python {Path(__file__).name} --report {args.output} -o report.json")

    # Print citation summary
    print(f"\nCitations extracted:")
    for cit in citations:
        print(f"  [{cit['key']}] {cit['ref_text'][:80]}... (used {cit['usage_count']}x)")


if __name__ == "__main__":
    main()
