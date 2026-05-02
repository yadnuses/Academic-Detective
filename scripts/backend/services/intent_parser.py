import re
from typing import Tuple


def parse_intent(text: str) -> Tuple[str, dict]:
    """Parse user intent from natural language input.
    Returns: (intent_type, params)
    """
    t = text.strip().lower()

    # 1. 初始化案件 / 调查某人
    if re.search(r"调查|查一下|查|新建|开始调查|init", t):
        name_match = re.search(r"调查\s*([\u4e00-\u9fa5]{2,8})|[\u4e00-\u9fa5]{2,8}\s*(?:的学术|的背景|的档案)", text)
        name = name_match.group(1) if name_match else ""
        inst_match = re.search(r"([^，,。\s]{2,20})(?:大学|学院|医院|研究所|研究院)", text)
        institution = inst_match.group(0) if inst_match else ""
        return ("init", {"scholar_name": name, "institution": institution})

    # 2. 分析论文 / PDF
    if re.search(r"分析论文|分析PDF|text_profiler|extract.*pdf|提取.*文本", t):
        return ("execute", {"tool": "text_profiler"})

    # 3. 质量评分
    if re.search(r"质量评分|paper_quality|评分|打分|质量评估", t):
        return ("execute", {"tool": "paper_quality"})

    # 4. 混合评分
    if re.search(r"混合评分|hybrid_score|综合评分", t):
        return ("execute", {"tool": "hybrid_score"})

    # 5. 生成报告
    if re.search(r"生成报告|generate|出报告|写报告", t):
        return ("execute", {"tool": "investigate_generate"})

    # 6. 期刊检查
    if re.search(r"查期刊|journal.*check|期刊检查|审稿周期", t):
        return ("execute", {"tool": "journal_check"})

    # 7. 查询状态
    if re.search(r"进度|到哪了|状态|status|怎么样了", t):
        return ("query", {})

    # 8. 暂停
    if re.search(r"暂停|停一下|pause|stop", t):
        return ("pause", {})

    # 9. 恢复
    if re.search(r"继续|resume|go on", t):
        return ("resume", {})

    # 10. 追踪证据
    if re.search(r"追踪|关注|track|follow", t):
        return ("track", {"target": text})

    # 11. 搜索 / 获取网页
    if re.search(r"搜索|搜一下|网上找|查一下.*网上|fetch|get.*url", t):
        url_match = re.search(r'(https?://[^\s]+)', text)
        if url_match:
            return ("fetch", {"url": url_match.group(1)})
        return ("search", {"query": text})

    # 12. 学者姓名+机构 → 自动触发深度调查搜索
    # 匹配如 "张明 南京大学" "李华 清华大学计算机系" 等
    has_name = re.search(r'[\u4e00-\u9fa5]{2,8}', text)
    has_institution = re.search(r'(大学|学院|医院|研究所|研究院)', text)
    if has_name and has_institution and len(text) < 60:
        return ("search", {"query": text + " 学术 论文 导师"})

    # 13. 开放对话
    return ("chat", {"message": text})
