#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
import re
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

import yaml
from dotenv import dotenv_values
from xhs_auth_common import is_auth_error, is_network_error


ROOT = Path(__file__).resolve().parent
SPIDER_ROOT = ROOT / "Spider_XHS"
REPORTS_DIR = ROOT / "reports"
LOCAL_TZ = ZoneInfo("Asia/Shanghai")

os.chdir(SPIDER_ROOT)
sys.path.insert(0, str(SPIDER_ROOT))

from apis.xhs_pc_apis import XHS_Apis  # noqa: E402


NOVELTY_HINTS = [
    "新", "上线", "发布", "推出", "更新", "首发", "新功能", "汇总", "盘点", "趋势",
    "观察", "拆解", "复盘", "总结", "清单", "推荐", "核心", "为什么",
]
LEARNING_HINTS = [
    "学习", "认知", "理解", "复盘", "总结", "方法", "框架", "原则", "思路", "模型",
]
METHOD_HINTS = [
    "步骤", "方法", "框架", "原则", "清单", "模板", "公式", "判断标准", "如何判断",
]
USEFULNESS_HINTS = [
    "产品", "工具", "PM", "产品经理", "信息源", "agent", "Agent", "MCP", "SaaS",
    "工作流", "效率", "分析", "判断", "观察", "趋势",
]
TUTORIAL_HINTS = [
    "教程", "保姆级", "部署", "搭建", "安装", "从0开始", "手把手", "实操",
]
CLICKBAIT_HINTS = [
    "私信", "加群", "进群", "训练营", "卖课", "咨询", "领取", "资料",
]
JOB_NOISE_HINTS = [
    "上岸", "月薪", "实习", "找实习", "面试", "二面", "秋招", "春招", "转行", "内推", "offer",
]
BUSINESS_NOISE_HINTS = [
    "公司注册", "费用多少钱",
]
CODING_NOISE_HINTS = [
    "python", "java", "前端", "后端", "刷题", "算法题",
]
EDUCATION_NOISE_HINTS = [
    "孩子", "家长", "学校", "教育", "提分", "课堂", "老师", "小学", "中学",
]
DOMAIN_SIGNAL_HINTS = [
    "AI", "ai", "人工智能", "产品", "工具", "PM", "产品经理", "Agent", "agent", "MCP", "SaaS", "信息源",
]
CONTROLLED_TAGS = ["AI产品", "AI工具", "Agent", "AI PM", "AI产品经理", "AI知识学习", "信息源"]


def load_rules(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_cookies(path: Path) -> str:
    env = dotenv_values(path)
    cookies = env.get("COOKIES", "")
    if not cookies:
        raise RuntimeError(f"No COOKIES found in {path}")
    return cookies


def validate_cookie(api: XHS_Apis, cookies: str) -> None:
    ok, msg, _ = api.get_user_self_info(cookies)
    if not ok:
        if is_network_error(msg):
            raise RuntimeError(
                f"Cookie validation unavailable due to network error: {msg}. "
                "当前环境无法访问小红书接口，请先检查 DNS 或网络连通性。"
            )
        if is_auth_error(msg):
            raise RuntimeError(
                f"Cookie invalid or expired: {msg}. 请先运行 `python3 xhs_auth_refresh.py --mode qr` 刷新登录态。"
            )
        raise RuntimeError(f"Cookie validation failed: {msg}")


def text_blob(*parts: str) -> str:
    return " ".join(part for part in parts if part).strip()


def contains_any(text: str, words: List[str]) -> bool:
    lower = text.lower()
    return any(word.lower() in lower for word in words)


def count_hits(text: str, words: List[str]) -> int:
    lower = text.lower()
    return sum(1 for word in words if word.lower() in lower)


def build_note_url(note_id: str, xsec_token: str) -> str:
    return f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec_token}&xsec_source=pc_search"


def search_keyword_candidates(
    api: XHS_Apis,
    cookies: str,
    keyword: str,
    limit: int,
) -> List[Dict[str, Any]]:
    ok, msg, notes = api.search_some_note(keyword, limit, cookies, 1, 0, 1, 0, 0, None)
    if not ok:
        raise RuntimeError(f"Keyword search failed for {keyword}: {msg}")
    return notes


def normalize_search_note(note: Dict[str, Any], keyword: str) -> Dict[str, Any]:
    card = note.get("note_card", {})
    user = card.get("user", {})
    interact = card.get("interact_info", {})
    note_id = note.get("id", "")
    xsec_token = note.get("xsec_token", "")
    title = (card.get("display_title") or card.get("title") or "").strip()
    author = (user.get("nickname") or "").strip()
    return {
        "note_id": note_id,
        "url": build_note_url(note_id, xsec_token) if note_id and xsec_token else "",
        "xsec_token": xsec_token,
        "title": title,
        "author_name": author,
        "content_type": card.get("type"),
        "matched_keywords": [keyword],
        "source_lanes": ["keyword_search"],
        "liked_count": interact.get("liked_count"),
        "comment_count": interact.get("comment_count"),
        "search_payload": note,
    }


def search_author_profile(api: XHS_Apis, cookies: str, author_name: str) -> Dict[str, Any] | None:
    ok, msg, users = api.search_some_user(author_name, 5, cookies)
    if not ok:
        raise RuntimeError(f"Priority author search failed for {author_name}: {msg}")
    if not users:
        return None
    for user in users:
        if user.get("name") == author_name:
            return user
    return users[0]


def fetch_author_candidates(
    api: XHS_Apis,
    cookies: str,
    author_name: str,
    limit: int,
) -> List[Dict[str, Any]]:
    user = search_author_profile(api, cookies, author_name)
    if not user:
        return []
    ok, msg, res = api.get_user_note_info(user["id"], "", cookies, user["xsec_token"], "pc_search")
    if not ok:
        raise RuntimeError(f"Author note fetch failed for {author_name}: {msg}")
    notes = res.get("data", {}).get("notes", [])[:limit]
    out: List[Dict[str, Any]] = []
    for note in notes:
        note_id = note.get("note_id", "")
        xsec_token = note.get("xsec_token", "")
        card_user = note.get("user", {})
        interact = note.get("interact_info", {})
        out.append({
            "note_id": note_id,
            "url": build_note_url(note_id, xsec_token) if note_id and xsec_token else "",
            "xsec_token": xsec_token,
            "title": (note.get("display_title") or "").strip(),
            "author_name": (card_user.get("nickname") or author_name).strip(),
            "content_type": note.get("type"),
            "matched_keywords": [],
            "source_lanes": ["priority_author"],
            "liked_count": interact.get("liked_count"),
            "comment_count": interact.get("comment_count"),
            "search_payload": note,
        })
    return out


def fetch_note_detail(api: XHS_Apis, cookies: str, url: str) -> Dict[str, Any]:
    ok, msg, res = api.get_note_info(url, cookies)
    if not ok:
        return {"detail_ok": False, "detail_msg": msg}
    items = res.get("data", {}).get("items", [])
    if not items:
        return {"detail_ok": False, "detail_msg": "No detail items"}
    item = items[0]
    card = item.get("note_card", {})
    user = card.get("user", {})
    interact = card.get("interact_info", {})
    return {
        "detail_ok": True,
        "detail_msg": msg,
        "detail_title": card.get("title") or card.get("display_title") or "",
        "desc": card.get("desc") or "",
        "detail_author": user.get("nickname") or "",
        "detail_type": card.get("type"),
        "publish_time_ms": card.get("time"),
        "last_update_time_ms": card.get("last_update_time"),
        "tag_list": card.get("tag_list") or [],
        "liked_count": interact.get("liked_count"),
        "collected_count": interact.get("collected_count"),
        "comment_count": interact.get("comment_count"),
    }


def infer_topic_tags(candidate: Dict[str, Any]) -> List[str]:
    tags: List[str] = []

    blob = text_blob(
        candidate.get("title", ""),
        candidate.get("detail_title", ""),
        candidate.get("desc", ""),
    )

    for kw in candidate.get("matched_keywords", []):
        if kw in CONTROLLED_TAGS and kw not in tags:
            tags.append(kw)

    inferred_pairs = [
        ("信息源", ["信息源", "汇总", "roundup", "newsletter"]),
        ("Agent", ["agent", "Agent", "skill", "MCP"]),
        ("AI工具", ["AI工具", "工具", "gpt", "openai", "claude"]),
        ("AI产品经理", ["AI产品经理"]),
        ("AI PM", ["PM", "产品经理"]),
        ("AI产品", ["产品", "商业化", "增长", "功能"]),
    ]
    for label, hints in inferred_pairs:
        if contains_any(blob, hints) and label not in tags:
            tags.append(label)

    if contains_any(blob, LEARNING_HINTS) and contains_any(blob, METHOD_HINTS) and "AI知识学习" not in tags:
        tags.append("AI知识学习")

    return tags[:3]


def publish_bucket(candidate: Dict[str, Any], reference_date: date | None = None) -> str:
    ms = candidate.get("publish_time_ms") or candidate.get("last_update_time_ms")
    if not ms:
        return "unknown"
    dt = datetime.fromtimestamp(ms / 1000, tz=LOCAL_TZ)
    ref = reference_date or datetime.now(LOCAL_TZ).date()
    days = (ref - dt.date()).days
    if days == 0:
        return "today"
    if 0 < days <= 3:
        return "recent_3d"
    return "older"


def clean_summary_text(text: str) -> str:
    text = (text or "").replace("\n", " ").replace("\t", " ").strip()
    text = re.sub(r"#.*?#", " ", text)
    text = re.sub(r"\[[^\]]+\]", " ", text)
    text = re.sub(r"^[0-9]+[、.．]\s*", "", text)
    text = re.sub(r"^[（(【\[].*?[）)】\]]\s*", "", text)
    while "  " in text:
        text = text.replace("  ", " ")
    return text


def condense_summary_text(text: str) -> str:
    text = clean_summary_text(text)
    filler_phrases = [
        "对于文科生来说，",
        "对于文科生来说",
        "大家",
        "这次",
        "咱们",
        "真的",
        "直接",
        "其实",
    ]
    for phrase in filler_phrases:
        text = text.replace(phrase, "")
    return clean_summary_text(text)


def compress_title(title: str, max_chars: int) -> str:
    title = clean_summary_text(title)
    if len(title) <= max_chars:
        return title
    window = title[: max_chars + 1]
    punctuation = "，。！？：；,.!?;: "
    cut_pos = -1
    for i, ch in enumerate(window):
        if ch in punctuation:
            cut_pos = i
    if cut_pos >= max(6, max_chars // 2):
        return window[:cut_pos].rstrip(punctuation)

    last_space = max(window.rfind(" "), window.rfind("、"))
    if last_space >= max(6, max_chars // 2):
        return window[:last_space].rstrip(punctuation)

    cut = title[:max_chars].rstrip(punctuation)
    return cut


def is_bad_summary_candidate(text: str) -> bool:
    if not text:
        return True
    if text.count("#") >= 1:
        return True
    if len(text.strip("，。！？：；,.!?;: ")) < 6:
        return True
    if contains_any(text, ["[话题]", "置顶", "刚刚看过"]):
        return True
    return False


def generate_summary(candidate: Dict[str, Any], rules: Dict[str, Any]) -> str:
    summary_rules = rules["summary"]
    max_chars = summary_rules["max_chars"]
    min_chars = summary_rules["min_chars"]

    title = clean_summary_text(candidate.get("detail_title") or candidate.get("title") or "")
    desc = clean_summary_text(candidate.get("desc") or "")
    tags = candidate.get("topic_tags", [])

    summary = ""
    if desc:
        normalized_desc = (
            desc.replace("！", "。")
            .replace("?", "。")
            .replace("？", "。")
            .replace("；", "。")
            .replace(";", "。")
        )
        sentences = [seg.strip() for seg in normalized_desc.split("。") if seg.strip()]
        preferred = None
        for sent in sentences:
            cleaned = condense_summary_text(sent)
            if is_bad_summary_candidate(cleaned):
                continue
            if contains_any(cleaned, ["发现", "总结", "说明", "适合", "值得", "核心", "方法", "框架", "信号", "思路", "判断"]):
                preferred = cleaned
                break
        if not preferred:
            for sent in sentences:
                cleaned = condense_summary_text(sent)
                if not is_bad_summary_candidate(cleaned):
                    preferred = cleaned
                    break
        if preferred:
            summary = preferred
        elif sentences:
            summary = condense_summary_text(sentences[0])

    if summary:
        summary = condense_summary_text(summary)
        summary = compress_title(summary, max_chars)
    else:
        summary = compress_title(title, max_chars)

    if (len(summary) < min_chars or is_bad_summary_candidate(summary)) and title:
        summary = compress_title(title, max_chars)

    summary = summary.rstrip("，。！？：；,.!?;: ")

    if tags:
        lead = tags[0]
        if lead and lead not in summary and len(lead) + 1 + len(summary) <= max_chars:
            summary = f"{lead}：{summary}"

    return summary or "(无摘要)"


def score_candidate(candidate: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    ranking = rules["ranking"]
    scoring = ranking["top_pick_scoring"]
    sources = rules["sources"]

    title = candidate.get("title", "") or candidate.get("detail_title", "")
    desc = candidate.get("desc", "")
    author = candidate.get("author_name", "") or candidate.get("detail_author", "")
    blob = text_blob(title, desc, author)

    if contains_any(blob, scoring["hard_exclusions"]):
        return {
            "is_excluded": True,
            "exclude_reason": "hard_exclusion_match",
            "label": "快速略过",
            "score_breakdown": {},
            "total_score": 0,
        }

    if contains_any(blob, JOB_NOISE_HINTS + BUSINESS_NOISE_HINTS):
        return {
            "is_excluded": True,
            "exclude_reason": "job_or_business_noise",
            "label": "快速略过",
            "score_breakdown": {},
            "total_score": 0,
        }

    if (
        "Agent" in candidate.get("matched_keywords", [])
        and not contains_any(blob, ["AI", "ai", "人工智能", "产品", "工具", "PM", "MCP", "SaaS"])
        and contains_any(blob, CODING_NOISE_HINTS + BUSINESS_NOISE_HINTS)
    ):
        return {
            "is_excluded": True,
            "exclude_reason": "weak_agent_match",
            "label": "快速略过",
            "score_breakdown": {},
            "total_score": 0,
        }

    matched_keywords = candidate.get("matched_keywords", [])
    topic_tags = candidate.get("topic_tags", [])
    has_controlled_tag = any(tag in CONTROLLED_TAGS for tag in topic_tags)
    is_learning_note = "AI知识学习" in topic_tags
    has_method_signal = contains_any(blob, METHOD_HINTS)
    keyword_hits = count_hits(blob, sources["keywords"])
    if keyword_hits >= 2:
        theme_relevance = 5
    elif keyword_hits == 1:
        theme_relevance = 4
    elif has_controlled_tag:
        theme_relevance = 4
    elif author in sources["priority_authors"] and contains_any(blob, DOMAIN_SIGNAL_HINTS + LEARNING_HINTS):
        theme_relevance = 4
    elif matched_keywords:
        theme_relevance = 4
    elif contains_any(blob, DOMAIN_SIGNAL_HINTS):
        theme_relevance = 3
    else:
        theme_relevance = 1

    novelty_hits = count_hits(blob, NOVELTY_HINTS)
    if novelty_hits >= 2:
        novelty = 5
    elif novelty_hits == 1:
        novelty = 3
    else:
        novelty = 1

    if title and contains_any(title, ["核心", "为什么", "拆解", "复盘", "总结", "清单", "汇总"]):
        clarity = 5
    elif title:
        clarity = 3
    else:
        clarity = 1

    usefulness_hits = count_hits(blob, USEFULNESS_HINTS)
    if usefulness_hits >= 2:
        usefulness = 5
    elif usefulness_hits == 1:
        usefulness = 3
    else:
        usefulness = 1

    if is_learning_note and has_method_signal:
        novelty = max(novelty, 3)
        clarity = max(clarity, 3)
        usefulness = max(usefulness, 4)

    if contains_any(blob, EDUCATION_NOISE_HINTS) and not contains_any(blob, ["产品", "工具", "PM", "产品经理", "Agent", "MCP"]):
        usefulness = max(1, usefulness - 2)
        theme_relevance = max(1, theme_relevance - 1)

    engagement = 0
    weights = scoring["weights"]
    weighted = (
        theme_relevance / 5 * weights["theme_relevance"] +
        novelty / 5 * weights["novelty"] +
        clarity / 5 * weights["clarity"] +
        usefulness / 5 * weights["usefulness"] +
        engagement / 5 * weights["engagement"]
    )

    boost = 0
    if author in sources["priority_authors"]:
        boost += scoring["boosts"]["priority_author"]
    elif author in sources["watch_authors"]:
        boost += scoring["boosts"]["watch_author"]

    penalty = 0
    if contains_any(blob, TUTORIAL_HINTS) and novelty < 3:
        penalty += scoring["penalties"]["low_signal_tutorial"]
    if contains_any(blob, CLICKBAIT_HINTS):
        penalty += scoring["penalties"]["clickbait_or_leadgen"]

    total_score = round(weighted + boost - penalty, 2)

    threshold = scoring["thresholds"]
    conditions = 0
    if novelty >= 3:
        conditions += 1
    if clarity >= 3:
        conditions += 1
    if usefulness >= 3:
        conditions += 1

    is_top_pick_eligible = (
        theme_relevance >= threshold["min_theme_relevance"] and
        novelty >= threshold["min_novelty"] and
        clarity >= threshold["min_clarity"] and
        conditions >= 2
    )

    if is_top_pick_eligible:
        label = "值得点开"
    else:
        label = "快速略过"

    return {
        "is_excluded": False,
        "exclude_reason": "",
        "label": label,
        "is_top_pick_eligible": is_top_pick_eligible,
        "score_breakdown": {
            "theme_relevance": theme_relevance,
            "novelty": novelty,
            "clarity": clarity,
            "usefulness": usefulness,
            "engagement": engagement,
            "boost": boost,
            "penalty": penalty,
        },
        "total_score": total_score,
    }


def is_secondary_digest_candidate(candidate: Dict[str, Any]) -> bool:
    blob = text_blob(
        candidate.get("title", "") or candidate.get("detail_title", ""),
        candidate.get("desc", ""),
        candidate.get("author_name", ""),
    )
    if contains_any(blob, TUTORIAL_HINTS + CLICKBAIT_HINTS + EDUCATION_NOISE_HINTS):
        return False
    tags = candidate.get("topic_tags", [])
    breakdown = candidate.get("score_breakdown", {})
    return (
        bool(tags) and
        breakdown.get("theme_relevance", 0) >= 3 and
        breakdown.get("usefulness", 0) >= 2
    )


def is_relaxed_secondary_candidate(candidate: Dict[str, Any]) -> bool:
    blob = text_blob(
        candidate.get("title", "") or candidate.get("detail_title", ""),
        candidate.get("desc", ""),
        candidate.get("author_name", ""),
    )
    if contains_any(blob, CLICKBAIT_HINTS):
        return False
    tags = candidate.get("topic_tags", [])
    breakdown = candidate.get("score_breakdown", {})
    return (
        bool(tags) and
        breakdown.get("theme_relevance", 0) >= 2 and
        breakdown.get("usefulness", 0) >= 1 and
        candidate.get("total_score", 0) >= 50
    )


def load_previously_sent_note_ids(reports_dir: Path, reference_date: date) -> set[str]:
    sent_note_ids: set[str] = set()
    for json_path in sorted(reports_dir.glob("*.json")):
        try:
            report_date = date.fromisoformat(json_path.stem)
        except ValueError:
            continue
        if report_date >= reference_date:
            continue
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for item in payload.get("digest_items", []):
            note_id = item.get("note_id")
            if note_id:
                sent_note_ids.add(str(note_id))
    return sent_note_ids


def append_until_limit(
    target: List[Dict[str, Any]],
    pool: List[Dict[str, Any]],
    target_total: int,
    selected_ids: set[str],
) -> None:
    for item in pool:
        if len(target) >= target_total:
            break
        note_id = item.get("note_id")
        if not note_id or note_id in selected_ids:
            continue
        target.append(item)
        selected_ids.add(note_id)


def merge_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for item in candidates:
        note_id = item["note_id"]
        if note_id not in merged:
            merged[note_id] = item
            continue
        merged[note_id]["matched_keywords"] = sorted(
            set(merged[note_id]["matched_keywords"]) | set(item["matched_keywords"])
        )
        merged[note_id]["source_lanes"] = sorted(
            set(merged[note_id].get("source_lanes", [])) | set(item.get("source_lanes", []))
        )
    return list(merged.values())


def render_markdown(result: Dict[str, Any], output_path: Path) -> None:
    lines: List[str] = []
    lines.append("# XHS AI 日报")
    lines.append("")
    lines.append("## 最推荐")
    for item in result["top_recommended"]:
        summary = item.get("detail_title") or item.get("title") or item.get("summary") or "(无标题)"
        tags = " / ".join(item.get("topic_tags", []))
        lines.append(f"- {summary}")
        lines.append(f"  作者: {item['author_name']}")
        if tags:
            lines.append(f"  关键词: {tags}")
        lines.append(f"  链接: {item['url']}")
        lines.append("")
    if not result["top_recommended"]:
        lines.append("- 今天没有最推荐的日报")
        lines.append("")

    lines.append("## 其余值得看")
    for item in result["more_items"]:
        summary = item.get("detail_title") or item.get("title") or item.get("summary") or "(无标题)"
        tags = " / ".join(item.get("topic_tags", []))
        lines.append(f"- {summary}")
        lines.append(f"  作者: {item['author_name']}")
        if tags:
            lines.append(f"  关键词: {tags}")
        lines.append(f"  链接: {item['url']}")
        lines.append("")
    if not result["more_items"]:
        lines.append("- 暂无")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_digest(
    rules_path: Path,
    cookie_env_path: Path,
    per_author: int,
    detail_limit: int,
    markdown_path: Path,
    json_path: Path,
    reference_date: date | None = None,
) -> Dict[str, Any]:
    rules = load_rules(rules_path)
    cookies = load_cookies(cookie_env_path)
    api = XHS_Apis()
    validate_cookie(api, cookies)
    followed_authors = list(
        dict.fromkeys(rules["sources"]["priority_authors"] + rules["sources"]["watch_authors"])
    )
    author_fetch_errors: List[Dict[str, str]] = []

    REPORTS_DIR.mkdir(exist_ok=True)
    all_candidates: List[Dict[str, Any]] = []
    for author_name in followed_authors:
        try:
            all_candidates.extend(fetch_author_candidates(api, cookies, author_name, per_author))
        except Exception as exc:
            author_fetch_errors.append({"author_name": author_name, "error": str(exc)})
            continue

    if not all_candidates:
        error_preview = "；".join(
            f"{item['author_name']}={item['error']}" for item in author_fetch_errors[:3]
        ) or "未知错误"
        raise RuntimeError(f"未抓到任何关注博主内容。最近错误: {error_preview}")

    merged = merge_candidates(all_candidates)

    detail_candidates = sorted(
        merged,
        key=lambda item: (
            item.get("author_name") in rules["sources"]["priority_authors"],
            item.get("author_name") in followed_authors,
        ),
        reverse=True,
    )
    for item in detail_candidates[:detail_limit]:
        if item["url"]:
            item.update(fetch_note_detail(api, cookies, item["url"]))
        item["topic_tags"] = infer_topic_tags(item)

    scored: List[Dict[str, Any]] = []
    for item in merged:
        item.update(score_candidate(item, rules))
        item["summary"] = generate_summary(item, rules)
        if not item["is_excluded"]:
            scored.append(item)

    scored.sort(key=lambda x: (x["total_score"], x.get("author_name") in rules["sources"]["priority_authors"]), reverse=True)
    daily_limit = rules["ranking"]["daily_item_limit"]
    top_limit = rules["ranking"]["top_pick_limit"]

    eligible_today = [
        item for item in scored
        if publish_bucket(item, reference_date) == "today"
        and item.get("is_top_pick_eligible")
        and item.get("author_name") in followed_authors
    ]

    top_recommended = eligible_today[:top_limit]

    selected_ids = {item["note_id"] for item in top_recommended}
    sent_note_ids = load_previously_sent_note_ids(REPORTS_DIR, reference_date or datetime.now(LOCAL_TZ).date())
    remaining_today = [
        item for item in scored
        if publish_bucket(item, reference_date) == "today"
        and item["note_id"] not in selected_ids
        and item.get("author_name") in followed_authors
        and is_secondary_digest_candidate(item)
    ]
    remaining_today_relaxed = [
        item for item in scored
        if publish_bucket(item, reference_date) == "today"
        and item["note_id"] not in selected_ids
        and item.get("author_name") in followed_authors
        and is_relaxed_secondary_candidate(item)
    ]
    remaining_recent = [
        item for item in scored
        if publish_bucket(item, reference_date) == "recent_3d"
        and item["note_id"] not in selected_ids
        and item["note_id"] not in sent_note_ids
        and item.get("author_name") in followed_authors
        and is_secondary_digest_candidate(item)
    ]
    remaining_recent_relaxed = [
        item for item in scored
        if publish_bucket(item, reference_date) == "recent_3d"
        and item["note_id"] not in selected_ids
        and item["note_id"] not in sent_note_ids
        and item.get("author_name") in followed_authors
        and is_relaxed_secondary_candidate(item)
    ]
    target_total = min(daily_limit, max(3, len(top_recommended)))
    more_items: List[Dict[str, Any]] = []
    append_until_limit(more_items, remaining_today, target_total, selected_ids)
    append_until_limit(more_items, remaining_today_relaxed, target_total, selected_ids)
    append_until_limit(more_items, remaining_recent, target_total, selected_ids)
    append_until_limit(more_items, remaining_recent_relaxed, target_total, selected_ids)
    digest_items = top_recommended + more_items

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    result = {
        "generated_at": generated_at,
        "summary": {
            "total_candidates": len(all_candidates),
            "deduped_candidates": len(merged),
            "kept_candidates": len(scored),
            "author_fetch_errors": len(author_fetch_errors),
        },
        "top_picks": top_recommended,
        "top_recommended": top_recommended,
        "more_items": more_items,
        "digest_items": digest_items,
        "candidates": scored,
        "author_fetch_errors": author_fetch_errors,
    }

    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    render_markdown(result, markdown_path)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect Xiaohongshu digest candidates")
    parser.add_argument("--rules", default=str(ROOT / "xhs-digest-agent.rules.yaml"))
    parser.add_argument("--cookie-env", default=str(SPIDER_ROOT / ".env"))
    parser.add_argument("--per-keyword", type=int, default=5)
    parser.add_argument("--per-author", type=int, default=2)
    parser.add_argument("--detail-limit", type=int, default=15)
    args = parser.parse_args()

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = REPORTS_DIR / f"xhs-prototype-{stamp}.json"
    md_path = REPORTS_DIR / f"xhs-prototype-{stamp}.md"
    result = run_digest(
        rules_path=Path(args.rules),
        cookie_env_path=Path(args.cookie_env),
        per_author=args.per_author,
        detail_limit=args.detail_limit,
        markdown_path=md_path,
        json_path=json_path,
    )

    print(f"generated_at={result['generated_at']}")
    print(f"json={json_path}")
    print(f"markdown={md_path}")
    print(f"digest_items={len(result['digest_items'])}")


if __name__ == "__main__":
    main()
