from pathlib import Path
from typing import List, Optional, Dict
import json


class Database:
    """JSON 数据库 封装，文件位于项目根目录下的 save 目录中。"""

    def __init__(self, db_path: Optional[str] = None):
        # 计算项目根目录：src/utils/db.py -> src -> 项目根
        project_root = Path(__file__).resolve().parents[2]
        save_dir = project_root / "save"
        save_dir.mkdir(parents=True, exist_ok=True)

        if db_path is None:
            db_path = save_dir / "bot.json"
        else:
            db_path = Path(db_path)

        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化 JSON 数据文件结构。"""
        if not self.db_path.exists():
            initial = {
                "admins": [],          # List[int]
                "group_configs": {},   # {str(group_id): {key: value}}
            }
            self._write_data(initial)

    def _read_data(self) -> Dict:
        """从 JSON 文件读取全部数据。"""
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {
                "admins": [],
                "group_configs": {},
            }
        # 确保必要字段存在
        data.setdefault("admins", [])
        data.setdefault("group_configs", {})
        return data

    def _write_data(self, data: Dict) -> None:
        """写回 JSON 文件。"""
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ===== 管理员相关操作 =====
    def add_admin(self, qq: int):
        data = self._read_data()
        admins = data.get("admins", [])
        if qq not in admins:
            admins.append(qq)
            data["admins"] = admins
            self._write_data(data)

    def remove_admin(self, qq: int):
        data = self._read_data()
        admins = data.get("admins", [])
        if qq in admins:
            admins.remove(qq)
            data["admins"] = admins
            self._write_data(data)

    def list_admins(self) -> List[int]:
        data = self._read_data()
        return list(data.get("admins", []))

    # ===== 群配置相关操作 =====
    def set_group_config(self, group_id: int, key: str, value: str) -> None:
        """设置或更新某个群的配置项"""
        data = self._read_data()
        group_configs = data.setdefault("group_configs", {})
        group_key = str(group_id)
        group_cfg = group_configs.setdefault(group_key, {})
        group_cfg[key] = value
        group_configs[group_key] = group_cfg
        data["group_configs"] = group_configs
        self._write_data(data)

    def get_group_config(self, group_id: int, key: str) -> Optional[str]:
        """获取某个群的单个配置项"""
        data = self._read_data()
        group_configs = data.get("group_configs", {})
        group_cfg = group_configs.get(str(group_id), {})
        return group_cfg.get(key)

    def list_group_configs(self, group_id: int) -> Dict[str, str]:
        """获取某个群的全部配置项"""
        data = self._read_data()
        group_configs = data.get("group_configs", {})
        return dict(group_configs.get(str(group_id), {}))
