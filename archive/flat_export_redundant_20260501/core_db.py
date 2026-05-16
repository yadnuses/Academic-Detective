#!/usr/bin/env python3
"""
db.py

SQLite persistence layer for academic investigation cases.
Each case gets its own .db file:  cases/{case_name}/case.db

Usage:
    from db import InvestigationDB

    db = InvestigationDB("./cases/zhangsan")
    db.init_schema()
    scholar_id = db.insert_scholar({
        "case_name": "zhangsan",
        "name": "张三",
        "institution": "北京大学",
        "current_title": "教授"
    })
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.utils import get_logger

logger = get_logger("db")


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
-- Scholars table
CREATE TABLE IF NOT EXISTS scholars (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    case_name   TEXT NOT NULL,
    name        TEXT NOT NULL,
    institution TEXT,
    department  TEXT,
    current_title TEXT,
    academic_title TEXT,
    birth_year  INTEGER,
    gender      TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(case_name, name)
);

-- Papers table (unified, deduplicated)
CREATE TABLE IF NOT EXISTS papers (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    scholar_id   INTEGER REFERENCES scholars(id),
    title        TEXT NOT NULL,
    authors      TEXT,               -- JSON array
    journal      TEXT,
    year         INTEGER,
    doi          TEXT,
    source_db    TEXT,               -- cnki/wanfang/wos
    is_verified  BOOLEAN DEFAULT 0,
    quality_score REAL,
    hybrid_score  REAL,
    excerpt      TEXT,
    pdf_path     TEXT,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Relationships (academic network)
CREATE TABLE IF NOT EXISTS relationships (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    scholar_id    INTEGER REFERENCES scholars(id),
    target_name   TEXT NOT NULL,
    target_type   TEXT,              -- advisor/collaborator/editorial/institution/citer
    relation_type TEXT,              -- advisor_of/collaborates_with/...
    institution   TEXT,
    detail        TEXT,
    weight        INTEGER DEFAULT 1,
    is_anomaly    BOOLEAN DEFAULT 0,
    evidence      TEXT               -- JSON
);

-- Investigations (case metadata)
CREATE TABLE IF NOT EXISTS investigations (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    case_name           TEXT UNIQUE NOT NULL,
    investigation_type  TEXT DEFAULT 'domestic',  -- domestic/international/cross_border
    depth               TEXT,            -- quick/standard/exhaustive
    status              TEXT,            -- init/collect/profile/build/validate/llm/prompt/report/done
    current_step        TEXT,
    started_at          TIMESTAMP,
    completed_at        TIMESTAMP,
    investigator        TEXT,
    notes               TEXT
);

-- Claims vs reality
CREATE TABLE IF NOT EXISTS claims_vs_reality (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scholar_id      INTEGER REFERENCES scholars(id),
    category        TEXT,            -- papers/monographs/projects/awards
    claimed_value   TEXT,
    verified_value  TEXT,
    source          TEXT,
    discrepancy     TEXT,
    severity        TEXT             -- minor/moderate/major/critical
);

-- Timeline events
CREATE TABLE IF NOT EXISTS timeline_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    scholar_id  INTEGER REFERENCES scholars(id),
    event_date  TEXT,
    event_type  TEXT,                -- education/career/publication/award/anomaly
    description TEXT,
    source      TEXT,
    is_anomaly  BOOLEAN DEFAULT 0
);

-- Anomalies
CREATE TABLE IF NOT EXISTS anomalies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    scholar_id  INTEGER REFERENCES scholars(id),
    category    TEXT,                -- S1-S5 or custom
    severity    TEXT,                -- low/medium/high/critical
    description TEXT,
    evidence    TEXT,                -- JSON
    status      TEXT DEFAULT 'open', -- open/verified/false_positive/resolved
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Import log (audit trail)
CREATE TABLE IF NOT EXISTS import_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    case_name   TEXT,
    source_type TEXT,
    source_file TEXT,
    records_imported INTEGER,
    duplicates_removed INTEGER,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indices for common queries
CREATE INDEX IF NOT EXISTS idx_papers_scholar ON papers(scholar_id);
CREATE INDEX IF NOT EXISTS idx_papers_year ON papers(year);
CREATE INDEX IF NOT EXISTS idx_rel_scholar ON relationships(scholar_id);
CREATE INDEX IF NOT EXISTS idx_timeline_scholar ON timeline_events(scholar_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_scholar ON anomalies(scholar_id);
CREATE INDEX IF NOT EXISTS idx_claims_scholar ON claims_vs_reality(scholar_id);
"""


# ---------------------------------------------------------------------------
# DB class
# ---------------------------------------------------------------------------

class InvestigationDB:
    """Per-case SQLite database."""

    def __init__(self, case_dir: Path | str):
        self.case_dir = Path(case_dir).resolve()
        self.db_path = self.case_dir / "case.db"
        self._ensure_dir()

    def _ensure_dir(self):
        self.case_dir.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    # -------------------------------------------------------------------
    # Schema
    # -------------------------------------------------------------------

    def init_schema(self):
        """Create all tables and indices. Migrate existing databases if needed."""
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)
            # Migrate: add investigation_type column if missing (pre-v2 databases)
            try:
                conn.execute("SELECT investigation_type FROM investigations LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute("ALTER TABLE investigations ADD COLUMN investigation_type TEXT DEFAULT 'domestic'")
                logger.info("Migrated database: added investigation_type column")
            conn.commit()
        logger.info("Schema initialized: %s", self.db_path)

    def reset(self):
        """Drop and recreate all tables. DANGEROUS."""
        with self._connect() as conn:
            tables = [
                "scholars", "papers", "relationships", "investigations",
                "claims_vs_reality", "timeline_events", "anomalies", "import_log"
            ]
            for t in tables:
                conn.execute(f"DROP TABLE IF EXISTS {t}")
            conn.commit()
        self.init_schema()
        logger.warning("Database reset: %s", self.db_path)

    # -------------------------------------------------------------------
    # Scholars
    # -------------------------------------------------------------------

    def insert_scholar(self, data: dict) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO scholars (case_name, name, institution, department,
                    current_title, academic_title, birth_year, gender)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(case_name, name) DO UPDATE SET
                    institution=excluded.institution,
                    department=excluded.department,
                    current_title=excluded.current_title,
                    academic_title=excluded.academic_title,
                    birth_year=excluded.birth_year,
                    gender=excluded.gender
                """,
                (
                    data.get("case_name", ""),
                    data.get("name", ""),
                    data.get("institution"),
                    data.get("department"),
                    data.get("current_title"),
                    data.get("academic_title"),
                    data.get("birth_year"),
                    data.get("gender"),
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_scholar(self, scholar_id: int) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM scholars WHERE id=?", (scholar_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_scholar_by_name(self, case_name: str, name: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM scholars WHERE case_name=? AND name=?",
                (case_name, name),
            ).fetchone()
            return dict(row) if row else None

    # -------------------------------------------------------------------
    # Papers
    # -------------------------------------------------------------------

    def insert_paper(self, scholar_id: int, data: dict) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO papers (scholar_id, title, authors, journal, year, doi,
                    source_db, is_verified, quality_score, hybrid_score, excerpt, pdf_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scholar_id,
                    data.get("title", ""),
                    json.dumps(data.get("authors", []), ensure_ascii=False),
                    data.get("journal"),
                    data.get("year"),
                    data.get("doi"),
                    data.get("source_db"),
                    data.get("is_verified", False),
                    data.get("quality_score"),
                    data.get("hybrid_score"),
                    data.get("excerpt"),
                    data.get("pdf_path"),
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_papers(self, scholar_id: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM papers WHERE scholar_id=? ORDER BY year DESC",
                (scholar_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def paper_exists(self, scholar_id: int, title: str, year: int) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM papers WHERE scholar_id=? AND title=? AND year=?",
                (scholar_id, title, year),
            ).fetchone()
            return bool(row)

    # -------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------

    def insert_relationship(self, scholar_id: int, data: dict) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO relationships (scholar_id, target_name, target_type,
                    relation_type, institution, detail, weight, is_anomaly, evidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scholar_id,
                    data.get("target_name", ""),
                    data.get("target_type"),
                    data.get("relation_type"),
                    data.get("institution"),
                    data.get("detail"),
                    data.get("weight", 1),
                    data.get("is_anomaly", False),
                    json.dumps(data.get("evidence", {}), ensure_ascii=False),
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_relationships(self, scholar_id: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM relationships WHERE scholar_id=?",
                (scholar_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # -------------------------------------------------------------------
    # Investigations (case metadata)
    # -------------------------------------------------------------------

    def upsert_investigation(self, data: dict) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO investigations (case_name, investigation_type, depth, status, current_step,
                    started_at, completed_at, investigator, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(case_name) DO UPDATE SET
                    investigation_type=excluded.investigation_type,
                    depth=excluded.depth,
                    status=excluded.status,
                    current_step=excluded.current_step,
                    started_at=excluded.started_at,
                    completed_at=excluded.completed_at,
                    investigator=excluded.investigator,
                    notes=excluded.notes
                """,
                (
                    data.get("case_name", ""),
                    data.get("investigation_type", "domestic"),
                    data.get("depth"),
                    data.get("status"),
                    data.get("current_step"),
                    data.get("started_at"),
                    data.get("completed_at"),
                    data.get("investigator"),
                    data.get("notes"),
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_investigation(self, case_name: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM investigations WHERE case_name=?",
                (case_name,),
            ).fetchone()
            return dict(row) if row else None

    # -------------------------------------------------------------------
    # Claims vs reality
    # -------------------------------------------------------------------

    def insert_claim(self, scholar_id: int, data: dict) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO claims_vs_reality (scholar_id, category, claimed_value,
                    verified_value, source, discrepancy, severity)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scholar_id,
                    data.get("category", ""),
                    data.get("claimed_value"),
                    data.get("verified_value"),
                    data.get("source"),
                    data.get("discrepancy"),
                    data.get("severity"),
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_claims(self, scholar_id: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM claims_vs_reality WHERE scholar_id=?",
                (scholar_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # -------------------------------------------------------------------
    # Timeline events
    # -------------------------------------------------------------------

    def insert_timeline_event(self, scholar_id: int, data: dict) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO timeline_events (scholar_id, event_date, event_type,
                    description, source, is_anomaly)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    scholar_id,
                    data.get("event_date"),
                    data.get("event_type", ""),
                    data.get("description", ""),
                    data.get("source"),
                    data.get("is_anomaly", False),
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_timeline(self, scholar_id: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM timeline_events WHERE scholar_id=? ORDER BY event_date",
                (scholar_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # -------------------------------------------------------------------
    # Anomalies
    # -------------------------------------------------------------------

    def insert_anomaly(self, scholar_id: int, data: dict) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO anomalies (scholar_id, category, severity, description,
                    evidence, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    scholar_id,
                    data.get("category", ""),
                    data.get("severity", "medium"),
                    data.get("description", ""),
                    json.dumps(data.get("evidence", {}), ensure_ascii=False),
                    data.get("status", "open"),
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_anomalies(self, scholar_id: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM anomalies WHERE scholar_id=? ORDER BY created_at DESC",
                (scholar_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # -------------------------------------------------------------------
    # Import log
    # -------------------------------------------------------------------

    def log_import(self, case_name: str, source_type: str, source_file: str,
                   records_imported: int, duplicates_removed: int = 0):
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO import_log (case_name, source_type, source_file,
                    records_imported, duplicates_removed)
                VALUES (?, ?, ?, ?, ?)
                """,
                (case_name, source_type, source_file, records_imported, duplicates_removed),
            )
            conn.commit()

    # -------------------------------------------------------------------
    # Bulk import from JSON
    # -------------------------------------------------------------------

    def import_scholar_data(self, data: dict) -> int:
        """
        Import a scholar_data.json into SQLite.
        Returns the scholar_id.
        """
        case_name = data.get("case_name", "default")
        name = data.get("name", "")

        # Upsert scholar
        scholar_id = self.insert_scholar({
            "case_name": case_name,
            "name": name,
            "institution": data.get("institution"),
            "current_title": data.get("basic_profile", {}).get("current_title"),
        })

        # Import papers
        verified_papers = data.get("academic_outputs", {}).get("verified_papers", [])
        papers = verified_papers if isinstance(verified_papers, list) else []
        for p in papers:
            if not self.paper_exists(scholar_id, p.get("title", ""), p.get("year", 0)):
                self.insert_paper(scholar_id, p)

        # Import anomalies
        for a in data.get("anomalies", []):
            self.insert_anomaly(scholar_id, {
                "category": a.get("category", "custom"),
                "severity": a.get("severity", "medium"),
                "description": a.get("description", ""),
                "evidence": a.get("evidence", {}),
            })

        # Import claims vs reality
        claims = data.get("claims_vs_reality", {})
        for category, vals in claims.items():
            self.insert_claim(scholar_id, {
                "category": category,
                "claimed_value": vals.get("claimed"),
                "verified_value": vals.get("verified"),
                "discrepancy": vals.get("discrepancy"),
                "severity": vals.get("severity", "minor"),
            })

        logger.info("Imported scholar_data for '%s': scholar_id=%d", name, scholar_id)
        return scholar_id

    # -------------------------------------------------------------------
    # Cross-case queries
    # -------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return basic stats for the case."""
        with self._connect() as conn:
            scholars = conn.execute("SELECT COUNT(*) FROM scholars").fetchone()[0]
            papers = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
            anomalies = conn.execute("SELECT COUNT(*) FROM anomalies").fetchone()[0]
            relationships = conn.execute("SELECT COUNT(*) FROM relationships").fetchone()[0]
            return {
                "scholars": scholars,
                "papers": papers,
                "anomalies": anomalies,
                "relationships": relationships,
            }

    def get_anomalies_by_severity(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT a.*, s.name as scholar_name
                FROM anomalies a
                JOIN scholars s ON a.scholar_id = s.id
                ORDER BY CASE a.severity
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                    ELSE 5
                END, a.created_at DESC
                """
            ).fetchall()
            return [dict(r) for r in rows]
