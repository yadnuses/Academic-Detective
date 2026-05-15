#!/usr/bin/env python3
"""
Flatten export script.
Copies all working engines into a flat directory and rewrites imports.
"""

import os
import shutil
import re
from pathlib import Path

SRC = Path(os.environ.get("ACADEMIC_DETECTIVE_SRC", "./scripts"))
DST = Path(os.environ.get("ACADEMIC_DETECTIVE_DST", "./academic-investigation-engine"))

# Mapping: (source_path, dest_name)
FILES = [
    # Core
    ("core/utils.py", "core_utils.py"),
    ("core/db.py", "core_db.py"),
    ("core/case_manager.py", "core_case_manager.py"),
    ("core/router.py", "core_router.py"),
    ("core/config_loader.py", "core_config_loader.py"),
    ("core/watermark.py", "core_watermark.py"),
    ("core/recommendation_engine.py", "core_recommendation_engine.py"),

    # CLI
    ("investigate.py", "investigate.py"),

    # Domestic
    ("domestic/data_importer.py", "domestic_data_importer.py"),
    ("domestic/data_validator.py", "domestic_data_validator.py"),
    ("domestic/scholar_data_builder.py", "domestic_scholar_data_builder.py"),
    ("domestic/review_matcher.py", "domestic_review_matcher.py"),
    ("domestic/wechat_search.py", "domestic_wechat_search.py"),
    ("domestic/openalex_enricher.py", "domestic_openalex_enricher.py"),

    # International
    ("international/data_fetcher.py", "international_data_fetcher.py"),
    ("international/data_validator.py", "international_data_validator.py"),
    ("international/scholar_data_builder.py", "international_scholar_data_builder.py"),
    ("international/evaluator.py", "international_evaluator.py"),
    ("international/heuristics_classifier.py", "international_heuristics_classifier.py"),
    ("international/missing_reporter.py", "international_missing_reporter.py"),
    ("international/xiaohongshu_client.py", "international_xiaohongshu_client.py"),

    # Analysis
    ("analysis/text_profiler.py", "analysis_text_profiler.py"),
    ("analysis/hybrid_scorer.py", "analysis_hybrid_scorer.py"),
    ("analysis/paper_quality_rubric.py", "analysis_paper_quality_rubric.py"),
    ("analysis/stylometry_profiler.py", "analysis_stylometry_profiler.py"),
    ("analysis/citation_profiler.py", "analysis_citation_profiler.py"),
    ("analysis/common_heuristics.py", "analysis_common_heuristics.py"),
    ("analysis/review_aggregator.py", "analysis_review_aggregator.py"),
    ("analysis/source_evaluation.py", "analysis_source_evaluation.py"),
    ("analysis/journal_credibility_checker.py", "analysis_journal_credibility_checker.py"),

    # Network
    ("network/network_visualizer.py", "network_network_visualizer.py"),
    ("network/timeline_weaver.py", "network_timeline_weaver.py"),
    ("network/grant_linker.py", "network_grant_linker.py"),
    ("network/negative_space_analyzer.py", "network_negative_space_analyzer.py"),
    ("network/investigation_retrospector.py", "network_investigation_retrospector.py"),

    # Cross-border
    ("cross_border/merger.py", "cross_border_merger.py"),
    ("cross_border/validator.py", "cross_border_validator.py"),

    # Deep evidence
    ("deep_evidence/publication_trace/bilingual_publication_detector.py", "deep_bilingual_publication_detector.py"),
    ("deep_evidence/evidence_compiler/evidence_chain_builder.py", "deep_evidence_chain_builder.py"),
    ("deep_evidence/evidence_compiler/signal_aggregator.py", "deep_signal_aggregator.py"),

    # Agents
    ("agents/base.py", "agents_base.py"),
    ("agents/orchestrator.py", "agents_orchestrator.py"),
]

# Configs, schemas, templates
STATIC_FILES = [
    ("config.template.yaml", "config.template.yaml"),
    ("schema/scholar_data.schema.json", "schema_scholar_data.json"),
    ("schema/international_scholar.schema.json", "schema_international_scholar.json"),
    ("schema/corruption_network.schema.json", "schema_corruption_network.json"),
    ("report/report_template.md", "report_template.md"),
    ("report/international_template.md", "report_international_template.md"),
]

# Import rewrite rules: (pattern, replacement)
# Order matters: more specific first
REWRITE_RULES = [
    # Deep evidence (must come before general rules)
    (r"from deep_evidence\.publication_trace\.bilingual_publication_detector import", "from deep_bilingual_publication_detector import"),
    (r"from deep_evidence\.evidence_compiler\.evidence_chain_builder import", "from deep_evidence_chain_builder import"),
    (r"from deep_evidence\.evidence_compiler\.signal_aggregator import", "from deep_signal_aggregator import"),
    (r"from deep_evidence\.[^ ]+ import", "# from deep_evidence.XXX import"),  # catch-all

    # Agents relative imports
    (r"from base import BaseAgent", "from agents_base import BaseAgent"),
    (r"from \.base import BaseAgent", "from agents_base import BaseAgent"),
    (r"from \.orchestrator import Orchestrator", "from agents_orchestrator import Orchestrator"),
    (r"from \.dududu import Dududu", "# from .dududu import Dududu  # agent not included in flat export"),
    (r"from \.huangmao import Huangmao", "# from .huangmao import Huangmao  # agent not included in flat export"),
    (r"from \.laozhoumo import LaoZhoumo", "# from .laozhoumo import LaoZhoumo  # agent not included in flat export"),
    (r"from \.zhu_xiansheng import ZhuXiansheng", "# from .zhu_xiansheng import ZhuXiansheng  # agent not included in flat export"),
    (r"from \.xiaojinjing import Xiaojinjing", "# from .xiaojinjing import Xiaojinjing  # agent not included in flat export"),
    (r"from \.xiaotangdou import Xiaotangdou", "# from .xiaotangdou import Xiaotangdou  # agent not included in flat export"),

    # Package imports
    (r"from agents\.([^ ]+) import", r"from agents_\1 import"),
    (r"from core\.([^ ]+) import", r"from core_\1 import"),
    (r"from domestic\.([^ ]+) import", r"from domestic_\1 import"),
    (r"from international\.([^ ]+) import", r"from international_\1 import"),
    (r"from analysis\.([^ ]+) import", r"from analysis_\1 import"),
    (r"from network\.([^ ]+) import", r"from network_\1 import"),
    (r"from cross_border\.([^ ]+) import", r"from cross_border_\1 import"),
    (r"from delivery\.([^ ]+) import", r"from delivery_\1 import"),
    (r"from report\.([^ ]+) import", r"# from report_\1 import  # report module not included in flat export"),

    # `from domestic import X as Y` style
    (r"from domestic import data_importer as di", "import domestic_data_importer as di"),
    (r"from domestic import data_validator as dv", "import domestic_data_validator as dv"),
]


def rewrite_imports(content: str) -> str:
    for pattern, replacement in REWRITE_RULES:
        content = re.sub(pattern, replacement, content)
    return content


def main():
    DST.mkdir(parents=True, exist_ok=True)

    # Copy and rewrite Python files
    for src_rel, dst_name in FILES:
        src_path = SRC / src_rel
        dst_path = DST / dst_name
        if not src_path.exists():
            print(f"WARNING: {src_path} not found, skipping")
            continue
        content = src_path.read_text(encoding="utf-8")
        content = rewrite_imports(content)
        dst_path.write_text(content, encoding="utf-8")
        print(f"Copied & rewrote: {src_rel} -> {dst_name}")

    # Copy static files
    for src_rel, dst_name in STATIC_FILES:
        src_path = SRC / src_rel
        dst_path = DST / dst_name
        if not src_path.exists():
            print(f"WARNING: {src_path} not found, skipping")
            continue
        shutil.copy2(src_path, dst_path)
        print(f"Copied: {src_rel} -> {dst_name}")

    # Count files
    all_files = list(DST.iterdir())
    print(f"\nTotal files in {DST}: {len(all_files)}")
    for f in sorted(all_files, key=lambda x: x.name):
        print(f"  {f.name}")


if __name__ == "__main__":
    main()
