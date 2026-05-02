#!/usr/bin/env python3
"""Tests for international/data_fetcher.py

All external HTTP calls are mocked to avoid network dependency.
"""

import json
import sys
import urllib.request
from io import BytesIO
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from international.data_fetcher import (
    fetch_openalex,
    fetch_orcid,
    fetch_semantic_scholar,
    fetch_pubpeer,
    fetch_arxiv,
    fetch_retraction_watch,
    fetch_google_scholar,
    UnifiedFetcher,
    _rate_limit,
    _http_get_json,
)


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _mock_json_response(data: dict):
    """Create a mock urllib response that returns JSON."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(data).encode("utf-8")
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = lambda s, *a: None
    return mock_resp


# ---------------------------------------------------------------------------
# OpenAlex
# ---------------------------------------------------------------------------

class TestFetchOpenalex:
    @patch("international.data_fetcher.urllib.request.urlopen")
    def test_fetch_with_results(self, mock_urlopen):
        mock_urlopen.return_value = _mock_json_response({
            "results": [
                {
                    "id": "A1",
                    "display_name": "Test Author",
                    "orcid": "0000-0001-0000-0001",
                    "works_count": 42,
                    "cited_by_count": 1000,
                    "h_index": 20,
                    "i10_index": 35,
                }
            ]
        })
        result = fetch_openalex("Test Author", "MIT")
        assert result["author"]["display_name"] == "Test Author"
        assert result["author"]["works_count"] == 42

    @patch("international.data_fetcher.urllib.request.urlopen")
    def test_fetch_no_results(self, mock_urlopen):
        mock_urlopen.return_value = _mock_json_response({"results": []})
        result = fetch_openalex("Unknown Person")
        assert result["author"] is None
        assert result["works"] == []

    @patch("international.data_fetcher.urllib.request.urlopen")
    def test_fetch_works(self, mock_urlopen):
        # First call: author search, second: works
        mock_urlopen.side_effect = [
            _mock_json_response({
                "results": [{"id": "A1", "display_name": "Author", "works_api_url": "http://x"}]
            }),
            _mock_json_response({
                "results": [
                    {"id": "W1", "display_name": "Paper 1", "publication_year": 2023}
                ]
            }),
        ]
        result = fetch_openalex("Author")
        assert len(result["works"]) == 1
        assert result["works"][0]["title"] == "Paper 1"


# ---------------------------------------------------------------------------
# ORCID
# ---------------------------------------------------------------------------

class TestFetchOrcid:
    @patch("international.data_fetcher.urllib.request.urlopen")
    def test_fetch_orcid_profile(self, mock_urlopen):
        mock_urlopen.return_value = _mock_json_response({
            "person": {
                "name": {"given-names": {"value": "John"}, "family-name": {"value": "Doe"}},
            },
            "activities-summary": {
                "employments": {
                    "affiliation-group": [
                        {
                            "summaries": [
                                {"employment-summary": {"organization": {"name": "MIT"}, "role-title": "Professor"}}
                            ]
                        }
                    ]
                }
            },
        })
        result = fetch_orcid("0000-0001-0000-0001")
        assert result["name"] == "John Doe"
        assert result["employment"][0]["institution"] == "MIT"


# ---------------------------------------------------------------------------
# Semantic Scholar
# ---------------------------------------------------------------------------

class TestFetchSemanticScholar:
    @patch("international.data_fetcher.urllib.request.urlopen")
    def test_fetch_author(self, mock_urlopen):
        mock_urlopen.return_value = _mock_json_response({
            "data": [
                {
                    "authorId": "S1",
                    "name": "Test Author",
                    "paperCount": 50,
                    "citationCount": 2000,
                    "hIndex": 25,
                }
            ]
        })
        result = fetch_semantic_scholar("Test Author")
        assert result["author"]["name"] == "Test Author"
        assert result["author"]["h_index"] == 25

    @patch("international.data_fetcher.urllib.request.urlopen")
    def test_fetch_papers(self, mock_urlopen):
        mock_urlopen.side_effect = [
            _mock_json_response({
                "data": [{"authorId": "S1", "name": "Author", "papers": [{"paperId": "P1"}]}]
            }),
            _mock_json_response({
                "data": [{"paperId": "P1", "title": "Paper 1", "year": 2023}]
            }),
        ]
        result = fetch_semantic_scholar("Author")
        assert len(result["papers"]) == 1
        assert result["papers"][0]["title"] == "Paper 1"


# ---------------------------------------------------------------------------
# PubPeer
# ---------------------------------------------------------------------------

class TestFetchPubpeer:
    @patch("international.data_fetcher.urllib.request.urlopen")
    def test_fetch_comments(self, mock_urlopen):
        mock_urlopen.return_value = _mock_json_response({
            "feeds": [
                {"publication": {"id": "P1", "title": "Paper with issues"}, "comments": [{"content": "concern"}]}
            ]
        })
        result = fetch_pubpeer("Author")
        assert result["total_comments"] == 1
        assert "papers_with_comments" in result

    @patch("international.data_fetcher.urllib.request.urlopen")
    def test_empty_result(self, mock_urlopen):
        mock_urlopen.return_value = _mock_json_response({"feeds": []})
        result = fetch_pubpeer("Unknown")
        assert result["total_comments"] == 0


# ---------------------------------------------------------------------------
# arXiv
# ---------------------------------------------------------------------------

class TestFetchArxiv:
    def test_fetch_arxiv(self):
        # arXiv uses Atom XML, test with a simple mock
        xml = b'''<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2301.00001</id>
    <title>Paper Title</title>
    <summary>Abstract text</summary>
    <published>2023-01-01T00:00:00Z</published>
    <updated>2023-01-02T00:00:00Z</updated>
    <author><name>John Doe</name></author>
    <arxiv:primary_category term="cs.AI"/>
  </entry>
</feed>'''
        mock_resp = MagicMock()
        mock_resp.read.return_value = xml
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = lambda s, *a: None

        with patch("international.data_fetcher.urllib.request.urlopen", return_value=mock_resp):
            result = fetch_arxiv("John Doe")
            assert len(result["papers"]) == 1
            assert result["papers"][0]["title"] == "Paper Title"


# ---------------------------------------------------------------------------
# Retraction Watch
# ---------------------------------------------------------------------------

class TestFetchRetractionWatch:
    @patch("international.data_fetcher.urllib.request.urlopen")
    def test_fetch(self, mock_urlopen):
        mock_urlopen.return_value = _mock_json_response({
            "data": [{"Title": "Retracted Paper", "Author": "Test"}]
        })
        result = fetch_retraction_watch("Test")
        assert "retracted_papers" in result


# ---------------------------------------------------------------------------
# Google Scholar
# ---------------------------------------------------------------------------

class TestFetchGoogleScholar:
    def test_scholarly_not_installed(self):
        # Google Scholar requires scholarly library; test when not available
        with patch("builtins.__import__", side_effect=lambda name, *a, **k: __import__(name, *a, **k) if name != "scholarly" else (_ for _ in ()).throw(ImportError("No module named scholarly"))):
            result = fetch_google_scholar("Author")
            assert result["h_index"] == 0
            assert result["publications"] == []


# ---------------------------------------------------------------------------
# UnifiedFetcher
# ---------------------------------------------------------------------------

class TestUnifiedFetcher:
    def test_init_default(self):
        f = UnifiedFetcher()
        assert f.config == {}

    def test_init_with_config(self):
        f = UnifiedFetcher({"international_sources": {"openalex": {"enabled": False}}})
        assert f._enabled("openalex") is False

    def test_enabled_defaults_true(self):
        f = UnifiedFetcher()
        assert f._enabled("openalex") is True
        assert f._enabled("semantic_scholar") is True

    def test_normalize_paper_openalex(self):
        f = UnifiedFetcher()
        paper = {
            "title": "Test",
            "publication_year": 2023,
            "authorships": [{"author_name": "A"}],
            "host_venue": {"name": "Nature"},
            "cited_by_count": 10,
            "open_access": {"is_oa": True, "oa_url": "http://pdf"},
        }
        norm = f._normalize_paper(paper, "openalex")
        assert norm["title"] == "Test"
        assert norm["year"] == 2023
        assert norm["journal"] == "Nature"
        assert norm["is_oa"] is True

    def test_normalize_paper_semantic_scholar(self):
        f = UnifiedFetcher()
        paper = {
            "title": "Test",
            "year": 2023,
            "authors": ["A", "B"],
            "journal": "Science",
            "citation_count": 20,
            "abstract": "Abstract",
        }
        norm = f._normalize_paper(paper, "semantic_scholar")
        assert norm["source"] == "semantic_scholar"
        assert norm["authors"] == ["A", "B"]

    def test_normalize_paper_arxiv(self):
        f = UnifiedFetcher()
        paper = {
            "title": "Test",
            "published": "2023-05-01",
            "authors": ["A"],
            "primary_category": "cs.AI",
            "id": "2305.00001",
            "pdf_url": "http://pdf",
            "summary": "Abstract",
        }
        norm = f._normalize_paper(paper, "arxiv")
        assert norm["year"] == 2023
        assert norm["is_oa"] is True
        assert "arXiv" in norm["journal"]

    def test_deduplicate_by_doi(self):
        f = UnifiedFetcher()
        papers = [
            {"doi": "10.1/abc", "title": "T1", "citation_count": 5, "source": "openalex"},
            {"doi": "10.1/abc", "title": "T1", "citation_count": 10, "source": "semantic_scholar"},
        ]
        result = f._deduplicate(papers)
        assert len(result) == 1
        assert result[0]["citation_count"] == 10  # merged to higher
        assert "openalex" in result[0]["source"]
        assert "semantic_scholar" in result[0]["source"]

    def test_deduplicate_by_title(self):
        f = UnifiedFetcher()
        papers = [
            {"doi": "", "title": "Same Title", "citation_count": 5, "source": "a"},
            {"doi": "", "title": "Same Title", "citation_count": 8, "source": "b"},
        ]
        result = f._deduplicate(papers)
        assert len(result) == 1

    def test_aggregate_metrics(self):
        f = UnifiedFetcher()
        profiles = {
            "openalex": {"works_count": 50, "cited_by_count": 1000, "h_index": 20, "i10_index": 30},
            "semantic_scholar": {"paper_count": 48, "citation_count": 950, "h_index": 19},
            "google_scholar": {"cited_by": 1200, "h_index": 22, "i10_index": 35},
        }
        metrics = f._aggregate_metrics(profiles)
        assert metrics["total_papers"] == 50  # max
        assert metrics["total_citations"] == 1200  # max
        assert metrics["h_index"] == 22  # max
        assert metrics["i10_index"] == 35  # max

    def test_aggregate_metrics_empty(self):
        f = UnifiedFetcher()
        metrics = f._aggregate_metrics({})
        assert metrics["total_papers"] == 0
        assert metrics["sources"] == []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_rate_limit(self):
        # Should not raise
        _rate_limit("test_domain", 0.01)
        _rate_limit("test_domain", 0.01)

    @patch("international.data_fetcher.urllib.request.urlopen")
    def test_http_get_json(self, mock_urlopen):
        mock_urlopen.return_value = _mock_json_response({"key": "value"})
        result = _http_get_json("http://example.com")
        assert result["key"] == "value"
