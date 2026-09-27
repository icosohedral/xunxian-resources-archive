"""生成稳定的外部任务链接。"""

from __future__ import annotations


DEFAULT_QUEST_SITE_BASE_URL = "https://quests.xunxian.wiki"


def quest_url(
    quest_id: int,
    *,
    base_url: str = DEFAULT_QUEST_SITE_BASE_URL,
) -> str:
    if isinstance(quest_id, bool) or not isinstance(quest_id, int) or quest_id <= 0:
        raise ValueError("quest_id 必须是正整数")
    if not base_url.startswith(("https://", "http://")):
        raise ValueError("任务站地址必须是 HTTP(S) URL")
    return f"{base_url.rstrip('/')}/quests/{quest_id}"

