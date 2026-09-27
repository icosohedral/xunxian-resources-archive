"""核心身份与来源模型。

数字 ID 永远不能脱离资源种类单独作为资源身份。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ResourceKind(StrEnum):
    ITEM = "item"
    QUEST_ITEM = "quest_item"
    PET = "pet"
    TITLE = "title"
    RIDE = "ride"


class RelationEvidence(StrEnum):
    SOURCE = "source"
    MAPPED = "mapped"
    CURATED = "curated"
    INFERRED = "inferred"


@dataclass(frozen=True, slots=True)
class ResourceKey:
    kind: ResourceKind
    resource_id: int

    def __post_init__(self) -> None:
        if self.resource_id < 0:
            raise ValueError("resource_id must be non-negative")

    def __str__(self) -> str:
        return f"{self.kind.value}:{self.resource_id}"

