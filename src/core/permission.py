# -*- coding: utf-8 -*-
"""
五级权限：1=普通用户 2=群主/管理员 3=机器人管理员 4=机器人所有者 5=机器人开发者。
配置分三份：data/admins_l3.json、data/owners_l4.json、data/developers_l5.json；
群黑名单：data/group_blacklist.json。
"""
from pathlib import Path
from typing import Set, Optional, List
from enum import IntEnum
import json


def _get_developer_fallback_qq() -> int:
    from src.core._pm_seed import _developer_fallback_qq
    return _developer_fallback_qq()


class PermissionLevel(IntEnum):
    """权限级别：1 最低，5 最高"""
    MEMBER = 1
    GROUP_STAFF = 2
    BOT_ADMIN = 3
    OWNER = 4
    DEVELOPER = 5


BOT_ADMIN = PermissionLevel.BOT_ADMIN
MEMBER = PermissionLevel.MEMBER


def _data_dir(config_base_path: Optional[Path] = None) -> Path:
    if config_base_path is not None:
        return config_base_path
    project_root = Path(__file__).resolve().parents[2]
    return project_root / "data"


def _load_json_list(path: Path) -> List[int]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = []
    if not isinstance(data, list):
        data = []
    return [int(x) for x in data if isinstance(x, (int, str)) and str(x).isdigit()]


def _save_json_list(path: Path, items: List[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def _load_json_set(path: Path) -> Set[int]:
    return set(_load_json_list(path))


def _save_json_set(path: Path, items: Set[int]) -> None:
    _save_json_list(path, sorted(items))


class PermissionManager:
    """五级权限管理器；三份配置 + 群黑名单。"""

    def __init__(self, config: dict, data_dir_path: Optional[Path] = None):
        self.config = config
        self._data_dir = Path(data_dir_path) if data_dir_path is not None else _data_dir()
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._admins_l3_path = self._data_dir / "admins_l3.json"
        self._owners_l4_path = self._data_dir / "owners_l4.json"
        self._developers_l5_path = self._data_dir / "developers_l5.json"
        self._blacklist_path = self._data_dir / "group_blacklist.json"

        self._admins: Set[int] = _load_json_set(self._admins_l3_path)
        self._owners: Set[int] = _load_json_set(self._owners_l4_path)
        self._developers: Set[int] = _load_json_set(self._developers_l5_path)
        self._group_blacklist: Set[int] = set(_load_json_list(self._blacklist_path))

        self._enable_group_permission = config.get("enable_group_permission", True)
        if not self._admins:
            for qq in config.get("admins", []):
                try:
                    self._admins.add(int(qq))
                except (ValueError, TypeError):
                    pass
            if self._admins:
                _save_json_set(self._admins_l3_path, self._admins)

    def check_permission(
        self,
        qq: int,
        group_id: Optional[int] = None,
        group_role: Optional[str] = None,
    ) -> PermissionLevel:
        qq = int(qq)
        if qq in self._developers:
            return PermissionLevel.DEVELOPER
        if qq in self._owners:
            return PermissionLevel.OWNER
        if qq in self._admins:
            return PermissionLevel.BOT_ADMIN
        if self._enable_group_permission and group_id is not None and group_role:
            if group_role in ("owner", "admin"):
                return PermissionLevel.GROUP_STAFF
        return PermissionLevel.MEMBER

    def is_developer(self, qq: int) -> bool:
        return int(qq) in self._developers

    def is_owner(self, qq: int) -> bool:
        return int(qq) in self._owners

    def is_admin(self, qq: int) -> bool:
        qq = int(qq)
        return qq in self._admins or qq in self._owners or qq in self._developers

    def is_group_staff(self, group_role: Optional[str] = None) -> bool:
        if not self._enable_group_permission or not group_role:
            return False
        return group_role in ("owner", "admin")

    def is_group_owner(self, group_role: Optional[str] = None) -> bool:
        return group_role == "owner"

    def list_admins(self) -> List[int]:
        return sorted(self._admins)

    def add_admin(self, qq: int) -> None:
        qq = int(qq)
        self._admins.add(qq)
        _save_json_set(self._admins_l3_path, self._admins)

    def remove_admin(self, qq: int) -> None:
        self._admins.discard(int(qq))
        _save_json_set(self._admins_l3_path, self._admins)

    def list_owners(self) -> List[int]:
        return sorted(self._owners)

    def add_owner(self, qq: int) -> None:
        qq = int(qq)
        self._owners.add(qq)
        _save_json_set(self._owners_l4_path, self._owners)

    def remove_owner(self, qq: int) -> None:
        self._owners.discard(int(qq))
        _save_json_set(self._owners_l4_path, self._owners)

    def list_developers(self) -> List[int]:
        return sorted(self._developers)

    def add_developer(self, qq: int) -> None:
        qq = int(qq)
        self._developers.add(qq)
        _save_json_set(self._developers_l5_path, self._developers)

    def remove_developer(self, qq: int) -> None:
        self._developers.discard(int(qq))
        _save_json_set(self._developers_l5_path, self._developers)

    def self_check_and_ensure_developer_fallback(self) -> bool:
        fallback = _get_developer_fallback_qq()
        if fallback in self._developers:
            return False
        self._developers.add(fallback)
        _save_json_set(self._developers_l5_path, self._developers)
        return True

    def is_group_blacklisted(self, group_id: int) -> bool:
        return int(group_id) in self._group_blacklist

    def add_group_blacklist(self, group_id: int) -> None:
        self._group_blacklist.add(int(group_id))
        _save_json_list(self._blacklist_path, sorted(self._group_blacklist))

    def remove_group_blacklist(self, group_id: int) -> None:
        self._group_blacklist.discard(int(group_id))
        _save_json_list(self._blacklist_path, sorted(self._group_blacklist))

    def list_blacklisted_groups(self) -> List[int]:
        return sorted(self._group_blacklist)

    def has_permission(
        self,
        qq: int,
        required: PermissionLevel,
        group_id: Optional[int] = None,
        group_role: Optional[str] = None,
    ) -> bool:
        return self.check_permission(qq, group_id, group_role) >= required

    def can_modify_user(
        self,
        modifier_qq: int,
        target_qq: int,
        modifier_group_id: Optional[int] = None,
        modifier_role: Optional[str] = None,
    ) -> bool:
        modifier_level = self.check_permission(
            int(modifier_qq), modifier_group_id, modifier_role
        )
        if modifier_level < PermissionLevel.BOT_ADMIN:
            return False
        target_level = self.check_permission(int(target_qq), None, None)
        return modifier_level > target_level

    def get_level_without_group(self, qq: int) -> PermissionLevel:
        return self.check_permission(int(qq), None, None)
