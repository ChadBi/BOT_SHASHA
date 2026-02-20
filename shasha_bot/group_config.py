"""群级行为配置：读取、缓存、持久化。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GroupBehaviorConfig:
    """单个群的行为配置（已合并默认值）。"""

    random_reply_chance: int
    enable_memory: bool
    enable_image: bool


class GroupConfigStore:
    """群级配置存储。"""

    def __init__(self, path: Path, *, default_random_reply_chance: int, default_enable_memory: bool):
        self.path = Path(path)
        self._default_random_reply_chance = max(0, int(default_random_reply_chance))
        self._default_enable_memory = bool(default_enable_memory)
        self._raw: dict[str, dict[str, Any]] = {}
        self._cache: dict[int, GroupBehaviorConfig] = {}
        self.reload()

    def reload(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self._raw = raw if isinstance(raw, dict) else {}
        except FileNotFoundError:
            self._raw = {}
        except Exception:
            self._raw = {}
        self._cache.clear()

    def _to_group_key(self, group_id: int | None) -> str:
        if group_id is None:
            return "private"
        return str(group_id)

    def _parse_group(self, group_id: int | None) -> GroupBehaviorConfig:
        key = self._to_group_key(group_id)
        section = self._raw.get(key, {}) if isinstance(self._raw.get(key, {}), dict) else {}

        random_raw = section.get("random_reply_chance", self._default_random_reply_chance)
        try:
            random_reply_chance = max(0, int(random_raw))
        except Exception:
            random_reply_chance = self._default_random_reply_chance

        enable_memory = section.get("enable_memory", self._default_enable_memory)
        enable_image = section.get("enable_image", True)

        return GroupBehaviorConfig(
            random_reply_chance=random_reply_chance,
            enable_memory=bool(enable_memory),
            enable_image=bool(enable_image),
        )

    def get(self, group_id: int | None) -> GroupBehaviorConfig:
        cache_key = -1 if group_id is None else int(group_id)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        parsed = self._parse_group(group_id)
        self._cache[cache_key] = parsed
        return parsed

    def _ensure_group_raw(self, group_id: int | None) -> dict[str, Any]:
        key = self._to_group_key(group_id)
        section = self._raw.get(key)
        if not isinstance(section, dict):
            section = {}
            self._raw[key] = section
        return section

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._raw, ensure_ascii=False, indent=2), encoding="utf-8")

    def update_random_reply_chance(self, group_id: int | None, chance: int) -> GroupBehaviorConfig:
        section = self._ensure_group_raw(group_id)
        section["random_reply_chance"] = max(0, int(chance))
        self._persist()
        self._cache.pop(-1 if group_id is None else int(group_id), None)
        return self.get(group_id)

    def update_enable_memory(self, group_id: int | None, enabled: bool) -> GroupBehaviorConfig:
        section = self._ensure_group_raw(group_id)
        section["enable_memory"] = bool(enabled)
        self._persist()
        self._cache.pop(-1 if group_id is None else int(group_id), None)
        return self.get(group_id)

    def describe_group(self, group_id: int | None) -> dict[str, Any]:
        cfg = self.get(group_id)
        return asdict(cfg)

