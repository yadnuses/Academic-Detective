#!/usr/bin/env python3
"""Tests for international/xiaohongshu_client.py"""

import json
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from international.xiaohongshu_client import (
    XiaohongshuClient,
    XiaohongshuReview,
    aggregate_reviews,
    _extract_red_flag,
)


class TestXiaohongshuReview:
    def test_default_values(self):
        review = XiaohongshuReview()
        assert review.platform == "xiaohongshu"
        assert review.sentiment == "neutral"
        assert review.credibility_score == 0.5
        assert review.topics == []

    def test_custom_values(self):
        review = XiaohongshuReview(
            post_id="abc123",
            post_title="Test Title",
            post_content="Test content",
            sentiment="positive",
            credibility_score=0.8,
        )
        assert review.post_id == "abc123"
        assert review.sentiment == "positive"
        assert review.credibility_score == 0.8


class TestExtractDimensions:
    def test_positive_sentiment(self):
        client = XiaohongshuClient()
        review = XiaohongshuReview(post_content="强烈推荐！宝藏导师！")
        client._extract_dimensions(review)
        assert review.sentiment == "positive"

    def test_negative_sentiment(self):
        client = XiaohongshuClient()
        review = XiaohongshuReview(post_content="快跑！避雷！坑！")
        client._extract_dimensions(review)
        assert review.sentiment == "negative"

    def test_graduation_difficulty_easy(self):
        client = XiaohongshuClient()
        review = XiaohongshuReview(post_content="3年毕业，按时毕业很容易")
        client._extract_dimensions(review)
        assert review.graduation_difficulty == 2

    def test_graduation_difficulty_hard(self):
        client = XiaohongshuClient()
        review = XiaohongshuReview(post_content="延期了，卡毕业，5年都没毕业")
        client._extract_dimensions(review)
        assert review.graduation_difficulty == 4

    def test_workload_high(self):
        client = XiaohongshuClient()
        review = XiaohongshuReview(post_content="996 push 周末加班 催命")
        client._extract_dimensions(review)
        assert review.workload == 5

    def test_workload_low(self):
        client = XiaohongshuClient()
        review = XiaohongshuReview(post_content="放养 自由 wlb work life balance")
        client._extract_dimensions(review)
        assert review.workload == 2

    def test_supportiveness_high(self):
        client = XiaohongshuClient()
        review = XiaohongshuReview(post_content="推荐信强推 手把手 funding足 关心学生")
        client._extract_dimensions(review)
        assert review.supportiveness == 5

    def test_supportiveness_low(self):
        client = XiaohongshuClient()
        review = XiaohongshuReview(post_content="不管 不回邮件 甩手掌柜 自生自灭")
        client._extract_dimensions(review)
        assert review.supportiveness == 1

    def test_recommendation_true(self):
        client = XiaohongshuClient()
        review = XiaohongshuReview(post_content="宝藏导师 神仙导师 值得跟 推荐")
        client._extract_dimensions(review)
        assert review.recommendation is True

    def test_recommendation_false(self):
        client = XiaohongshuClient()
        review = XiaohongshuReview(post_content="快跑 避雷 不要来 千万别选")
        client._extract_dimensions(review)
        assert review.recommendation is False

    def test_topics_extraction(self):
        client = XiaohongshuClient()
        review = XiaohongshuReview(post_content="funding充足，毕业顺利，论文发了顶会")
        client._extract_dimensions(review)
        assert "funding" in review.topics
        assert "graduation" in review.topics
        assert "publication" in review.topics


class TestCalculateCredibility:
    def test_high_credibility(self):
        client = XiaohongshuClient()
        review = XiaohongshuReview(
            post_content="Detailed review with specific information about 2023 fall semester, lab meetings, funding amount, TA/RA experience.",
            images_count=2,
            comments_count=10,
            likes=50,
        )
        client._calculate_credibility(review)
        assert review.credibility_score > 0.6

    def test_low_credibility_short_emotional(self):
        client = XiaohongshuClient()
        review = XiaohongshuReview(
            post_content="快跑！",
            sentiment="negative",
        )
        client._calculate_credibility(review)
        assert review.credibility_score < 0.5

    def test_empty_content(self):
        client = XiaohongshuClient()
        review = XiaohongshuReview(post_content="")
        client._calculate_credibility(review)
        assert review.credibility_score == 0.5


class TestIsRelevant:
    def test_relevant_post(self):
        client = XiaohongshuClient()
        review = XiaohongshuReview(
            post_title="MIT CS PhD 选导师",
            post_content="MIT 的 Smith 教授怎么样",
        )
        assert client._is_relevant(review, "Smith", "MIT") is True

    def test_irrelevant_no_institution(self):
        client = XiaohongshuClient()
        review = XiaohongshuReview(
            post_title="Stanford 选导师",
            post_content="Stanford 的 Johnson 教授",
        )
        assert client._is_relevant(review, "Smith", "MIT") is False

    def test_ad_filter(self):
        client = XiaohongshuClient()
        review = XiaohongshuReview(
            post_title="MIT 留学中介",
            post_content="MIT 申请服务 免费咨询 保录取",
        )
        assert client._is_relevant(review, "Smith", "MIT") is False

    def test_abbreviation_match(self):
        client = XiaohongshuClient()
        review = XiaohongshuReview(
            post_title="CMU 导师推荐",
            post_content="Carnegie Mellon",
        )
        assert client._is_relevant(review, "Smith", "Carnegie Mellon University") is True


class TestAggregateReviews:
    def test_empty_reviews(self):
        result = aggregate_reviews([])
        assert result["matched"] is False
        assert result["review_count"] == 0

    def test_single_review(self):
        reviews = [
            XiaohongshuReview(
                post_id="abc",
                post_title="Test",
                post_content="Good review",
                sentiment="positive",
                credibility_score=0.8,
                recommendation=True,
                graduation_difficulty=3,
                workload=3,
                supportiveness=4,
                topics=["funding", "graduation"],
            )
        ]
        result = aggregate_reviews(reviews)
        assert result["matched"] is True
        assert result["review_count"] == 1
        assert result["sentiment_distribution"]["positive"] == 1
        assert result["recommendation_ratio"] == 1.0

    def test_multiple_reviews_mixed(self):
        reviews = [
            XiaohongshuReview(sentiment="positive", credibility_score=0.8, recommendation=True, topics=["funding"]),
            XiaohongshuReview(sentiment="negative", credibility_score=0.6, recommendation=False, topics=["workload"]),
            XiaohongshuReview(sentiment="positive", credibility_score=0.7, recommendation=True, topics=["funding", "graduation"]),
        ]
        result = aggregate_reviews(reviews)
        assert result["review_count"] == 3
        assert result["sentiment_distribution"]["positive"] == 2
        assert result["sentiment_distribution"]["negative"] == 1
        assert result["recommendation_ratio"] == 2 / 3
        assert result["topics"]["funding"] == 2

    def test_red_flags_extraction(self):
        reviews = [
            XiaohongshuReview(
                sentiment="negative",
                credibility_score=0.7,
                post_content="导师 push 压榨 歧视",
            )
        ]
        result = aggregate_reviews(reviews)
        assert len(result["red_flags"]) > 0


class TestExtractRedFlag:
    def test_multiple_flags(self):
        review = XiaohongshuReview(post_content="抢一作 不回邮件 funding问题 push")
        flags = _extract_red_flag(review)
        assert "抢一作" in flags
        assert "不回邮件" in flags
        assert "push" in flags

    def test_no_flags(self):
        review = XiaohongshuReview(post_content="一般般吧")
        flags = _extract_red_flag(review)
        assert flags == "负面评价"
