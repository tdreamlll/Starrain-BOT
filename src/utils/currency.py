# -*- coding: utf-8 -*-
"""
货币存储（JSON 文件），用于替代 MySQL 的 user_currency 表。
- 写入：先存内存，每 5 分钟定时按分片刷盘；每轮总写入量 ≤70MB，其余分片下一轮再写，适配机械硬盘。
- 分片：currency_0.json ... currency_31.json，单文件体积由分片数保证 <70MB。
- 多核：按分片加锁，不同分片并发访问；落盘使用线程池并行写各分片（适配 E5-2666 v3 等多核 CPU）。
"""
from pathlib import Path
from typing import Optional, Dict, Tuple, List
from collections import defaultdict
import json
import os
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# 定时落盘间隔（秒）
FLUSH_INTERVAL = 300
# 超过此秒数未活跃的缓存条目将被释放
INACTIVE_TTL = 300
# 缓存条数上限
MAX_CACHE_SIZE = 250_000
# 每轮（每 5 分钟）写入磁盘的总数据量上限（字节），机械硬盘友好
MAX_BYTES_PER_ROUND = 70 * 1024 * 1024
# 单个分片文件体积上限，避免单文件过大
MAX_BYTES_PER_FILE = 70 * 1024 * 1024
# 分片数：使每片用户数约 total/num，单片体积 < MAX_BYTES_PER_FILE（约 50 字节/用户）
NUM_SHARDS = 32
# 每用户约占用字节数（估算落盘体积）
BYTES_PER_USER_EST = 55
# 落盘线程池大小，适配 E5-2666 v3（10 核 20 线程）等多核 CPU
FLUSH_WORKERS = min(NUM_SHARDS, (os.cpu_count() or 8) * 2)

# 内存中每条记录: (balance, last_daily_yyyymmdd, last_activity_timestamp)
_Entry = Tuple[int, int, float]


def _shard_path_from_base(base_path: Path, shard_id: int) -> Path:
    parent = base_path.parent
    stem = base_path.stem
    return parent / f"{stem}_{shard_id}.json"


def _read_shard_file(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"balances": {}, "last_daily": {}}
    data.setdefault("balances", {})
    data.setdefault("last_daily", {})
    return data


def _write_shard_file(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def _write_one_shard_worker(
    base_path: Path,
    shard_id: int,
    qq_entries: Dict[int, _Entry],
) -> None:
    """在 worker 线程中执行：读分片、合并缓存、写回。便于多核并行落盘。"""
    path = _shard_path_from_base(base_path, shard_id)
    data = _read_shard_file(path)
    for qq, (balance, last_daily_int, _) in qq_entries.items():
        sk = str(qq)
        data["balances"][sk] = balance
        ds = _date_int_to_str(last_daily_int)
        if ds is not None:
            data["last_daily"][sk] = ds
        else:
            data["last_daily"].pop(sk, None)
    _write_shard_file(path, data)


def _date_str_to_int(s: Optional[str]) -> int:
    """"YYYY-MM-DD" -> YYYYMMDD，None 或空 -> 0。"""
    if not s:
        return 0
    try:
        parts = s.split("-")
        if len(parts) != 3:
            return 0
        return int(parts[0]) * 10000 + int(parts[1]) * 100 + int(parts[2])
    except (ValueError, AttributeError):
        return 0


def _date_int_to_str(i: int) -> Optional[str]:
    """YYYYMMDD -> "YYYY-MM-DD"，0 -> None。"""
    if i <= 0:
        return None
    y = i // 10000
    m = (i % 10000) // 100
    d = i % 100
    return f"{y}-{m:02d}-{d:02d}"


class CurrencyStore:
    """基于内存缓存 + 分片 JSON 文件的用户货币存储；单文件写入 ≤70MB；多核分片锁 + 并行落盘。"""

    def __init__(self, db_path: Optional[str] = None):
        project_root = Path(__file__).resolve().parents[2]
        data_dir = project_root / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        if db_path is None:
            db_path = data_dir / "currency.json"
        else:
            db_path = Path(db_path)
        self._base_path = Path(db_path)
        self._init_lock = threading.RLock()
        self._shard_locks: List[threading.RLock] = [threading.RLock() for _ in range(NUM_SHARDS)]
        self._cache: Dict[int, _Entry] = {}
        self._executor = ThreadPoolExecutor(max_workers=FLUSH_WORKERS, thread_name_prefix="currency_flush")
        self._ensure_shards_or_migrate()
        self._start_flush_timer()

    def _shard_path(self, shard_id: int) -> Path:
        return _shard_path_from_base(self._base_path, shard_id)

    @staticmethod
    def _shard_id(qq: int) -> int:
        return int(qq) % NUM_SHARDS

    def _ensure_shards_or_migrate(self) -> None:
        """若存在旧单文件且尚无分片则迁移到分片；若 save 目录有旧数据则迁到 data；否则确保至少有一个分片存在。"""
        with self._init_lock:
            first_shard = self._shard_path(0)
            if first_shard.exists():
                return
            project_root = self._base_path.resolve().parents[1]
            old_save_dir = project_root / "save"
            old_shard_0 = old_save_dir / (self._base_path.stem + "_0.json")
            if old_shard_0.exists():
                for i in range(NUM_SHARDS):
                    src = old_save_dir / f"{self._base_path.stem}_{i}.json"
                    if src.exists():
                        shutil.copy2(src, self._shard_path(i))
                return
            old_single = old_save_dir / (self._base_path.stem + ".json")
            if old_single.exists():
                self._migrate_single_file_to_shards(old_single)
                return
            if self._base_path.exists():
                self._migrate_single_to_shards()
                return
            _write_shard_file(self._shard_path(0), {"balances": {}, "last_daily": {}})

    def _migrate_single_file_to_shards(self, from_path: Path) -> None:
        """将指定单文件按 qq % NUM_SHARDS 拆到当前 base 的各分片（用于 save -> data 迁移）。"""
        try:
            with open(from_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return
        balances = data.get("balances", {})
        last_daily = data.get("last_daily", {})
        by_shard: Dict[int, dict] = defaultdict(lambda: {"balances": {}, "last_daily": {}})
        for sk, balance in balances.items():
            try:
                qq = int(sk)
            except ValueError:
                continue
            sid = self._shard_id(qq)
            by_shard[sid]["balances"][sk] = balance
            if sk in last_daily:
                by_shard[sid]["last_daily"][sk] = last_daily[sk]
        for sid, shard_data in by_shard.items():
            _write_shard_file(self._shard_path(sid), shard_data)
        for sid in range(NUM_SHARDS):
            if sid not in by_shard:
                _write_shard_file(self._shard_path(sid), {"balances": {}, "last_daily": {}})

    def _migrate_single_to_shards(self) -> None:
        """将当前 base 的单文件 currency.json 按 qq % NUM_SHARDS 拆到各分片。"""
        try:
            with open(self._base_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return
        balances = data.get("balances", {})
        last_daily = data.get("last_daily", {})
        by_shard: Dict[int, dict] = defaultdict(lambda: {"balances": {}, "last_daily": {}})
        for sk, balance in balances.items():
            try:
                qq = int(sk)
            except ValueError:
                continue
            sid = self._shard_id(qq)
            by_shard[sid]["balances"][sk] = balance
            if sk in last_daily:
                by_shard[sid]["last_daily"][sk] = last_daily[sk]
        for sid, shard_data in by_shard.items():
            _write_shard_file(self._shard_path(sid), shard_data)
        for sid in range(NUM_SHARDS):
            if sid not in by_shard:
                _write_shard_file(self._shard_path(sid), {"balances": {}, "last_daily": {}})

    def _read_shard_unsafe(self, shard_id: int) -> dict:
        """读取单个分片（调用方已持该分片锁）。"""
        return _read_shard_file(self._shard_path(shard_id))

    def _touch(self, qq: int) -> None:
        if qq in self._cache:
            b, d, _ = self._cache[qq]
            self._cache[qq] = (b, d, time.time())

    def _load_from_file(self, qq: int) -> None:
        """从对应分片加载该用户到内存。"""
        sid = self._shard_id(qq)
        data = self._read_shard_unsafe(sid)
        sk = str(qq)
        balance = int(data["balances"].get(sk, 0))
        last_daily = _date_str_to_int(data["last_daily"].get(sk))
        self._cache[qq] = (balance, last_daily, time.time())

    def _flush_to_file(self) -> None:
        """按分片写入；每轮总写入量不超过 MAX_BYTES_PER_ROUND；多分片并行落盘。"""
        for lock in self._shard_locks:
            lock.acquire()
        try:
            by_shard: Dict[int, Dict[int, _Entry]] = defaultdict(dict)
            for qq, entry in self._cache.items():
                by_shard[self._shard_id(qq)][qq] = entry

            round_tasks: List[Tuple[int, Dict[int, _Entry]]] = []
            bytes_this_round = 0
            for shard_id in sorted(by_shard.keys()):
                if bytes_this_round >= MAX_BYTES_PER_ROUND:
                    break
                qq_entries = by_shard[shard_id]
                est = len(qq_entries) * BYTES_PER_USER_EST * 2
                if est > MAX_BYTES_PER_FILE:
                    est = MAX_BYTES_PER_FILE
                if bytes_this_round + est > MAX_BYTES_PER_ROUND and bytes_this_round > 0:
                    break
                round_tasks.append((shard_id, dict(qq_entries)))
                bytes_this_round += est
        finally:
            for lock in self._shard_locks:
                lock.release()

        futures = [
            self._executor.submit(_write_one_shard_worker, self._base_path, sid, entries)
            for sid, entries in round_tasks
        ]
        for f in as_completed(futures):
            f.result()

    def _evict_inactive(self) -> None:
        for lock in self._shard_locks:
            lock.acquire()
        try:
            now = time.time()
            to_remove = [
                qq for qq, (_, _, last_activity) in self._cache.items()
                if (now - last_activity) >= INACTIVE_TTL
            ]
            for qq in to_remove:
                del self._cache[qq]
            if len(self._cache) <= MAX_CACHE_SIZE:
                return
            ordered = sorted(self._cache.items(), key=lambda x: x[1][2])
            for qq, _ in ordered[: len(self._cache) - MAX_CACHE_SIZE]:
                del self._cache[qq]
        finally:
            for lock in self._shard_locks:
                lock.release()

    def _timer_work(self) -> None:
        self._flush_to_file()
        self._evict_inactive()

    def _start_flush_timer(self) -> None:
        def run():
            while True:
                time.sleep(FLUSH_INTERVAL)
                try:
                    self._timer_work()
                except Exception:
                    pass

        t = threading.Thread(target=run, daemon=True)
        t.start()

    def _lock_for(self, qq: int):
        return self._shard_locks[self._shard_id(qq)]

    def get_currency(self, qq: int) -> int:
        qq = int(qq)
        with self._lock_for(qq):
            if qq not in self._cache:
                self._load_from_file(qq)
            self._touch(qq)
            return self._cache[qq][0]

    def set_currency(self, qq: int, amount: int) -> None:
        if amount < 0:
            amount = 0
        qq = int(qq)
        with self._lock_for(qq):
            if qq not in self._cache:
                self._load_from_file(qq)
            _, d, _ = self._cache[qq]
            self._cache[qq] = (amount, d, time.time())

    def add_currency(self, qq: int, delta: int) -> int:
        qq = int(qq)
        with self._lock_for(qq):
            if qq not in self._cache:
                self._load_from_file(qq)
            balance, d, _ = self._cache[qq]
            new_balance = max(0, balance + delta)
            self._cache[qq] = (new_balance, d, time.time())
            return new_balance

    def get_last_daily_date(self, qq: int) -> Optional[str]:
        qq = int(qq)
        with self._lock_for(qq):
            if qq not in self._cache:
                self._load_from_file(qq)
            self._touch(qq)
            return _date_int_to_str(self._cache[qq][1])

    def set_last_daily_date(self, qq: int, date_str: str) -> None:
        qq = int(qq)
        di = _date_str_to_int(date_str)
        with self._lock_for(qq):
            if qq not in self._cache:
                self._load_from_file(qq)
            balance, _, _ = self._cache[qq]
            self._cache[qq] = (balance, di, time.time())

    def get_debug_info(self) -> dict:
        """供 5 级 debug 使用：缓存条数等（不持锁，近似值）。"""
        return {"cache_size": len(self._cache)}


_store: Optional[CurrencyStore] = None


def get_currency_store() -> CurrencyStore:
    global _store
    if _store is None:
        _store = CurrencyStore()
    return _store
