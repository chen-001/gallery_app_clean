"""
Gallery 服务层
处理文件夹和图片相关的业务逻辑
"""

import hashlib
import math
import os
import json
import sqlite3
import threading
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import mimetypes
import logging
import numpy as np

from backend.utils.file_utils import get_file_info, is_image_file, get_image_dimensions
from backend.utils.cache_utils import cached_result, cache_clear

IMAGES_ROOT = os.environ.get(
    "GALLERY_IMAGES_ROOT", os.path.expanduser("~/pythoncode/pngs")
)
DEDUPE_CACHE_FILE = (
    Path(__file__).resolve().parent.parent.parent
    / "config"
    / "data"
    / "correlation_dedupe_cache.json"
)
DEDUPE_PROGRESS_DB_FILE = (
    Path(__file__).resolve().parent.parent.parent
    / "config"
    / "data"
    / "correlation_dedupe_progress.db"
)
MAX_DEDUPE_CACHE_ENTRIES = 50
DEDUPE_BATCH_SIZE = 50
DEDUPE_MAX_KEPT_FACTORS = 100
DEDUPE_RULE_VERSION = "abs_corr_v1"

logger = logging.getLogger(__name__)


class GalleryService:
    """画廊服务类"""

    def __init__(self):
        self.images_root = Path(IMAGES_ROOT)
        self._dedupe_cache_lock = threading.Lock()
        self._dedupe_progress_db_lock = threading.RLock()
        self._dedupe_progress_db_initialized = False
        self._dedupe_run_locks: Dict[str, threading.Lock] = {}
        self._dedupe_run_locks_guard = threading.Lock()
        if not self.images_root.exists():
            logger.warning(f"图片根目录不存在: {self.images_root}")

    def _load_neu_ret_data(self, folder_path: Path) -> Dict[str, float]:
        """
        加载收益率数据（优先从SQLite数据库读取，如果不存在则从JSON文件读取）

        Args:
            folder_path: 文件夹路径

        Returns:
            收益率数据字典，键为图片名（不含扩展名），值为收益率数值
        """
        neu_ret_data = {}

        # 1. 优先尝试从 SQLite 数据库读取
        db_file = folder_path / "neu_rets.db"
        if db_file.exists():
            try:
                conn = sqlite3.connect(str(db_file))
                cursor = conn.cursor()
                cursor.execute("SELECT factor_name, neu_ret FROM factor_returns")
                rows = cursor.fetchall()
                neu_ret_data = {row[0]: row[1] for row in rows}
                conn.close()
                logger.debug(
                    f"从 SQLite 数据库加载收益率数据: {db_file}, 共 {len(neu_ret_data)} 条记录"
                )
                return neu_ret_data
            except Exception as e:
                logger.warning(f"无法从 SQLite 数据库读取 {db_file}: {e}")

        # 2. 如果数据库不存在或读取失败，尝试从 JSON 文件读取（fallback）
        json_file = folder_path / "neu_rets.json"
        if json_file.exists():
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    neu_ret_data = json.load(f)
                logger.debug(
                    f"从 JSON 文件加载收益率数据: {json_file}, 共 {len(neu_ret_data)} 条记录"
                )
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"无法读取 neu_rets.json 文件 {json_file}: {e}")

        return neu_ret_data

    def _build_image_result(self, images: List[Dict], page: int, per_page: int) -> Dict:
        """构建统一的图片分页结果"""
        total = len(images)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page

        return {
            "images": images[start_idx:end_idx],
            "total": total,
            "page": page,
            "per_page": per_page,
            "has_next": end_idx < total,
            "has_prev": page > 1,
        }

    def _build_basic_image_info(self, image_path: Path) -> Optional[Dict]:
        """构建轻量图片信息，避免首屏阶段解析图片内容"""
        try:
            if (
                not image_path.exists()
                or not image_path.is_file()
                or not is_image_file(image_path)
            ):
                return None

            stat = image_path.stat()
            mime_type, _ = mimetypes.guess_type(str(image_path))

            return {
                "name": image_path.name,
                "path": str(image_path),
                "size": stat.st_size,
                "mime_type": mime_type,
                "extension": image_path.suffix.lower(),
                "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "date": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "is_image": True,
                "is_svg": image_path.suffix.lower() == ".svg",
                "relative_path": str(image_path.relative_to(self.images_root)),
            }
        except Exception as e:
            logger.error(f"构建轻量图片信息失败 {image_path}: {e}")
            return None

    def _enrich_image_info(
        self,
        image_info: Dict,
        include_dimensions: bool = True,
        include_description: bool = True,
    ) -> Dict:
        """为当前页图片补充重成本字段"""
        try:
            image_path = Path(str(image_info.get("path", "")))
            if not image_path.exists() or not image_path.is_file():
                relative_path = image_info.get("relative_path")
                if relative_path:
                    image_path = self.images_root / str(relative_path)

            if not image_path.exists() or not image_path.is_file():
                return image_info

            if include_dimensions and (
                "width" not in image_info or "height" not in image_info
            ):
                try:
                    dimensions = get_image_dimensions(image_path)
                    if dimensions:
                        image_info["width"], image_info["height"] = dimensions
                except Exception as e:
                    logger.debug(f"获取图片尺寸失败 {image_path}: {e}")

            if include_description and "description" not in image_info:
                try:
                    description = self._get_image_description_from_folder(
                        image_path.parent, image_path.name
                    )
                    image_info["description"] = description
                    image_info["has_description"] = (
                        description is not None and description.strip() != ""
                    )
                except Exception as e:
                    logger.debug(f"获取图片描述失败 {image_path}: {e}")
                    image_info["description"] = None
                    image_info["has_description"] = False

            if "date" not in image_info:
                image_info["date"] = image_info.get("modified_at")

            return image_info
        except Exception as e:
            logger.error(f"补充图片信息失败 {image_info.get('path')}: {e}")
            return image_info

    @cached_result(timeout=300)
    def _get_folder_descriptions(self, folder_path: Path) -> Dict[str, str]:
        """读取文件夹级描述映射，避免同一页重复打开描述文件"""
        try:
            desc_file = folder_path / ".descriptions.json"
            if desc_file.exists():
                with open(desc_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data if isinstance(data, dict) else {}

            desc_file_public = folder_path / "descriptions.json"
            if desc_file_public.exists():
                with open(desc_file_public, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data if isinstance(data, dict) else {}

            return {}
        except Exception as e:
            logger.error(f"读取图片描述映射失败 {folder_path}: {e}")
            return {}

    def _get_image_description_from_folder(
        self, folder_path: Path, filename: str
    ) -> Optional[str]:
        """按现有优先级读取单张图片描述"""
        descriptions = self._get_folder_descriptions(folder_path)
        if filename in descriptions:
            return descriptions.get(filename)

        name_without_ext = filename.rsplit(".", 1)[0]
        individual_desc_file = folder_path / f"{name_without_ext}.json"
        if individual_desc_file.exists():
            try:
                with open(individual_desc_file, "r", encoding="utf-8") as f:
                    desc_data = json.load(f)
                if isinstance(desc_data, str):
                    return desc_data
                if isinstance(desc_data, dict):
                    return (
                        desc_data.get("description")
                        or desc_data.get("desc")
                        or desc_data.get("text")
                    )
            except Exception as e:
                logger.error(f"读取单图描述失败 {folder_path}/{filename}: {e}")

        return None

    def _load_dedupe_cache_unlocked(self) -> Dict[str, Dict]:
        """读取本地去重缓存文件（需在锁内调用）"""
        if not DEDUPE_CACHE_FILE.exists():
            return {}

        try:
            with open(DEDUPE_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.warning(f"读取去重缓存失败 {DEDUPE_CACHE_FILE}: {e}")
            return {}

    def _write_dedupe_cache_unlocked(self, cache_data: Dict[str, Dict]) -> None:
        """写入本地去重缓存文件（需在锁内调用）"""
        DEDUPE_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp_file = DEDUPE_CACHE_FILE.with_suffix(".tmp")

        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)

        os.replace(temp_file, DEDUPE_CACHE_FILE)

    def _normalize_dedupe_target_kept(self, target_kept_limit: Optional[int]) -> int:
        """当前仅支持 50/100 两档保留目标"""
        if target_kept_limit is None:
            return DEDUPE_BATCH_SIZE

        try:
            target_value = int(target_kept_limit)
        except (TypeError, ValueError):
            return DEDUPE_BATCH_SIZE

        if target_value <= DEDUPE_BATCH_SIZE:
            return DEDUPE_BATCH_SIZE
        return DEDUPE_MAX_KEPT_FACTORS

    def _ensure_dedupe_progress_db_schema(self) -> None:
        """只在进程内初始化一次 SQLite 表结构，避免并发 DDL 锁库"""
        if self._dedupe_progress_db_initialized:
            return

        with self._dedupe_progress_db_lock:
            if self._dedupe_progress_db_initialized:
                return

            DEDUPE_PROGRESS_DB_FILE.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(
                str(DEDUPE_PROGRESS_DB_FILE),
                timeout=30,
                check_same_thread=False,
            )
            try:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA busy_timeout=30000")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS dedupe_runs (
                        run_key TEXT PRIMARY KEY,
                        cache_key TEXT NOT NULL,
                        signature TEXT NOT NULL,
                        threshold REAL NOT NULL,
                        total_factors INTEGER NOT NULL,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS dedupe_factor_results (
                        run_key TEXT NOT NULL,
                        factor_index INTEGER NOT NULL,
                        relative_path TEXT NOT NULL,
                        factor_name TEXT,
                        factor_version TEXT,
                        neu_ret REAL,
                        is_kept INTEGER NOT NULL,
                        max_corr REAL,
                        max_corr_with TEXT,
                        compared_count INTEGER NOT NULL DEFAULT 0,
                        processed INTEGER NOT NULL DEFAULT 0,
                        processed_at TEXT,
                        PRIMARY KEY (run_key, factor_index)
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS dedupe_pairwise_results (
                        run_key TEXT NOT NULL,
                        factor_index INTEGER NOT NULL,
                        prior_relative_path TEXT NOT NULL,
                        corr REAL,
                        created_at TEXT NOT NULL,
                        PRIMARY KEY (run_key, factor_index, prior_relative_path)
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_dedupe_pairwise_run_factor
                    ON dedupe_pairwise_results (run_key, factor_index)
                    """
                )
                conn.commit()
                self._dedupe_progress_db_initialized = True
            finally:
                conn.close()

    def _open_dedupe_progress_db(self) -> sqlite3.Connection:
        """打开去重进度数据库，支持断点续跑"""
        self._ensure_dedupe_progress_db_schema()
        DEDUPE_PROGRESS_DB_FILE.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            str(DEDUPE_PROGRESS_DB_FILE),
            timeout=30,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _build_dedupe_control_state(
        self,
        status: str,
        processed_factors: int,
        total_factors: int,
        kept_factors: int,
        target_kept_limit: Optional[int],
    ) -> Dict[str, object]:
        """构造前端继续/暂停控制所需状态"""
        target_limit = self._normalize_dedupe_target_kept(target_kept_limit)
        processed_factors = max(0, int(processed_factors))
        total_factors = max(0, int(total_factors))
        kept_factors = max(0, int(kept_factors))

        can_continue = (
            status in {"paused", "failed"}
            and processed_factors < total_factors
            and kept_factors < DEDUPE_MAX_KEPT_FACTORS
        )

        next_target_kept = target_limit
        if kept_factors >= target_limit and target_limit < DEDUPE_MAX_KEPT_FACTORS:
            next_target_kept = min(
                target_limit + DEDUPE_BATCH_SIZE, DEDUPE_MAX_KEPT_FACTORS
            )

        if status == "failed" and kept_factors < target_limit:
            next_target_kept = target_limit

        return {
            "status": status,
            "processed_factors": processed_factors,
            "total_factors": total_factors,
            "kept_factors": kept_factors,
            "target_kept_limit": target_limit,
            "hard_stop_limit": DEDUPE_MAX_KEPT_FACTORS,
            "can_continue": can_continue,
            "next_target_kept": next_target_kept,
            "has_partial_result": kept_factors > 0
            and processed_factors < total_factors,
        }

    def _build_dedupe_run_key(
        self, cache_key: str, signature: str, threshold: float
    ) -> str:
        payload = f"{cache_key}|{signature}|{threshold:.6f}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _ensure_dedupe_run(
        self,
        conn: sqlite3.Connection,
        run_key: str,
        cache_key: str,
        signature: str,
        threshold: float,
        total_factors: int,
    ) -> None:
        now = datetime.now().isoformat()
        conn.execute(
            """
            INSERT INTO dedupe_runs (
                run_key, cache_key, signature, threshold, total_factors, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_key) DO UPDATE SET
                total_factors=excluded.total_factors,
                status=excluded.status,
                updated_at=excluded.updated_at
            """,
            (
                run_key,
                cache_key,
                signature,
                threshold,
                total_factors,
                "running",
                now,
                now,
            ),
        )
        conn.commit()

    def _update_dedupe_run_status(
        self,
        conn: sqlite3.Connection,
        run_key: str,
        status: str,
    ) -> None:
        conn.execute(
            "UPDATE dedupe_runs SET status = ?, updated_at = ? WHERE run_key = ?",
            (status, datetime.now().isoformat(), run_key),
        )
        conn.commit()

    def _get_dedupe_run_lock(self, run_key: str) -> threading.Lock:
        with self._dedupe_run_locks_guard:
            lock = self._dedupe_run_locks.get(run_key)
            if lock is None:
                lock = threading.Lock()
                self._dedupe_run_locks[run_key] = lock
            return lock

    def _load_dedupe_run_row(
        self,
        conn: sqlite3.Connection,
        run_key: str,
    ) -> Optional[sqlite3.Row]:
        return conn.execute(
            """
            SELECT run_key, cache_key, signature, threshold, total_factors, status, created_at, updated_at
            FROM dedupe_runs
            WHERE run_key = ?
            """,
            (run_key,),
        ).fetchone()

    def _load_resumable_dedupe_state(
        self,
        conn: sqlite3.Connection,
        run_key: str,
        images: List[Dict],
    ) -> Tuple[int, List[Dict]]:
        """恢复已经完成的前缀结果，重新构造 kept_images"""
        image_map = {str(image.get("relative_path")): image for image in images}
        rows = conn.execute(
            """
            SELECT factor_index, relative_path, is_kept, processed
            FROM dedupe_factor_results
            WHERE run_key = ?
            ORDER BY factor_index
            """,
            (run_key,),
        ).fetchall()

        processed_prefix = 0
        kept_images: List[Dict] = []

        for row in rows:
            factor_index = int(row["factor_index"])
            if factor_index != processed_prefix + 1 or int(row["processed"]) != 1:
                break

            processed_prefix = factor_index
            if int(row["is_kept"]) == 1:
                image = image_map.get(str(row["relative_path"]))
                if image is not None:
                    kept_images.append(image)

        return processed_prefix, kept_images

    def _load_saved_factor_comparisons(
        self,
        conn: sqlite3.Connection,
        run_key: str,
        factor_index: int,
    ) -> Dict[str, Optional[float]]:
        rows = conn.execute(
            """
            SELECT prior_relative_path, corr
            FROM dedupe_pairwise_results
            WHERE run_key = ? AND factor_index = ?
            """,
            (run_key, factor_index),
        ).fetchall()
        return {str(row["prior_relative_path"]): row["corr"] for row in rows}

    def _save_factor_comparison(
        self,
        conn: sqlite3.Connection,
        run_key: str,
        factor_index: int,
        prior_relative_path: str,
        corr: Optional[float],
    ) -> None:
        conn.execute(
            """
            INSERT OR REPLACE INTO dedupe_pairwise_results (
                run_key, factor_index, prior_relative_path, corr, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                run_key,
                factor_index,
                prior_relative_path,
                float(corr) if corr is not None else None,
                datetime.now().isoformat(),
            ),
        )

    def _save_dedupe_factor_result(
        self,
        conn: sqlite3.Connection,
        run_key: str,
        factor_index: int,
        image_info: Dict,
        is_kept: bool,
        max_corr: Optional[float],
        max_corr_with: Optional[str],
        compared_count: int,
    ) -> None:
        conn.execute(
            """
            INSERT OR REPLACE INTO dedupe_factor_results (
                run_key, factor_index, relative_path, factor_name, factor_version, neu_ret,
                is_kept, max_corr, max_corr_with, compared_count, processed, processed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                run_key,
                factor_index,
                str(image_info.get("relative_path", "")),
                str(self._get_factor_name_from_image(image_info)),
                str(image_info.get("factor_version", "")),
                float(image_info.get("neu_ret", 0) or 0),
                1 if is_kept else 0,
                float(max_corr) if max_corr is not None else None,
                max_corr_with,
                compared_count,
                datetime.now().isoformat(),
            ),
        )

    def _rank_factor_matrix(self, values: np.ndarray) -> np.ndarray:
        """用 numpy 进行逐行排序，替代 pandas rank(axis=1) 的高开销实现"""
        matrix = np.asarray(values, dtype=np.float32)
        if matrix.ndim != 2:
            return matrix

        valid_mask = np.isfinite(matrix)
        filled = np.where(valid_mask, matrix, np.inf)
        order = np.argsort(filled, axis=1, kind="mergesort")
        ranks = np.empty(matrix.shape, dtype=np.float32)
        row_indices = np.arange(matrix.shape[0])[:, None]
        ranks[row_indices, order] = np.arange(1, matrix.shape[1] + 1, dtype=np.float32)
        ranks[~valid_mask] = np.nan
        return ranks

    def _mean_rowwise_correlation(
        self,
        left_values: np.ndarray,
        right_values: np.ndarray,
    ) -> Optional[float]:
        """按日期逐行计算截面相关性，避免构造超大中间矩阵"""
        total_corr = 0.0
        valid_days = 0

        for left_row, right_row in zip(left_values, right_values):
            mask = np.isfinite(left_row) & np.isfinite(right_row)
            if mask.sum() <= 1:
                continue

            valid_left = left_row[mask]
            valid_right = right_row[mask]
            centered_left = valid_left - valid_left.mean()
            centered_right = valid_right - valid_right.mean()
            denominator = np.linalg.norm(centered_left) * np.linalg.norm(centered_right)
            if denominator <= 0:
                continue

            total_corr += float(np.dot(centered_left, centered_right) / denominator)
            valid_days += 1

        if valid_days == 0:
            return None

        return total_corr / valid_days

    def _get_factor_data_file_path(self, factor_version: str, factor_name: str) -> Path:
        """获取相关性计算实际依赖的 parquet 路径"""
        from backend.utils.correlation_utils import FACTOR_DATA_ROOT

        parquet_factor_name = (
            factor_name[:-5] if factor_name.endswith("_fold") else factor_name
        )
        return (
            Path(FACTOR_DATA_ROOT) / factor_version / f"{parquet_factor_name}.parquet"
        )

    def _build_dedupe_cache_signature(
        self, images: List[Dict], threshold: float
    ) -> str:
        """基于当前候选因子集合、去重规则和底层数据时间戳生成缓存签名"""
        parquet_mtime_cache: Dict[Tuple[str, str], Optional[int]] = {}
        signature_items = []

        for image_info in images:
            factor_version = str(image_info.get("factor_version", ""))
            factor_name = str(self._get_factor_name_from_image(image_info))
            parquet_key = (factor_version, factor_name)

            if parquet_key not in parquet_mtime_cache:
                parquet_path = self._get_factor_data_file_path(
                    factor_version, factor_name
                )
                parquet_mtime_cache[parquet_key] = (
                    parquet_path.stat().st_mtime_ns if parquet_path.exists() else None
                )

            signature_items.append(
                {
                    "relative_path": image_info.get("relative_path"),
                    "factor_version": factor_version,
                    "factor_name": factor_name,
                    "neu_ret": image_info.get("neu_ret", 0),
                    "parquet_mtime_ns": parquet_mtime_cache[parquet_key],
                }
            )

        payload = {
            "rule_version": DEDUPE_RULE_VERSION,
            "threshold": threshold,
            "items": signature_items,
        }
        payload_str = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

    def _get_cached_dedupe_entry(
        self, cache_key: str, signature: str
    ) -> Optional[Dict]:
        """读取匹配签名的本地去重缓存条目"""
        with self._dedupe_cache_lock:
            cache_data = self._load_dedupe_cache_unlocked()

        entry = cache_data.get(cache_key)
        if not entry or entry.get("signature") != signature:
            return None
        if not isinstance(entry, dict):
            return None
        return entry

    def _get_cached_dedupe_result(
        self, cache_key: str, signature: str
    ) -> Optional[List[str]]:
        """读取命中的本地去重结果"""
        entry = self._get_cached_dedupe_entry(cache_key, signature)
        if not entry:
            return None
        if entry.get("status") not in (None, "completed"):
            return None

        kept_paths = entry.get("kept_relative_paths")
        if not isinstance(kept_paths, list):
            return None

        logger.info("命中去重缓存: %s", cache_key)
        return kept_paths

    def _save_cached_dedupe_result(
        self,
        cache_key: str,
        signature: str,
        kept_relative_paths: List[str],
        status: str = "completed",
        state: Optional[Dict[str, object]] = None,
    ) -> None:
        """保存本地去重结果，供后续点击直接复用"""
        with self._dedupe_cache_lock:
            cache_data = self._load_dedupe_cache_unlocked()
            cache_data[cache_key] = {
                "signature": signature,
                "kept_relative_paths": kept_relative_paths,
                "status": status,
                "updated_at": datetime.now().isoformat(),
            }
            if state:
                cache_data[cache_key]["state"] = state

            if len(cache_data) > MAX_DEDUPE_CACHE_ENTRIES:
                sorted_items = sorted(
                    cache_data.items(),
                    key=lambda item: item[1].get("updated_at", ""),
                    reverse=True,
                )
                cache_data = dict(sorted_items[:MAX_DEDUPE_CACHE_ENTRIES])

            self._write_dedupe_cache_unlocked(cache_data)

    def _load_existing_dedupe_snapshot(
        self,
        conn: sqlite3.Connection,
        images: List[Dict],
        cache_key: str,
        threshold: float,
        target_kept_limit: Optional[int],
    ) -> Optional[Tuple[List[Dict], Dict[str, object], str]]:
        """从 SQLite 恢复当前快照，用于刷新展示而不是继续计算"""
        if not images:
            return None

        signature = self._build_dedupe_cache_signature(images, threshold)
        run_key = self._build_dedupe_run_key(cache_key, signature, threshold)
        run_row = self._load_dedupe_run_row(conn, run_key)
        if run_row is None:
            return None

        processed_prefix, kept_images = self._load_resumable_dedupe_state(
            conn, run_key, images
        )
        if processed_prefix <= 0 and not kept_images:
            return None

        annotations = self._load_dedupe_annotations(
            images,
            cache_key=cache_key,
            threshold=threshold,
            conn=conn,
        )
        kept_images = self._apply_dedupe_annotations(kept_images, annotations)
        run_status = str(run_row["status"] or "running")
        total_factors = int(run_row["total_factors"] or len(images))
        state = self._build_dedupe_control_state(
            status=run_status,
            processed_factors=processed_prefix,
            total_factors=total_factors,
            kept_factors=len(kept_images),
            target_kept_limit=target_kept_limit,
        )
        return kept_images, state, run_status

    def _apply_cached_dedupe_paths(
        self,
        images: List[Dict],
        kept_relative_paths: List[str],
    ) -> List[Dict]:
        """把缓存的保留顺序映射回当前图片对象"""
        image_map = {str(image.get("relative_path")): image for image in images}
        return [image_map[path] for path in kept_relative_paths if path in image_map]

    def _load_dedupe_annotations(
        self,
        images: List[Dict],
        cache_key: str,
        threshold: float = 0.6,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Dict]:
        """读取每个因子的最大相关因子与相关性摘要"""
        if not images:
            return {}

        signature = self._build_dedupe_cache_signature(images, threshold)
        run_key = self._build_dedupe_run_key(cache_key, signature, threshold)
        image_map = {str(image.get("relative_path")): image for image in images}
        active_conn = conn
        owns_connection = False

        try:
            if active_conn is None:
                active_conn = self._open_dedupe_progress_db()
                owns_connection = True

            rows = active_conn.execute(
                """
                SELECT
                    src.relative_path,
                    src.max_corr,
                    src.max_corr_with,
                    src.compared_count,
                    target.factor_name AS max_corr_factor_name,
                    target.factor_version AS max_corr_factor_version,
                    target.relative_path AS max_corr_relative_path
                FROM dedupe_factor_results AS src
                LEFT JOIN dedupe_factor_results AS target
                    ON target.run_key = src.run_key
                    AND target.relative_path = src.max_corr_with
                WHERE src.run_key = ?
                """,
                (run_key,),
            ).fetchall()
        except Exception as e:
            logger.warning("读取去重注解失败 %s: %s", cache_key, e)
            return {}
        finally:
            try:
                if owns_connection and active_conn is not None:
                    active_conn.close()
            except Exception:
                pass

        annotations: Dict[str, Dict] = {}
        for row in rows:
            relative_path = str(row["relative_path"])
            target_path = row["max_corr_relative_path"] or row["max_corr_with"]
            target_image = image_map.get(str(target_path)) if target_path else None
            target_factor_name = row["max_corr_factor_name"] or (
                self._get_factor_name_from_image(target_image) if target_image else None
            )
            target_factor_version = row["max_corr_factor_version"] or (
                str(target_image.get("factor_version")) if target_image else None
            )

            annotations[relative_path] = {
                "dedupe_compared_count": int(row["compared_count"] or 0),
                "dedupe_max_corr": float(row["max_corr"])
                if row["max_corr"] is not None
                else None,
                "dedupe_max_corr_with_relative_path": str(target_path)
                if target_path
                else None,
                "dedupe_max_corr_factor_name": target_factor_name,
                "dedupe_max_corr_factor_version": target_factor_version,
            }

        return annotations

    def _apply_dedupe_annotations(
        self,
        images: List[Dict],
        annotations: Dict[str, Dict],
    ) -> List[Dict]:
        """把去重分析摘要附加到图片信息上"""
        if not annotations:
            return images

        for image in images:
            relative_path = str(image.get("relative_path", ""))
            annotation = annotations.get(relative_path)
            if not annotation:
                continue
            image.update(annotation)

        return images

    def _get_factor_name_from_image(self, image_info: Dict) -> str:
        """从图片信息中提取因子名"""
        factor_name = image_info.get("factor_name")
        if factor_name:
            return factor_name
        image_name = image_info.get("name", "")
        return image_name.rsplit(".", 1)[0] if "." in image_name else image_name

    def _get_factor_version_from_folder(self, folder_name: str) -> str:
        """从文件夹路径中提取因子版本"""
        return Path(folder_name).name

    def _apply_neu_ret_metadata(
        self,
        images: List[Dict],
        neu_ret_data: Dict[str, float],
        default_factor_version: str,
        dedupe_group: Optional[str] = None,
    ) -> List[Dict]:
        """为图片附加收益率排序和相关性去重所需的元信息"""
        group_name = dedupe_group or default_factor_version

        for image_info in images:
            factor_name = self._get_factor_name_from_image(image_info)
            image_info["factor_name"] = factor_name
            image_info["factor_version"] = image_info.get(
                "factor_version", default_factor_version
            )
            image_info["dedupe_group"] = image_info.get("dedupe_group", group_name)
            image_info["neu_ret"] = neu_ret_data.get(factor_name, 0)

        return images

    def _get_neu_ret_sort_key(self, image_info: Dict) -> Tuple[float, str, str]:
        """收益率排序键，收益率降序，其余字段升序打破并列"""
        try:
            neu_ret = float(image_info.get("neu_ret", 0) or 0)
        except (TypeError, ValueError):
            neu_ret = 0.0
        factor_version = str(image_info.get("factor_version", ""))
        factor_name = str(self._get_factor_name_from_image(image_info))
        return (-neu_ret, factor_version.lower(), factor_name.lower())

    def _load_ranked_factor_data(
        self,
        factor_version: str,
        factor_name: str,
        factor_cache: Dict[Tuple[str, str], Optional[object]],
    ):
        """加载并缓存因子数据，按原始截面值计算相关性以避免 rank 的高开销"""
        cache_key = (factor_version, factor_name)
        if cache_key in factor_cache:
            return factor_cache[cache_key]

        try:
            from backend.utils.correlation_utils import load_and_process_factor

            df = load_and_process_factor(factor_version, factor_name)
            if df is None:
                factor_cache[cache_key] = None
                return None

            values = df.to_numpy(dtype=np.float32, copy=False)

            factor_cache[cache_key] = {
                "index": df.index,
                "values": values,
            }
            return factor_cache[cache_key]
        except Exception as e:
            logger.warning(f"加载因子数据失败 {factor_name}@{factor_version}: {e}")
            factor_cache[cache_key] = None
            return None

    def _calculate_mean_factor_correlation(
        self,
        image_a: Dict,
        image_b: Dict,
        factor_cache: Dict[Tuple[str, str], Optional[object]],
        correlation_cache: Dict[
            Tuple[Tuple[str, str], Tuple[str, str]], Optional[float]
        ],
    ) -> Optional[float]:
        """计算两个因子的平均截面相关性"""
        factor_a = (
            str(image_a.get("factor_version", "")),
            str(self._get_factor_name_from_image(image_a)),
        )
        factor_b = (
            str(image_b.get("factor_version", "")),
            str(self._get_factor_name_from_image(image_b)),
        )
        cache_key = tuple(sorted((factor_a, factor_b)))

        if cache_key in correlation_cache:
            return correlation_cache[cache_key]

        try:
            df1 = self._load_ranked_factor_data(factor_a[0], factor_a[1], factor_cache)
            df2 = self._load_ranked_factor_data(factor_b[0], factor_b[1], factor_cache)

            if df1 is None or df2 is None:
                correlation_cache[cache_key] = None
                return None

            index1 = df1["index"]
            index2 = df2["index"]
            common_dates = index1.intersection(index2)
            if len(common_dates) == 0:
                correlation_cache[cache_key] = None
                return None

            if (
                len(common_dates) == len(index1)
                and len(common_dates) == len(index2)
                and index1.equals(index2)
            ):
                values1 = df1["values"]
                values2 = df2["values"]
            else:
                positions1 = index1.get_indexer(common_dates)
                positions2 = index2.get_indexer(common_dates)
                values1 = df1["values"][positions1]
                values2 = df2["values"][positions2]

            mean_corr = self._mean_rowwise_correlation(values1, values2)
            if (
                mean_corr is None
                or (isinstance(mean_corr, float) and math.isnan(mean_corr))
                or mean_corr != mean_corr
            ):
                correlation_cache[cache_key] = None
                return None

            correlation_cache[cache_key] = float(mean_corr)
            return correlation_cache[cache_key]
        except Exception as e:
            logger.warning(
                f"计算相关性失败 {factor_a[1]}@{factor_a[0]} vs {factor_b[1]}@{factor_b[0]}: {e}"
            )
            correlation_cache[cache_key] = None
            return None

    def _emit_dedupe_progress(
        self,
        task_id: Optional[str],
        status: str,
        processed_factors: int,
        total_factors: int,
        kept_factors: int,
        target_kept_limit: Optional[int] = None,
        start_time: Optional[float] = None,
        current_factor: Optional[str] = None,
        message: str = "",
        kept_images: Optional[List[Dict]] = None,
        new_kept_image: Optional[Dict] = None,
        replace_gallery: bool = False,
    ) -> None:
        """通过 Socket.IO 向前端广播去重进度"""
        if not task_id:
            return

        try:
            from backend.app import socketio

            elapsed_seconds = 0.0
            eta_seconds = None
            progress_percent = 0

            if start_time is not None:
                elapsed_seconds = max(0.0, time.monotonic() - start_time)

            if total_factors > 0:
                progress_percent = min(
                    100, int((processed_factors / total_factors) * 100)
                )

            if (
                processed_factors > 0
                and total_factors > processed_factors
                and elapsed_seconds > 0
            ):
                eta_seconds = (elapsed_seconds / processed_factors) * (
                    total_factors - processed_factors
                )

            control_state = self._build_dedupe_control_state(
                status=status,
                processed_factors=processed_factors,
                total_factors=total_factors,
                kept_factors=kept_factors,
                target_kept_limit=target_kept_limit,
            )

            socketio.emit(
                "dedupe_progress",
                {
                    "task_id": task_id,
                    "status": status,
                    "processed_factors": processed_factors,
                    "total_factors": total_factors,
                    "kept_factors": kept_factors,
                    "progress_percent": progress_percent,
                    "elapsed_seconds": round(elapsed_seconds, 1),
                    "eta_seconds": round(eta_seconds, 1)
                    if eta_seconds is not None
                    else None,
                    "current_factor": current_factor,
                    "message": message,
                    "kept_images": kept_images or [],
                    "new_kept_image": new_kept_image,
                    "replace_gallery": replace_gallery,
                    **control_state,
                },
            )
        except Exception as e:
            logger.warning("发送去重进度失败 %s: %s", task_id, e)

    def _dedupe_images_by_correlation(
        self,
        images: List[Dict],
        threshold: float = 0.6,
        cache_key: Optional[str] = None,
        task_id: Optional[str] = None,
        target_kept_limit: Optional[int] = None,
        continue_requested: bool = False,
    ) -> Tuple[List[Dict], Dict[str, object]]:
        """按收益率从高到低贪心去除高相关的重复因子，使用相关系数绝对值判重"""
        start_time = time.monotonic()
        conn: Optional[sqlite3.Connection] = None
        run_key: Optional[str] = None
        run_lock: Optional[threading.Lock] = None
        acquired_run_lock = False
        normalized_target_kept = self._normalize_dedupe_target_kept(target_kept_limit)
        kept_images: List[Dict] = []
        processed_prefix = 0
        last_processed_factors = 0
        total_factors = len(images)

        try:
            if len(images) < 2:
                final_state = self._build_dedupe_control_state(
                    status="completed",
                    processed_factors=len(images),
                    total_factors=len(images),
                    kept_factors=len(images),
                    target_kept_limit=normalized_target_kept,
                )
                self._emit_dedupe_progress(
                    task_id,
                    status="completed",
                    processed_factors=len(images),
                    total_factors=len(images),
                    kept_factors=len(images),
                    target_kept_limit=normalized_target_kept,
                    start_time=start_time,
                    message="候选因子数量较少，无需去重",
                )
                return images, final_state

            dedupe_cache_key = cache_key or f"adhoc::{len(images)}"
            cache_signature = self._build_dedupe_cache_signature(images, threshold)
            run_key = self._build_dedupe_run_key(
                dedupe_cache_key, cache_signature, threshold
            )

            self._emit_dedupe_progress(
                task_id,
                status="running",
                processed_factors=0,
                total_factors=len(images),
                kept_factors=0,
                target_kept_limit=normalized_target_kept,
                start_time=start_time,
                message="开始计算高相关去重",
            )

            if cache_key:
                cached_paths = self._get_cached_dedupe_result(
                    cache_key, cache_signature
                )
                if cached_paths is not None:
                    cached_images = self._apply_cached_dedupe_paths(
                        images, cached_paths
                    )
                    cached_annotations = self._load_dedupe_annotations(
                        images,
                        cache_key=cache_key,
                        threshold=threshold,
                    )
                    cached_images = self._apply_dedupe_annotations(
                        cached_images, cached_annotations
                    )
                    streamed_images = [
                        self._enrich_image_info(dict(image), include_dimensions=False)
                        for image in cached_images
                    ]
                    final_state = self._build_dedupe_control_state(
                        status="completed",
                        processed_factors=len(images),
                        total_factors=len(images),
                        kept_factors=len(cached_images),
                        target_kept_limit=max(
                            normalized_target_kept, len(cached_images)
                        ),
                    )
                    self._emit_dedupe_progress(
                        task_id,
                        status="completed",
                        processed_factors=len(images),
                        total_factors=len(images),
                        kept_factors=len(cached_images),
                        target_kept_limit=max(
                            normalized_target_kept, len(cached_images)
                        ),
                        start_time=start_time,
                        message="命中去重缓存，已直接加载结果",
                        kept_images=streamed_images,
                        replace_gallery=True,
                    )
                    return cached_images, final_state

            conn = self._open_dedupe_progress_db()
            existing_snapshot = self._load_existing_dedupe_snapshot(
                conn,
                images,
                cache_key=dedupe_cache_key,
                threshold=threshold,
                target_kept_limit=normalized_target_kept,
            )
            if existing_snapshot is not None and not continue_requested:
                kept_images, snapshot_state, run_status = existing_snapshot
                if cache_key and kept_images:
                    self._save_cached_dedupe_result(
                        cache_key,
                        cache_signature,
                        [
                            str(image.get("relative_path"))
                            for image in kept_images
                            if image.get("relative_path")
                        ],
                        status=run_status,
                        state=snapshot_state,
                    )
                streamed_images = [
                    self._enrich_image_info(dict(image), include_dimensions=False)
                    for image in kept_images
                ]
                self._emit_dedupe_progress(
                    task_id,
                    status=run_status,
                    processed_factors=int(snapshot_state.get("processed_factors", 0)),
                    total_factors=int(snapshot_state.get("total_factors", len(images))),
                    kept_factors=len(kept_images),
                    target_kept_limit=normalized_target_kept,
                    start_time=start_time,
                    message="已加载本地保存的去重结果",
                    kept_images=streamed_images,
                    replace_gallery=bool(streamed_images),
                )
                return kept_images, snapshot_state

            run_lock = self._get_dedupe_run_lock(run_key)
            if not run_lock.acquire(blocking=False):
                concurrent_snapshot = self._load_existing_dedupe_snapshot(
                    conn,
                    images,
                    cache_key=dedupe_cache_key,
                    threshold=threshold,
                    target_kept_limit=normalized_target_kept,
                )
                if concurrent_snapshot is not None:
                    kept_images, snapshot_state, run_status = concurrent_snapshot
                    streamed_images = [
                        self._enrich_image_info(dict(image), include_dimensions=False)
                        for image in kept_images
                    ]
                    self._emit_dedupe_progress(
                        task_id,
                        status=run_status,
                        processed_factors=int(
                            snapshot_state.get("processed_factors", 0)
                        ),
                        total_factors=int(
                            snapshot_state.get("total_factors", len(images))
                        ),
                        kept_factors=len(kept_images),
                        target_kept_limit=normalized_target_kept,
                        start_time=start_time,
                        message="检测到后台已有同目录去重任务，已加载当前快照",
                        kept_images=streamed_images,
                        replace_gallery=bool(streamed_images),
                    )
                    return kept_images, snapshot_state
                raise RuntimeError("同目录已有高相关去重任务正在写入，请稍后继续")
            acquired_run_lock = True

            self._ensure_dedupe_run(
                conn,
                run_key=run_key,
                cache_key=dedupe_cache_key,
                signature=cache_signature,
                threshold=threshold,
                total_factors=len(images),
            )

            factor_cache: Dict[Tuple[str, str], Optional[object]] = {}
            correlation_cache: Dict[
                Tuple[Tuple[str, str], Tuple[str, str]], Optional[float]
            ] = {}
            processed_prefix, kept_images = self._load_resumable_dedupe_state(
                conn, run_key, images
            )
            last_processed_factors = processed_prefix
            all_image_map = {
                str(image.get("relative_path", "")): image for image in images
            }
            existing_annotations = self._load_dedupe_annotations(
                images,
                cache_key=dedupe_cache_key,
                threshold=threshold,
                conn=conn,
            )

            if processed_prefix > 0:
                kept_images = self._apply_dedupe_annotations(
                    kept_images, existing_annotations
                )
                restored_images = [
                    self._enrich_image_info(dict(image), include_dimensions=False)
                    for image in kept_images
                ]
                self._emit_dedupe_progress(
                    task_id,
                    status="running",
                    processed_factors=processed_prefix,
                    total_factors=len(images),
                    kept_factors=len(kept_images),
                    target_kept_limit=normalized_target_kept,
                    start_time=start_time,
                    message="已恢复上次进度，继续计算",
                    kept_images=restored_images,
                    replace_gallery=True,
                )

            if processed_prefix >= total_factors:
                final_state = self._build_dedupe_control_state(
                    status="completed",
                    processed_factors=processed_prefix,
                    total_factors=total_factors,
                    kept_factors=len(kept_images),
                    target_kept_limit=max(normalized_target_kept, len(kept_images)),
                )
                if cache_key:
                    self._save_cached_dedupe_result(
                        cache_key,
                        cache_signature,
                        [
                            str(image.get("relative_path"))
                            for image in kept_images
                            if image.get("relative_path")
                        ],
                        status="completed",
                        state=final_state,
                    )

                if conn is not None:
                    self._update_dedupe_run_status(conn, run_key, "completed")

                self._emit_dedupe_progress(
                    task_id,
                    status="completed",
                    processed_factors=processed_prefix,
                    total_factors=total_factors,
                    kept_factors=len(kept_images),
                    target_kept_limit=max(normalized_target_kept, len(kept_images)),
                    start_time=start_time,
                    message="已恢复全部去重结果",
                )
                return kept_images, final_state

            if len(kept_images) >= DEDUPE_MAX_KEPT_FACTORS:
                final_state = self._build_dedupe_control_state(
                    status="completed",
                    processed_factors=processed_prefix,
                    total_factors=total_factors,
                    kept_factors=len(kept_images),
                    target_kept_limit=DEDUPE_MAX_KEPT_FACTORS,
                )
                if cache_key:
                    self._save_cached_dedupe_result(
                        cache_key,
                        cache_signature,
                        [
                            str(image.get("relative_path"))
                            for image in kept_images
                            if image.get("relative_path")
                        ],
                        status="completed",
                        state=final_state,
                    )

                if conn is not None:
                    self._update_dedupe_run_status(conn, run_key, "completed")

                self._emit_dedupe_progress(
                    task_id,
                    status="completed",
                    processed_factors=processed_prefix,
                    total_factors=total_factors,
                    kept_factors=len(kept_images),
                    target_kept_limit=DEDUPE_MAX_KEPT_FACTORS,
                    start_time=start_time,
                    message="已达到 100 个保留因子的上限",
                )
                return kept_images[:DEDUPE_MAX_KEPT_FACTORS], final_state

            if (
                len(kept_images) >= normalized_target_kept
                and normalized_target_kept < DEDUPE_MAX_KEPT_FACTORS
            ):
                final_state = self._build_dedupe_control_state(
                    status="paused",
                    processed_factors=processed_prefix,
                    total_factors=total_factors,
                    kept_factors=len(kept_images),
                    target_kept_limit=normalized_target_kept,
                )
                if cache_key:
                    self._save_cached_dedupe_result(
                        cache_key,
                        cache_signature,
                        [
                            str(image.get("relative_path"))
                            for image in kept_images
                            if image.get("relative_path")
                        ],
                        status="paused",
                        state=final_state,
                    )
                if conn is not None:
                    self._update_dedupe_run_status(conn, run_key, "paused")

                self._emit_dedupe_progress(
                    task_id,
                    status="paused",
                    processed_factors=processed_prefix,
                    total_factors=total_factors,
                    kept_factors=len(kept_images),
                    target_kept_limit=normalized_target_kept,
                    start_time=start_time,
                    message=f"已保留 {len(kept_images)} 个低相关因子，等待继续计算",
                )
                return kept_images, final_state

            for index, image_info in enumerate(images, start=1):
                if index <= processed_prefix:
                    continue

                saved_comparisons = self._load_saved_factor_comparisons(
                    conn, run_key, index
                )
                should_hide = False
                max_corr: Optional[float] = None
                max_corr_with: Optional[str] = None

                for prior_image in images[: index - 1]:
                    prior_relative_path = str(prior_image.get("relative_path", ""))

                    if prior_relative_path in saved_comparisons:
                        corr_value = saved_comparisons[prior_relative_path]
                    else:
                        corr_value = self._calculate_mean_factor_correlation(
                            prior_image,
                            image_info,
                            factor_cache,
                            correlation_cache,
                        )
                        self._save_factor_comparison(
                            conn,
                            run_key=run_key,
                            factor_index=index,
                            prior_relative_path=prior_relative_path,
                            corr=corr_value,
                        )
                        saved_comparisons[prior_relative_path] = corr_value

                    corr_abs_value = abs(corr_value) if corr_value is not None else None

                    if corr_value is not None and (
                        max_corr is None or corr_abs_value > abs(max_corr)
                    ):
                        max_corr = float(corr_value)
                        max_corr_with = prior_relative_path

                    if corr_abs_value is not None and corr_abs_value > threshold:
                        should_hide = True

                image_info["dedupe_compared_count"] = index - 1
                image_info["dedupe_max_corr"] = max_corr
                image_info["dedupe_max_corr_with_relative_path"] = max_corr_with
                if max_corr_with:
                    target_image = all_image_map.get(max_corr_with)
                    if target_image is not None:
                        image_info["dedupe_max_corr_factor_name"] = (
                            self._get_factor_name_from_image(target_image)
                        )
                        image_info["dedupe_max_corr_factor_version"] = str(
                            target_image.get("factor_version", "")
                        )

                new_kept_image: Optional[Dict] = None
                if not should_hide:
                    kept_images.append(image_info)
                    new_kept_image = self._enrich_image_info(
                        dict(image_info),
                        include_dimensions=False,
                    )

                self._save_dedupe_factor_result(
                    conn,
                    run_key=run_key,
                    factor_index=index,
                    image_info=image_info,
                    is_kept=not should_hide,
                    max_corr=max_corr,
                    max_corr_with=max_corr_with,
                    compared_count=index - 1,
                )
                conn.commit()
                last_processed_factors = index

                self._emit_dedupe_progress(
                    task_id,
                    status="running",
                    processed_factors=index,
                    total_factors=len(images),
                    kept_factors=len(kept_images),
                    target_kept_limit=normalized_target_kept,
                    start_time=start_time,
                    current_factor=self._get_factor_name_from_image(image_info),
                    message="正在计算平均截面相关性",
                    new_kept_image=new_kept_image,
                )

                if len(kept_images) >= DEDUPE_MAX_KEPT_FACTORS:
                    final_state = self._build_dedupe_control_state(
                        status="completed",
                        processed_factors=index,
                        total_factors=total_factors,
                        kept_factors=len(kept_images),
                        target_kept_limit=DEDUPE_MAX_KEPT_FACTORS,
                    )
                    if cache_key:
                        self._save_cached_dedupe_result(
                            cache_key,
                            cache_signature,
                            [
                                str(image.get("relative_path"))
                                for image in kept_images
                                if image.get("relative_path")
                            ],
                            status="completed",
                            state=final_state,
                        )

                    if conn is not None:
                        self._update_dedupe_run_status(conn, run_key, "completed")

                    self._emit_dedupe_progress(
                        task_id,
                        status="completed",
                        processed_factors=index,
                        total_factors=total_factors,
                        kept_factors=len(kept_images),
                        target_kept_limit=DEDUPE_MAX_KEPT_FACTORS,
                        start_time=start_time,
                        message="已达到 100 个保留因子的上限，本轮计算结束",
                    )
                    return kept_images[:DEDUPE_MAX_KEPT_FACTORS], final_state

                if (
                    len(kept_images) >= normalized_target_kept
                    and normalized_target_kept < DEDUPE_MAX_KEPT_FACTORS
                ):
                    final_state = self._build_dedupe_control_state(
                        status="paused",
                        processed_factors=index,
                        total_factors=total_factors,
                        kept_factors=len(kept_images),
                        target_kept_limit=normalized_target_kept,
                    )
                    if cache_key:
                        self._save_cached_dedupe_result(
                            cache_key,
                            cache_signature,
                            [
                                str(image.get("relative_path"))
                                for image in kept_images
                                if image.get("relative_path")
                            ],
                            status="paused",
                            state=final_state,
                        )
                    if conn is not None:
                        self._update_dedupe_run_status(conn, run_key, "paused")

                    self._emit_dedupe_progress(
                        task_id,
                        status="paused",
                        processed_factors=index,
                        total_factors=total_factors,
                        kept_factors=len(kept_images),
                        target_kept_limit=normalized_target_kept,
                        start_time=start_time,
                        current_factor=self._get_factor_name_from_image(image_info),
                        message=f"已保留 {len(kept_images)} 个低相关因子，等待继续计算",
                    )
                    return kept_images, final_state

            logger.info(
                "高相关去重完成: 输入 %s 张, 保留 %s 张, 阈值 %.2f",
                len(images),
                len(kept_images),
                threshold,
            )

            final_state = self._build_dedupe_control_state(
                status="completed",
                processed_factors=len(images),
                total_factors=total_factors,
                kept_factors=len(kept_images),
                target_kept_limit=max(normalized_target_kept, len(kept_images)),
            )

            if cache_key:
                self._save_cached_dedupe_result(
                    cache_key,
                    cache_signature,
                    [
                        str(image.get("relative_path"))
                        for image in kept_images
                        if image.get("relative_path")
                    ],
                    status="completed",
                    state=final_state,
                )

            if conn is not None:
                self._update_dedupe_run_status(conn, run_key, "completed")

            self._emit_dedupe_progress(
                task_id,
                status="completed",
                processed_factors=len(images),
                total_factors=len(images),
                kept_factors=len(kept_images),
                target_kept_limit=max(normalized_target_kept, len(kept_images)),
                start_time=start_time,
                message="高相关去重计算完成",
            )

            return kept_images, final_state
        except Exception as e:
            logger.exception(
                "高相关去重中断 %s: %s", cache_key or task_id or "unknown", e
            )
            if conn is not None and run_key is not None:
                try:
                    self._update_dedupe_run_status(conn, run_key, "failed")
                except Exception:
                    logger.warning("更新去重运行状态失败: %s", run_key)

            partial_state = self._build_dedupe_control_state(
                status="failed",
                processed_factors=last_processed_factors,
                total_factors=total_factors,
                kept_factors=len(kept_images),
                target_kept_limit=normalized_target_kept,
            )
            if cache_key and kept_images:
                self._save_cached_dedupe_result(
                    cache_key,
                    cache_signature,
                    [
                        str(image.get("relative_path"))
                        for image in kept_images
                        if image.get("relative_path")
                    ],
                    status="failed",
                    state=partial_state,
                )
            streamed_images = [
                self._enrich_image_info(dict(image), include_dimensions=False)
                for image in kept_images
            ]
            self._emit_dedupe_progress(
                task_id,
                status="failed",
                processed_factors=last_processed_factors,
                total_factors=len(images),
                kept_factors=len(kept_images),
                target_kept_limit=normalized_target_kept,
                start_time=start_time,
                message=f"高相关去重中断，已保留当前结果: {e}",
                kept_images=streamed_images,
                replace_gallery=bool(streamed_images),
            )
            return kept_images, partial_state
        finally:
            if acquired_run_lock and run_lock is not None:
                run_lock.release()
            if conn is not None:
                conn.close()

    def get_folder_list(self) -> List[Dict]:
        """获取文件夹列表"""
        try:
            folders = []

            if not self.images_root.exists():
                return folders

            for item in self.images_root.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    folder_info = self._get_folder_info(item)
                    if folder_info:
                        if not folder_info.get("has_subfolders"):
                            continue
                        folders.append(folder_info)

            # 按日期降序排序
            folders.sort(key=lambda x: x.get("date", ""), reverse=True)
            return folders

        except Exception as e:
            logger.error(f"获取文件夹列表失败: {e}")
            raise

    def get_folder_info(self, folder_name: str) -> Optional[Dict]:
        """获取单个文件夹信息"""
        try:
            folder_path = self.images_root / folder_name
            if not folder_path.exists() or not folder_path.is_dir():
                return None

            return self._get_folder_info(folder_path)

        except Exception as e:
            logger.error(f"获取文件夹信息失败 {folder_name}: {e}")
            return None

    def get_subfolder_list(self, folder_name: str) -> List[Dict]:
        """获取子文件夹列表"""
        try:
            folder_path = self.images_root / folder_name
            if not folder_path.exists():
                return []

            subfolders = []
            for item in folder_path.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    subfolder_info = self._get_folder_info(item)
                    if subfolder_info:
                        subfolders.append(subfolder_info)

            # 按日期降序排序
            subfolders.sort(key=lambda x: x.get("date", ""), reverse=True)
            return subfolders

        except Exception as e:
            logger.error(f"获取子文件夹列表失败 {folder_name}: {e}")
            raise

    def get_image_list(
        self,
        folder_name: str,
        page: int = 1,
        per_page: int = 20,
        sort_by: str = "neu_ret",
        dedupe_similar: bool = False,
        dedupe_task_id: Optional[str] = None,
        dedupe_target_kept: Optional[int] = None,
        dedupe_continue: bool = False,
    ) -> Dict:
        """获取图片列表"""
        try:
            folder_path = self.images_root / folder_name
            if not folder_path.exists():
                return {"images": [], "total": 0, "page": page, "per_page": per_page}

            # 先仅收集轻量元数据，避免在分页前对所有图片解析尺寸和描述
            all_images = []
            for item in folder_path.rglob("*"):
                if item.is_file() and is_image_file(item):
                    image_info = self._build_basic_image_info(item)
                    if image_info:
                        all_images.append(image_info)

            # 收益率排序支持
            dedupe_source_images = None
            dedupe_state: Optional[Dict[str, object]] = None
            if sort_by == "neu_ret":
                all_images = self._sort_by_neu_ret(
                    folder_path,
                    all_images,
                    factor_version=self._get_factor_version_from_folder(folder_name),
                )
                dedupe_source_images = list(all_images)
                if dedupe_similar:
                    all_images, dedupe_state = self._dedupe_images_by_correlation(
                        all_images,
                        cache_key=f"single::{folder_name}",
                        task_id=dedupe_task_id,
                        target_kept_limit=dedupe_target_kept,
                        continue_requested=dedupe_continue,
                    )
            elif sort_by == "date" or sort_by == "time":  # 支持date和time两种参数
                all_images.sort(key=lambda x: x.get("date", ""), reverse=True)
            elif sort_by == "size":
                all_images.sort(key=lambda x: x.get("size", 0), reverse=True)
            else:
                # 默认按文件名排序
                all_images.sort(key=lambda x: x["name"].lower())

            result = self._build_image_result(all_images, page, per_page)
            result["images"] = [
                self._enrich_image_info(image) for image in result["images"]
            ]
            if sort_by == "neu_ret" and dedupe_source_images is not None:
                annotations = self._load_dedupe_annotations(
                    dedupe_source_images,
                    cache_key=f"single::{folder_name}",
                )
                result["images"] = self._apply_dedupe_annotations(
                    result["images"], annotations
                )
            if dedupe_state:
                result["dedupe_state"] = dedupe_state
            return result

        except Exception as e:
            logger.error(f"获取图片列表失败 {folder_name}: {e}")
            raise

    def get_file_path(self, relative_path: str) -> Optional[str]:
        """获取文件的完整路径"""
        try:
            full_path = self.images_root / relative_path

            # 安全检查：确保路径在images_root内
            if not str(full_path.resolve()).startswith(str(self.images_root.resolve())):
                logger.warning(f"路径访问被拒绝: {relative_path}")
                return None

            return str(full_path) if full_path.exists() else None

        except Exception as e:
            logger.error(f"获取文件路径失败 {relative_path}: {e}")
            return None

    def get_file_info(self, relative_path: str) -> Optional[Dict]:
        """获取文件信息"""
        try:
            full_path = self.get_file_path(relative_path)
            if not full_path:
                return None

            # 确保传入Path对象而不是字符串
            return get_file_info(Path(full_path))

        except Exception as e:
            logger.error(f"获取文件信息失败 {relative_path}: {e}")
            return None

    def search_files(
        self, query: str, folder: str = "", file_type: str = "all"
    ) -> List[Dict]:
        """搜索文件"""
        try:
            results = []
            search_path = self.images_root / folder if folder else self.images_root

            if not search_path.exists():
                return results

            query_lower = query.lower()

            for item in search_path.rglob("*"):
                if not item.is_file():
                    continue

                # 文件类型过滤
                if file_type == "image" and not is_image_file(item):
                    continue
                elif file_type == "svg" and item.suffix.lower() != ".svg":
                    continue

                # 名称匹配
                if query_lower in item.name.lower():
                    relative_path = item.relative_to(self.images_root)
                    file_info = get_file_info(item)
                    if file_info:
                        file_info["relative_path"] = str(relative_path)
                        # 添加父文件夹信息，便于在结果中显示来源
                        folder_path = item.parent.relative_to(self.images_root)
                        file_info["parent_folder"] = (
                            str(folder_path) if folder_path != Path(".") else ""
                        )
                        results.append(file_info)

            # 按相关性排序（名称匹配度）
            results.sort(key=lambda x: x["name"].lower().find(query_lower))
            return results[:100]  # 限制结果数量

        except Exception as e:
            logger.error(f"搜索文件失败 {query}: {e}")
            raise

    def search_images_in_folder(
        self, folder_name: str, query: str, page: int = 1, per_page: int = 20
    ) -> Dict:
        """在指定文件夹中搜索图片，支持多关键词AND搜索和屏蔽关键词"""
        try:
            results = []
            folder_path = self.images_root / folder_name

            if not folder_path.exists():
                return results

            # 解析查询字符串，支持屏蔽关键词语法 no:keyword
            include_keywords = []
            exclude_keywords = []

            for kw in query.split():
                kw = kw.strip()
                if not kw:
                    continue
                if kw.startswith("no:"):
                    # 屏蔽关键词
                    exclude_keyword = kw[3:].lower()
                    if exclude_keyword:
                        exclude_keywords.append(exclude_keyword)
                else:
                    # 包含关键词
                    include_keywords.append(kw.lower())

            # 如果没有包含关键字也没有排除关键字，则返回空结果
            if not include_keywords and not exclude_keywords:
                return results

            # 遍历文件夹中的所有图片
            for item in folder_path.rglob("*"):
                if not item.is_file() or not is_image_file(item):
                    continue

                # 关键词匹配：文件名必须包含所有包含关键词，且不能包含任何屏蔽关键词
                filename_lower = item.name.lower()
                # 如果有包含关键字，检查是否全部匹配
                include_match = not include_keywords or all(
                    keyword in filename_lower for keyword in include_keywords
                )
                # 如果有排除关键字，检查是否包含任何一个
                exclude_match = not any(
                    keyword in filename_lower for keyword in exclude_keywords
                )
                if include_match and exclude_match:
                    relative_path = item.relative_to(self.images_root)
                    file_info = get_file_info(item)
                    if file_info:
                        file_info["relative_path"] = str(relative_path)
                        file_info["folder"] = folder_name

                        # 添加图片描述信息
                        try:
                            folder_relative = str(
                                item.parent.relative_to(self.images_root)
                            )
                            description = self.get_image_description(
                                folder_relative, item.name
                            )
                            file_info["description"] = description
                            file_info["has_description"] = (
                                description is not None and description.strip() != ""
                            )
                        except Exception as e:
                            logger.debug(f"获取图片描述失败 {item}: {e}")
                            file_info["description"] = None
                            file_info["has_description"] = False

                        # 添加收益率信息（优先从SQLite数据库读取，其次从JSON文件读取）
                        try:
                            neu_ret_data = self._load_neu_ret_data(item.parent)
                            file_key = item.name.rsplit(".", 1)[0]
                            file_info["neu_ret"] = neu_ret_data.get(file_key, 0)
                        except Exception:
                            file_info["neu_ret"] = 0

                        # 添加匹配的关键词信息，用于排序
                        file_info["matched_keywords"] = include_keywords
                        results.append(file_info)

            # 按收益率降序排序
            results.sort(key=lambda x: x.get("neu_ret", 0), reverse=True)

            # 分页处理
            total = len(results)
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            paginated_results = results[start_idx:end_idx]

            return {
                "images": paginated_results,
                "total": total,
                "page": page,
                "per_page": per_page,
                "has_next": end_idx < total,
                "has_prev": page > 1,
            }

        except Exception as e:
            logger.error(f"在文件夹中搜索图片失败 {folder_name}, {query}: {e}")
            raise

    def search_images_in_subfolders(
        self, parent_folder: str, query: str, page: int = 1, per_page: int = 20
    ) -> Dict:
        """在指定父文件夹的所有子文件夹中搜索图片，支持多关键词AND搜索和屏蔽关键词"""
        try:
            results = []
            parent_path = self.images_root / parent_folder

            if not parent_path.exists():
                return results

            # 解析查询字符串，支持屏蔽关键词语法 no:keyword
            include_keywords = []
            exclude_keywords = []

            for kw in query.split():
                kw = kw.strip()
                if not kw:
                    continue
                if kw.startswith("no:"):
                    # 屏蔽关键词
                    exclude_keyword = kw[3:].lower()
                    if exclude_keyword:
                        exclude_keywords.append(exclude_keyword)
                else:
                    # 包含关键词
                    include_keywords.append(kw.lower())

            # 如果没有包含关键字也没有排除关键字，则返回空结果
            if not include_keywords and not exclude_keywords:
                return results

            # 遍历所有子文件夹
            for subfolder in parent_path.iterdir():
                if not subfolder.is_dir() or subfolder.name.startswith("."):
                    continue

                # 在子文件夹中搜索图片
                for item in subfolder.rglob("*"):
                    if not item.is_file() or not is_image_file(item):
                        continue

                    # 关键词匹配：文件名必须包含所有包含关键词，且不能包含任何屏蔽关键词
                    filename_lower = item.name.lower()
                    # 如果有包含关键字，检查是否全部匹配
                    include_match = not include_keywords or all(
                        keyword in filename_lower for keyword in include_keywords
                    )
                    # 如果有排除关键字，检查是否包含任何一个
                    exclude_match = not any(
                        keyword in filename_lower for keyword in exclude_keywords
                    )
                    if include_match and exclude_match:
                        relative_path = item.relative_to(self.images_root)
                        file_info = get_file_info(item)
                        if file_info:
                            file_info["relative_path"] = str(relative_path)
                            # 添加子文件夹信息
                            subfolder_path = item.parent.relative_to(parent_path)
                            file_info["subfolder"] = subfolder.name
                            file_info["subfolder_path"] = (
                                str(subfolder_path)
                                if subfolder_path != Path(".")
                                else ""
                            )
                            file_info["parent_folder"] = parent_folder

                            # 添加图片描述信息
                            try:
                                folder_relative = str(
                                    item.parent.relative_to(self.images_root)
                                )
                                description = self.get_image_description(
                                    folder_relative, item.name
                                )
                                file_info["description"] = description
                                file_info["has_description"] = (
                                    description is not None
                                    and description.strip() != ""
                                )
                            except Exception as e:
                                logger.debug(f"获取图片描述失败 {item}: {e}")
                                file_info["description"] = None
                                file_info["has_description"] = False

                            # 添加收益率信息
                            try:
                                neu_ret_file = item.parent / "neu_rets.json"
                                if neu_ret_file.exists():
                                    with open(neu_ret_file, "r", encoding="utf-8") as f:
                                        neu_ret_data = json.load(f)
                                        file_key = item.name.rsplit(".", 1)[0]
                                        file_info["neu_ret"] = neu_ret_data.get(
                                            file_key, 0
                                        )
                                else:
                                    file_info["neu_ret"] = 0
                            except Exception:
                                file_info["neu_ret"] = 0

                            # 添加匹配的关键词信息，用于排序
                            file_info["matched_keywords"] = include_keywords
                            results.append(file_info)

            # 按收益率降序排序
            results.sort(key=lambda x: x.get("neu_ret", 0), reverse=True)

            # 分页处理
            total = len(results)
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            paginated_results = results[start_idx:end_idx]

            return {
                "images": paginated_results,
                "total": total,
                "page": page,
                "per_page": per_page,
                "has_next": end_idx < total,
                "has_prev": page > 1,
            }

        except Exception as e:
            logger.error(f"在子文件夹中搜索图片失败 {parent_folder}, {query}: {e}")
            raise

    def get_unique_image_names_in_subfolders(self, parent_folder: str) -> List[str]:
        """获取父文件夹下所有子文件夹中的图片名称（去重）"""
        try:
            parent_path = self.images_root / parent_folder

            if not parent_path.exists():
                return []

            unique_names = set()

            # 遍历所有子文件夹
            for subfolder in parent_path.iterdir():
                if not subfolder.is_dir() or subfolder.name.startswith("."):
                    continue

                # 在子文件夹中收集图片名称
                for item in subfolder.rglob("*"):
                    if not item.is_file() or not is_image_file(item):
                        continue

                    unique_names.add(item.name)

            # 按名称排序并返回
            return sorted(list(unique_names), key=lambda x: x.lower())

        except Exception as e:
            logger.error(f"获取去重图片名称失败 {parent_folder}: {e}")
            raise

    def find_images_by_name_in_subfolders(
        self, parent_folder: str, image_name: str
    ) -> List[Dict]:
        """根据图片名称在所有子文件夹中查找匹配的图片"""
        try:
            results = []
            parent_path = self.images_root / parent_folder

            if not parent_path.exists():
                return results

            # 遍历所有子文件夹
            for subfolder in parent_path.iterdir():
                if not subfolder.is_dir() or subfolder.name.startswith("."):
                    continue

                # 在子文件夹中查找指定名称的图片
                for item in subfolder.rglob("*"):
                    if not item.is_file() or not is_image_file(item):
                        continue

                    # 精确匹配图片名称
                    if item.name == image_name:
                        relative_path = item.relative_to(self.images_root)
                        file_info = get_file_info(item)
                        if file_info:
                            file_info["relative_path"] = str(relative_path)
                            # 添加子文件夹信息
                            subfolder_path = item.parent.relative_to(parent_path)
                            file_info["subfolder"] = subfolder.name
                            file_info["subfolder_path"] = (
                                str(subfolder_path)
                                if subfolder_path != Path(".")
                                else ""
                            )
                            file_info["parent_folder"] = parent_folder

                            # 添加图片描述信息
                            try:
                                folder_relative = str(
                                    item.parent.relative_to(self.images_root)
                                )
                                description = self.get_image_description(
                                    folder_relative, item.name
                                )
                                file_info["description"] = description
                                file_info["has_description"] = (
                                    description is not None
                                    and description.strip() != ""
                                )
                            except Exception as e:
                                logger.debug(f"获取图片描述失败 {item}: {e}")
                                file_info["description"] = None
                                file_info["has_description"] = False

                            # 添加收益率信息
                            try:
                                neu_ret_file = item.parent / "neu_rets.json"
                                if neu_ret_file.exists():
                                    with open(neu_ret_file, "r", encoding="utf-8") as f:
                                        neu_ret_data = json.load(f)
                                        file_key = item.name.rsplit(".", 1)[0]
                                        file_info["neu_ret"] = neu_ret_data.get(
                                            file_key, 0
                                        )
                                else:
                                    file_info["neu_ret"] = 0
                            except Exception:
                                file_info["neu_ret"] = 0

                            results.append(file_info)

            # 按子文件夹名称排序
            results.sort(key=lambda x: x["subfolder"])
            return results

        except Exception as e:
            logger.error(f"根据名称查找图片失败 {parent_folder}, {image_name}: {e}")
            raise

    def delete_files(self, folder_name: str, file_paths: List[str]) -> Dict:
        """删除文件"""
        try:
            folder_path = self.images_root / folder_name
            if not folder_path.exists():
                return {"success": False, "message": "文件夹不存在"}

            deleted_files = []
            failed_files = []

            for file_path in file_paths:
                try:
                    full_path = folder_path / file_path

                    # 安全检查
                    if not str(full_path.resolve()).startswith(
                        str(folder_path.resolve())
                    ):
                        failed_files.append({"file": file_path, "error": "路径不安全"})
                        continue

                    if full_path.exists() and full_path.is_file():
                        full_path.unlink()
                        deleted_files.append(file_path)
                    else:
                        failed_files.append({"file": file_path, "error": "文件不存在"})

                except Exception as e:
                    failed_files.append({"file": file_path, "error": str(e)})

            return {
                "success": True,
                "deleted_count": len(deleted_files),
                "failed_count": len(failed_files),
                "deleted_files": deleted_files,
                "failed_files": failed_files,
            }

        except Exception as e:
            logger.error(f"删除文件失败: {e}")
            return {"success": False, "message": str(e)}

    def query_backup_files(self, query: str) -> List[Dict]:
        """查询备份文件"""
        try:
            # 这里可以根据实际需求实现备份文件查询逻辑
            # 例如从备份目录或数据库中查询
            results = []

            # 示例实现：在特定备份目录中搜索
            backup_paths = [
                Path.home() / "backup",
                Path.home() / "backups",
                self.images_root.parent / "backup",
            ]

            query_lower = query.lower()

            for backup_path in backup_paths:
                if not backup_path.exists():
                    continue

                for item in backup_path.rglob("*"):
                    if not item.is_file():
                        continue

                    if query_lower in item.name.lower():
                        file_info = get_file_info(item)
                        if file_info:
                            file_info["backup_path"] = str(backup_path)
                            file_info["relative_path"] = str(
                                item.relative_to(backup_path)
                            )
                            results.append(file_info)

            return results[:50]  # 限制结果数量

        except Exception as e:
            logger.error(f"查询备份文件失败 {query}: {e}")
            raise

    @cached_result(timeout=300)  # 缓存5分钟
    def _get_folder_info(self, folder_path: Path) -> Optional[Dict]:
        """获取文件夹详细信息"""
        try:
            if not folder_path.exists() or not folder_path.is_dir():
                return None

            # 统计文件
            image_count = 0
            total_size = 0

            for item in folder_path.rglob("*"):
                if item.is_file():
                    total_size += item.stat().st_size
                    if is_image_file(item):
                        image_count += 1

            # 获取修改时间
            mtime = folder_path.stat().st_mtime

            # 检查是否有描述文件
            description = self._get_folder_description(folder_path)

            return {
                "name": folder_path.name,
                "path": str(folder_path.relative_to(self.images_root)),
                "image_count": image_count,
                "size": total_size,
                "date": datetime.fromtimestamp(mtime).isoformat(),
                "description": description,
                "has_images": image_count > 0,
                "has_subfolders": any(
                    item.is_dir()
                    for item in folder_path.iterdir()
                    if not item.name.startswith(".")
                ),
            }

        except Exception as e:
            logger.error(f"获取文件夹信息失败 {folder_path}: {e}")
            return None

    def _get_folder_description(self, folder_path: Path) -> Optional[str]:
        """获取文件夹描述"""
        try:
            # 查找描述文件（folder_info.md为主，README.md等为备选）
            desc_files = [
                "folder_info.md",
                "README.md",
                "readme.md",
                "description.txt",
                "desc.txt",
            ]

            for desc_file in desc_files:
                desc_path = folder_path / desc_file
                if desc_path.exists() and desc_path.is_file():
                    with open(desc_path, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        return content

            return None

        except Exception as e:
            logger.debug(f"读取文件夹描述失败 {folder_path}: {e}")
            return None

    def _get_image_info(self, image_path: Path, base_path: Path) -> Optional[Dict]:
        """获取图片信息"""
        try:
            if not is_image_file(image_path):
                return None

            file_info = self._build_basic_image_info(image_path)
            if not file_info:
                return None

            return self._enrich_image_info(file_info)

        except Exception as e:
            logger.error(f"获取图片信息失败 {image_path}: {e}")
            return None

    def get_image_description(self, folder_name: str, filename: str) -> Optional[str]:
        """获取图片描述"""
        try:
            folder_path = self.images_root / folder_name
            return self._get_image_description_from_folder(folder_path, filename)

        except Exception as e:
            logger.error(f"获取图片描述失败 {folder_name}/{filename}: {e}")
            return None

    def set_image_description(
        self, folder_name: str, filename: str, description: str
    ) -> bool:
        """设置图片描述"""
        try:
            folder_path = self.images_root / folder_name

            # 使用隐藏的.descriptions.json文件
            desc_file = folder_path / ".descriptions.json"

            # 读取现有描述
            descriptions = {}
            if desc_file.exists():
                try:
                    with open(desc_file, "r", encoding="utf-8") as f:
                        descriptions = json.load(f)
                except (json.JSONDecodeError, OSError):
                    descriptions = {}

            # 更新或删除描述
            if description.strip():
                descriptions[filename] = description.strip()
            else:
                descriptions.pop(filename, None)

            # 保存更新的描述文件
            if descriptions:
                with open(desc_file, "w", encoding="utf-8") as f:
                    json.dump(descriptions, f, ensure_ascii=False, indent=2)
            else:
                # 如果没有任何描述，删除描述文件
                if desc_file.exists():
                    desc_file.unlink()

            # 清除缓存以确保立即更新
            cache_clear()

            return True

        except Exception as e:
            logger.error(f"设置图片描述失败 {folder_name}/{filename}: {e}")
            return False

    def get_described_images(self, folder_name: str) -> List[Dict]:
        """获取有描述的图片列表"""
        try:
            folder_path = self.images_root / folder_name
            described_images = []

            # 读取收益率数据
            neu_ret_file = folder_path / "neu_rets.json"
            neu_ret_data = {}
            if neu_ret_file.exists():
                try:
                    with open(neu_ret_file, "r", encoding="utf-8") as f:
                        neu_ret_data = json.load(f)
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning(f"无法读取neu_rets.json文件 {neu_ret_file}: {e}")

            # 主要方案：读取隐藏的.descriptions.json文件
            desc_file = folder_path / ".descriptions.json"
            if desc_file.exists():
                try:
                    with open(desc_file, "r", encoding="utf-8") as f:
                        descriptions = json.load(f)

                    for filename, description in descriptions.items():
                        image_path = folder_path / filename
                        if image_path.exists() and is_image_file(image_path):
                            image_info = self._get_image_info(image_path, folder_path)
                            if image_info:
                                image_info["description"] = description
                                # 添加收益率信息
                                file_key = filename.rsplit(".", 1)[0]
                                image_info["neu_ret"] = neu_ret_data.get(file_key, 0)
                                described_images.append(image_info)
                except (json.JSONDecodeError, OSError) as e:
                    logger.debug(f"读取隐藏描述文件失败 {desc_file}: {e}")

            # 备选方案：读取统一的descriptions.json文件
            if not described_images:
                desc_file_public = folder_path / "descriptions.json"
                if desc_file_public.exists():
                    try:
                        with open(desc_file_public, "r", encoding="utf-8") as f:
                            descriptions = json.load(f)

                        for filename, description in descriptions.items():
                            image_path = folder_path / filename
                            if image_path.exists() and is_image_file(image_path):
                                image_info = self._get_image_info(
                                    image_path, folder_path
                                )
                                if image_info:
                                    image_info["description"] = description
                                    # 添加收益率信息
                                    file_key = filename.rsplit(".", 1)[0]
                                    image_info["neu_ret"] = neu_ret_data.get(
                                        file_key, 0
                                    )
                                    described_images.append(image_info)
                    except (json.JSONDecodeError, OSError) as e:
                        logger.debug(f"读取统一描述文件失败 {desc_file_public}: {e}")

            # 按收益率从高到低排序
            described_images.sort(key=lambda x: x.get("neu_ret", 0), reverse=True)
            return described_images

        except Exception as e:
            logger.error(f"获取有描述图片列表失败 {folder_name}: {e}")
            return []

    def set_folder_description(self, folder_name: str, description: str) -> bool:
        """设置文件夹描述"""
        try:
            folder_path = self.images_root / folder_name
            if not folder_path.exists() or not folder_path.is_dir():
                return False

            # 保存到folder_info.md文件（优先使用）
            folder_info_path = folder_path / "folder_info.md"

            if description.strip():
                with open(folder_info_path, "w", encoding="utf-8") as f:
                    f.write(description.strip())
            else:
                # 删除空描述文件
                if folder_info_path.exists():
                    folder_info_path.unlink()

            # 清除相关缓存
            cache_clear()

            return True

        except Exception as e:
            logger.error(f"设置文件夹描述失败 {folder_name}: {e}")
            return False

    def _sort_by_neu_ret(
        self,
        folder_path: Path,
        images: List[Dict],
        factor_version: Optional[str] = None,
        dedupe_group: Optional[str] = None,
    ) -> List[Dict]:
        """根据收益率数据排序（优先从SQLite数据库读取，其次从JSON文件读取）"""
        try:
            # 加载收益率数据（优先从SQLite数据库，其次从JSON文件）
            neu_ret_data = self._load_neu_ret_data(folder_path)

            default_factor_version = factor_version or folder_path.name
            images = self._apply_neu_ret_metadata(
                images,
                neu_ret_data,
                default_factor_version=default_factor_version,
                dedupe_group=dedupe_group,
            )

            # 按neu_ret值从大到小排序，并在并列时稳定打破顺序
            images.sort(key=self._get_neu_ret_sort_key)
            return images

        except Exception as e:
            logger.error(f"收益率排序失败: {e}")
            # 如果排序失败，返回原始列表
            return images

    def get_images_cross_folders_by_return(
        self,
        parent_folder: str,
        page: int = 1,
        per_page: int = 20,
        dedupe_similar: bool = False,
        dedupe_task_id: Optional[str] = None,
        dedupe_target_kept: Optional[int] = None,
        dedupe_continue: bool = False,
    ) -> Dict:
        """跨子文件夹按收益率排序获取图片列表"""
        try:
            parent_path = self.images_root / parent_folder

            if not parent_path.exists():
                return {"images": [], "total": 0, "page": page, "per_page": per_page}

            all_images = []

            # 遍历所有子文件夹
            for subfolder in parent_path.iterdir():
                if not subfolder.is_dir() or subfolder.name.startswith("."):
                    continue

                # 读取子文件夹的收益率数据（优先从SQLite数据库读取，其次从JSON文件读取）
                neu_ret_data = self._load_neu_ret_data(subfolder)

                # 收集子文件夹中的所有图片
                for item in subfolder.rglob("*"):
                    if not item.is_file() or not is_image_file(item):
                        continue

                    image_info = self._build_basic_image_info(item)
                    if image_info:
                        # 添加子文件夹信息
                        image_info["subfolder"] = subfolder.name
                        subfolder_path = item.parent.relative_to(parent_path)
                        image_info["subfolder_path"] = str(subfolder_path)
                        image_info["parent_folder"] = parent_folder

                        # 添加收益率信息
                        file_key = item.name.rsplit(".", 1)[0]
                        image_info["factor_name"] = file_key
                        image_info["factor_version"] = subfolder.name
                        image_info["dedupe_group"] = parent_folder
                        image_info["neu_ret"] = neu_ret_data.get(file_key, 0)

                        all_images.append(image_info)

            # 按收益率从大到小排序，并在并列时稳定打破顺序
            all_images.sort(key=self._get_neu_ret_sort_key)
            dedupe_source_images = list(all_images)
            dedupe_state: Optional[Dict[str, object]] = None

            if dedupe_similar:
                all_images, dedupe_state = self._dedupe_images_by_correlation(
                    all_images,
                    cache_key=f"cross::{parent_folder}",
                    task_id=dedupe_task_id,
                    target_kept_limit=dedupe_target_kept,
                    continue_requested=dedupe_continue,
                )

            result = self._build_image_result(all_images, page, per_page)
            result["images"] = [
                self._enrich_image_info(image) for image in result["images"]
            ]
            annotations = self._load_dedupe_annotations(
                dedupe_source_images,
                cache_key=f"cross::{parent_folder}",
            )
            result["images"] = self._apply_dedupe_annotations(
                result["images"], annotations
            )
            if dedupe_state:
                result["dedupe_state"] = dedupe_state
            return result

        except Exception as e:
            logger.error(f"跨文件夹收益率排序失败 {parent_folder}: {e}")
            raise

    def search_images_in_selected_subfolders(
        self,
        parent_folder: str,
        query: str,
        selected_subfolders: List[str],
        page: int = 1,
        per_page: int = 20,
    ) -> Dict:
        """在指定父文件夹的选中子文件夹中搜索图片，支持多关键词AND搜索和屏蔽关键词"""
        try:
            results = []
            parent_path = self.images_root / parent_folder

            if not parent_path.exists():
                return results

            # 解析查询字符串，支持屏蔽关键词语法 no:keyword
            include_keywords = []
            exclude_keywords = []

            for kw in query.split():
                kw = kw.strip()
                if not kw:
                    continue
                if kw.startswith("no:"):
                    # 屏蔽关键词
                    exclude_keyword = kw[3:].lower()
                    if exclude_keyword:
                        exclude_keywords.append(exclude_keyword)
                else:
                    # 包含关键词
                    include_keywords.append(kw.lower())

            # 如果没有包含关键字也没有排除关键字，则返回空结果
            if not include_keywords and not exclude_keywords:
                return results

            # 遍历选中的子文件夹
            for subfolder_name in selected_subfolders:
                subfolder = parent_path / subfolder_name
                if (
                    not subfolder.exists()
                    or not subfolder.is_dir()
                    or subfolder.name.startswith(".")
                ):
                    continue

                # 在子文件夹中搜索图片
                for item in subfolder.rglob("*"):
                    if not item.is_file() or not is_image_file(item):
                        continue

                    # 关键词匹配：文件名必须包含所有包含关键词，且不能包含任何屏蔽关键词
                    filename_lower = item.name.lower()
                    # 如果有包含关键字，检查是否全部匹配
                    include_match = not include_keywords or all(
                        keyword in filename_lower for keyword in include_keywords
                    )
                    # 如果有排除关键字，检查是否包含任何一个
                    exclude_match = not any(
                        keyword in filename_lower for keyword in exclude_keywords
                    )
                    if include_match and exclude_match:
                        relative_path = item.relative_to(self.images_root)
                        file_info = get_file_info(item)
                        if file_info:
                            file_info["relative_path"] = str(relative_path)
                            # 添加子文件夹信息
                            subfolder_path = item.parent.relative_to(parent_path)
                            file_info["subfolder"] = subfolder.name
                            file_info["subfolder_path"] = (
                                str(subfolder_path)
                                if subfolder_path != Path(".")
                                else ""
                            )
                            file_info["parent_folder"] = parent_folder

                            # 添加图片描述信息
                            try:
                                folder_relative = str(
                                    item.parent.relative_to(self.images_root)
                                )
                                description = self.get_image_description(
                                    folder_relative, item.name
                                )
                                file_info["description"] = description
                                file_info["has_description"] = (
                                    description is not None
                                    and description.strip() != ""
                                )
                            except Exception as e:
                                logger.debug(f"获取图片描述失败 {item}: {e}")
                                file_info["description"] = None
                                file_info["has_description"] = False

                            # 添加收益率信息
                            try:
                                neu_ret_file = item.parent / "neu_rets.json"
                                if neu_ret_file.exists():
                                    with open(neu_ret_file, "r", encoding="utf-8") as f:
                                        neu_ret_data = json.load(f)
                                        file_key = item.name.rsplit(".", 1)[0]
                                        file_info["neu_ret"] = neu_ret_data.get(
                                            file_key, 0
                                        )
                                else:
                                    file_info["neu_ret"] = 0
                            except Exception:
                                file_info["neu_ret"] = 0

                            # 添加匹配的关键词信息，用于排序
                            file_info["matched_keywords"] = include_keywords
                            results.append(file_info)

            # 按收益率降序排序
            results.sort(key=lambda x: x.get("neu_ret", 0), reverse=True)

            # 分页处理
            total = len(results)
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            paginated_results = results[start_idx:end_idx]

            return {
                "images": paginated_results,
                "total": total,
                "page": page,
                "per_page": per_page,
                "has_next": end_idx < total,
                "has_prev": page > 1,
            }

        except Exception as e:
            logger.error(
                f"在选中子文件夹中搜索图片失败 {parent_folder}, {query}, {selected_subfolders}: {e}"
            )
            raise
