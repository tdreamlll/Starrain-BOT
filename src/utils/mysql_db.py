from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pymysql
import yaml


class MySQLClient:
    """MySQL 客户端封装，供插件使用。

    使用示例（在插件中）:
        from src.utils.mysql_db import get_mysql
        db = get_mysql()
        db.ensure_table(
            \"user_points\",
            \"\"\"
            CREATE TABLE IF NOT EXISTS user_points (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                qq BIGINT NOT NULL,
                points INT NOT NULL DEFAULT 0,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uq_user_points_qq (qq)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            \"\"\"
        )
        rows = db.query_all(\"SELECT * FROM user_points WHERE qq=%s\", (event.user_id,))
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._conn: Optional[pymysql.connections.Connection] = None

    def _connect(self):
        if self._conn and self._conn.open:
            return

        self._conn = pymysql.connect(
            host=self.config.get("host", "127.0.0.1"),
            port=int(self.config.get("port", 3306)),
            user=self.config.get("user", "root"),
            password=self.config.get("password", ""),
            database=self.config.get("database", ""),
            charset=self.config.get("charset", "utf8mb4"),
            autocommit=True,
        )

    def execute(self, sql: str, params: Tuple[Any, ...] = ()) -> int:
        """执行 INSERT/UPDATE/DELETE/DDL，返回受影响行数"""
        self._connect()
        assert self._conn is not None
        with self._conn.cursor() as cursor:
            rowcount = cursor.execute(sql, params)
        return rowcount

    def query_all(self, sql: str, params: Tuple[Any, ...] = ()) -> List[Tuple[Any, ...]]:
        """查询多行结果"""
        self._connect()
        assert self._conn is not None
        with self._conn.cursor() as cursor:
            cursor.execute(sql, params)
            return list(cursor.fetchall())

    def query_one(self, sql: str, params: Tuple[Any, ...] = ()) -> Optional[Tuple[Any, ...]]:
        """查询单行结果"""
        rows = self.query_all(sql, params)
        return rows[0] if rows else None

    # ===== 通用表结构辅助 =====
    def ensure_table(self, table_name: str, create_sql: str) -> None:
        """保证指定表存在：若不存在则按 create_sql 创建。

        table_name: 表名，用于判断是否已存在。
        create_sql: 完整的 CREATE TABLE IF NOT EXISTS ... 语句。
        """
        self._connect()
        assert self._conn is not None
        with self._conn.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema=%s AND table_name=%s",
                (self.config.get("database", ""), table_name),
            )
            exists = cursor.fetchone()[0] > 0

        if not exists:
            # 直接执行插件给出的建表语句
            self.execute(create_sql)

    # ===== 统一货币表 user_currency =====
    def ensure_currency_table(self) -> None:
        """保证统一货币表 user_currency 存在"""
        self.ensure_table(
            "user_currency",
            """
            CREATE TABLE IF NOT EXISTS user_currency (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                qq BIGINT NOT NULL,
                balance BIGINT NOT NULL DEFAULT 0,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uq_user_currency_qq (qq)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """,
        )

    def get_currency(self, qq: int) -> int:
        """获取某个用户的货币余额（不存在则返回 0）"""
        row = self.query_one(
            "SELECT balance FROM user_currency WHERE qq = %s",
            (qq,),
        )
        return int(row[0]) if row else 0

    def set_currency(self, qq: int, amount: int) -> None:
        """直接设置某个用户的货币余额"""
        self.execute(
            """
            INSERT INTO user_currency (qq, balance)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE balance = VALUES(balance)
            """,
            (qq, amount),
        )

    def add_currency(self, qq: int, delta: int) -> int:
        """为某个用户增加/减少货币，返回更新后的余额"""
        self.execute(
            """
            INSERT INTO user_currency (qq, balance)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE balance = balance + VALUES(balance)
            """,
            (qq, delta),
        )
        return self.get_currency(qq)

    def close(self):
        if self._conn:
            try:
                self._conn.close()
            finally:
                self._conn = None


_mysql_client: Optional[MySQLClient] = None


def _load_mysql_config() -> Dict[str, Any]:
    """从 config/config.yaml 读取 mysql 配置"""
    project_root = Path(__file__).resolve().parents[2]
    config_path = project_root / "config" / "config.yaml"
    if not config_path.exists():
        raise RuntimeError("未找到 config/config.yaml，无法读取 MySQL 配置")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    mysql_cfg = config.get("mysql")
    if not mysql_cfg:
        raise RuntimeError("配置文件中未找到 mysql 配置段（mysql: ...）")

    return mysql_cfg


def get_mysql() -> MySQLClient:
    """获取全局 MySQL 客户端单例（供插件直接使用）"""
    global _mysql_client
    if _mysql_client is None:
        cfg = _load_mysql_config()
        client = MySQLClient(cfg)
        # 确保统一货币表存在
        client.ensure_currency_table()
        _mysql_client = client
    return _mysql_client

 