"""Explicit first-party channel registry."""

from __future__ import annotations

from .skillpay import SkillPayAdapter
from .workbuddy import WorkBuddyAdapter
from .xiaohongshu_red_skill import XiaohongshuRedSkillAdapter
from .zhihu_ai_works import ZhihuAiWorksAdapter

CHANNEL_KEYS = (
    "workbuddy",
    "skillpay",
    "zhihu-ai-works",
    "xiaohongshu-red-skill",
)

CHANNEL_REGISTRY = {
    "workbuddy": WorkBuddyAdapter(),
    "skillpay": SkillPayAdapter(),
    "zhihu-ai-works": ZhihuAiWorksAdapter(contract=None),
    "xiaohongshu-red-skill": XiaohongshuRedSkillAdapter(),
}


def get_channel_adapter(key: str):
    try:
        return CHANNEL_REGISTRY[key]
    except KeyError as exc:
        raise KeyError("unknown channel: {0}".format(key)) from exc


__all__ = ["CHANNEL_KEYS", "CHANNEL_REGISTRY", "get_channel_adapter"]
