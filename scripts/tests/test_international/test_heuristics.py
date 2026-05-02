#!/usr/bin/env python3
"""Tests for international/heuristics_classifier.py"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from international.heuristics_classifier import InternationalHeuristicsClassifier, PREDATORY_PUBLISHERS


class TestClassifyPredatoryJournal:
    def test_flags_predatory_publisher(self):
        classifier = InternationalHeuristicsClassifier()
        papers = [
            {"title": "Paper 1", "journal": "Frontiers in Psychology", "year": 2023},
            {"title": "Paper 2", "journal": "MDPI Sensors", "year": 2022},
            {"title": "Paper 3", "journal": "Hindawi Complexity", "year": 2023},
            {"title": "Paper 4", "journal": "Nature", "year": 2021},
        ]
        flags = classifier.classify_predatory_journal(papers)
        assert len(flags) > 0
        assert flags[0]["rule_id"] == "I01"
        assert "掠夺性" in flags[0]["rule_name"]

    def test_suspicious_journal_name_pattern(self):
        classifier = InternationalHeuristicsClassifier()
        papers = [
            {"title": "P1", "journal": "International Journal of Advanced Research", "year": 2023},
            {"title": "P2", "journal": "Open Journal of Computer Science", "year": 2023},
            {"title": "P3", "journal": "Advances in Nanotechnology and Biotechnology Research", "year": 2022},
        ]
        flags = classifier.classify_predatory_journal(papers)
        assert len(flags) > 0

    def test_no_flags_for_clean_papers(self):
        classifier = InternationalHeuristicsClassifier()
        papers = [
            {"title": "P1", "journal": "Nature", "year": 2023},
            {"title": "P2", "journal": "Science", "year": 2022},
        ]
        flags = classifier.classify_predatory_journal(papers)
        assert len(flags) == 0

    def test_low_severity_for_few_papers(self):
        classifier = InternationalHeuristicsClassifier()
        papers = [
            {"title": "P1", "journal": "Frontiers in X", "year": 2023},
        ]
        flags = classifier.classify_predatory_journal(papers)
        assert len(flags) == 1
        assert flags[0]["severity"] == "low"

    def test_medium_severity_for_many_papers(self):
        classifier = InternationalHeuristicsClassifier()
        papers = [
            {"title": f"P{i}", "journal": "Frontiers in Something", "year": 2023}
            for i in range(5)
        ]
        flags = classifier.classify_predatory_journal(papers)
        assert len(flags) == 1
        assert flags[0]["severity"] == "medium"


class TestClassifyPaperMill:
    def test_flags_template_titles(self):
        classifier = InternationalHeuristicsClassifier()
        papers = [
            {"title": "Machine Learning for Cancer Detection in Medical Images", "authors": ["A", "B"], "year": 2020},
            {"title": "Deep Learning for Heart Disease Prediction in Clinical Data", "authors": ["A", "B"], "year": 2020},
            {"title": "Reinforcement Learning for Diabetes Monitoring in Hospitals", "authors": ["A", "B"], "year": 2020},
            {"title": "Transfer Learning for Alzheimer Classification in Brain Scans", "authors": ["A", "B"], "year": 2020},
            {"title": "Federated Learning for Parkinson Detection in Wearable Data", "authors": ["A", "B"], "year": 2020},
            {"title": "Contrastive Learning for Stroke Prediction in Patient Records", "authors": ["A", "B"], "year": 2020},
        ]
        flags = classifier.classify_paper_mill(papers)
        assert len(flags) > 0
        assert flags[0]["rule_id"] == "I02"

    def test_flags_rapid_publication(self):
        classifier = InternationalHeuristicsClassifier()
        papers = [{"title": f"P{i}", "authors": ["A"], "year": 2023} for i in range(10)]
        flags = classifier.classify_paper_mill(papers)
        assert len(flags) > 0

    def test_no_flags_for_normal_output(self):
        classifier = InternationalHeuristicsClassifier()
        papers = [
            {"title": "Unique Title One", "authors": ["A", "B"], "year": 2020},
            {"title": "Completely Different Two", "authors": ["A", "C"], "year": 2021},
            {"title": "Another Approach Three", "authors": ["B", "D"], "year": 2022},
        ]
        flags = classifier.classify_paper_mill(papers)
        assert len(flags) == 0

    def test_insufficient_papers(self):
        classifier = InternationalHeuristicsClassifier()
        papers = [
            {"title": "P1", "authors": ["A"], "year": 2020},
            {"title": "P2", "authors": ["A"], "year": 2020},
        ]
        flags = classifier.classify_paper_mill(papers)
        assert len(flags) == 0


class TestClassifyCitationCartel:
    def test_high_self_citation(self):
        classifier = InternationalHeuristicsClassifier()
        papers = []
        author_data = {"self_citation_ratio": 0.35}
        flags = classifier.classify_citation_cartel(papers, author_data)
        assert len(flags) == 1
        assert flags[0]["rule_id"] == "I04"
        assert "引用" in flags[0]["rule_name"]

    def test_normal_self_citation(self):
        classifier = InternationalHeuristicsClassifier()
        author_data = {"self_citation_ratio": 0.10}
        flags = classifier.classify_citation_cartel([], author_data)
        assert len(flags) == 0

    def test_no_author_data(self):
        classifier = InternationalHeuristicsClassifier()
        flags = classifier.classify_citation_cartel([], None)
        assert len(flags) == 0


class TestClassifyGhostAuthorship:
    def test_long_author_lists(self):
        classifier = InternationalHeuristicsClassifier()
        papers = [
            {"title": "P1", "authors": [f"A{i}" for i in range(25)]},
            {"title": "P2", "authors": [f"B{i}" for i in range(30)]},
            {"title": "P3", "authors": [f"C{i}" for i in range(22)]},
        ]
        flags = classifier.classify_ghost_authorship(papers)
        assert len(flags) == 1
        assert flags[0]["rule_id"] == "I06"

    def test_no_flags_for_short_lists(self):
        classifier = InternationalHeuristicsClassifier()
        papers = [
            {"title": "P1", "authors": ["A", "B", "C"]},
            {"title": "P2", "authors": ["A", "D"]},
        ]
        flags = classifier.classify_ghost_authorship(papers)
        assert len(flags) == 0


class TestClassifyRapidPublication:
    def test_rapid_monthly_publication(self):
        classifier = InternationalHeuristicsClassifier()
        papers = [
            {"title": f"P{i}", "publication_date": "2023-06-15"}
            for i in range(6)
        ]
        flags = classifier.classify_rapid_publication(papers)
        assert len(flags) == 1
        assert flags[0]["rule_id"] == "I07"

    def test_normal_monthly_publication(self):
        classifier = InternationalHeuristicsClassifier()
        papers = [
            {"title": f"P{i}", "publication_date": f"2023-{i+1:02d}-15"}
            for i in range(5)
        ]
        flags = classifier.classify_rapid_publication(papers)
        assert len(flags) == 0


class TestMainClassify:
    def test_full_classification(self):
        classifier = InternationalHeuristicsClassifier()
        papers = [
            {"title": "Frontiers Paper", "journal": "Frontiers in AI", "year": 2023,
             "authors": ["A", "B"], "publication_date": "2023-06-15"},
            {"title": "Another Frontiers", "journal": "Frontiers in AI", "year": 2023,
             "authors": ["A", "B"], "publication_date": "2023-06-20"},
            {"title": "Third Frontiers", "journal": "Frontiers in AI", "year": 2023,
             "authors": ["A", "B"], "publication_date": "2023-06-25"},
        ]
        author_data = {"self_citation_ratio": 0.40}
        flags = classifier.classify(papers, author_data)
        rule_ids = [f["rule_id"] for f in flags]
        assert "I01" in rule_ids or "I07" in rule_ids or "I04" in rule_ids
