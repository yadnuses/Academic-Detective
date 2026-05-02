#!/usr/bin/env python3
"""
Tests for db.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.db import InvestigationDB


class TestInvestigationDB:
    def test_init_schema(self, temp_case_dir):
        db = InvestigationDB(temp_case_dir)
        db.init_schema()
        assert (temp_case_dir / "case.db").exists()

    def test_insert_and_get_scholar(self, temp_case_dir):
        db = InvestigationDB(temp_case_dir)
        db.init_schema()
        sid = db.insert_scholar({
            "case_name": "test_case",
            "name": "张三",
            "institution": "北京大学",
            "current_title": "教授",
        })
        assert sid > 0
        scholar = db.get_scholar(sid)
        assert scholar["name"] == "张三"
        assert scholar["institution"] == "北京大学"

    def test_upsert_investigation(self, temp_case_dir):
        db = InvestigationDB(temp_case_dir)
        db.init_schema()
        db.upsert_investigation({
            "case_name": "test_case",
            "status": "init",
            "current_step": "collect",
        })
        inv = db.get_investigation("test_case")
        assert inv["status"] == "init"
        assert inv["current_step"] == "collect"

    def test_insert_paper(self, temp_case_dir):
        db = InvestigationDB(temp_case_dir)
        db.init_schema()
        sid = db.insert_scholar({"case_name": "test", "name": "张三"})
        pid = db.insert_paper(sid, {
            "title": "测试论文",
            "authors": ["张三"],
            "journal": "经济研究",
            "year": 2023,
            "source_db": "cnki",
        })
        assert pid > 0
        papers = db.get_papers(sid)
        assert len(papers) == 1
        assert papers[0]["title"] == "测试论文"

    def test_paper_deduplication(self, temp_case_dir):
        db = InvestigationDB(temp_case_dir)
        db.init_schema()
        sid = db.insert_scholar({"case_name": "test", "name": "张三"})
        db.insert_paper(sid, {"title": "测试论文", "year": 2023, "source_db": "cnki"})
        assert db.paper_exists(sid, "测试论文", 2023) is True
        assert db.paper_exists(sid, "不存在", 2023) is False

    def test_import_scholar_data(self, temp_case_dir, valid_scholar):
        db = InvestigationDB(temp_case_dir)
        db.init_schema()
        sid = db.import_scholar_data(valid_scholar)
        assert sid > 0
        scholar = db.get_scholar(sid)
        assert scholar["name"] == "张三"
        papers = db.get_papers(sid)
        assert len(papers) == 2
        anomalies = db.get_anomalies(sid)
        assert len(anomalies) == 1

    def test_stats(self, temp_case_dir, valid_scholar):
        db = InvestigationDB(temp_case_dir)
        db.init_schema()
        db.import_scholar_data(valid_scholar)
        stats = db.get_stats()
        assert stats["scholars"] == 1
        assert stats["papers"] == 2
        assert stats["anomalies"] == 1
