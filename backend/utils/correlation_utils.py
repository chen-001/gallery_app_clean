"""
因子相关性计算工具
"""
import os
import json
from pathlib import Path
from typing import List, Dict, Optional
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

FACTOR_DATA_ROOT = "/nas197/user_home_unsafe/chenzongwei/factor_data"
HISTORY_DIR = Path.home() / ".gallery"
HISTORY_FILE = HISTORY_DIR / "correlation_history.json"


def load_factor_data(factor_version: str, factor_name: str) -> Optional[pd.DataFrame]:
    """读取单个因子数据"""
    file_path = os.path.join(FACTOR_DATA_ROOT, factor_version, f"{factor_name}.parquet")
    if not os.path.exists(file_path):
        logger.warning(f"因子数据文件不存在: {file_path}")
        return None

    df = pd.read_parquet(file_path)
    if "date" in df.columns:
        df = df.set_index("date")
    return df


def get_abs(df: pd.DataFrame) -> pd.DataFrame:
    """均值距离化：计算因子与截面均值的距离的绝对值"""
    return np.abs((df.T - df.T.mean()).T)


def is_fold_factor(name: str) -> bool:
    """判断因子是否为fold类型"""
    return name.endswith("_fold")


def get_original_name(fold_name: str) -> str:
    """获取fold因子的原始名称（去掉_fold后缀）"""
    if fold_name.endswith("_fold"):
        return fold_name[:-5]
    return fold_name


def load_and_process_factor(
    factor_version: str, factor_name: str
) -> Optional[pd.DataFrame]:
    """
    读取并处理因子数据

    - 普通因子：直接读取
    - _fold结尾因子：读取原始因子，然后rank(axis=1) + get_abs处理
    """
    if is_fold_factor(factor_name):
        # fold因子：读取原始因子，处理后返回
        original_name = get_original_name(factor_name)
        df = load_factor_data(factor_version, original_name)
        if df is not None:
            # rank(axis=1) + get_abs 处理
            df = get_abs(df.rank(axis=1))
        return df
    else:
        # 普通因子：直接读取
        return load_factor_data(factor_version, factor_name)


def calculate_correlation_matrix(factor_version: str, factor_names: List[str]) -> Dict:
    """
    计算多个因子之间的相关性矩阵

    Args:
        factor_version: 因子版本（子文件夹名）- 仅作为默认值，优先使用 factor_list
        factor_names: 因子名称列表 - 仅作为默认值，优先使用 factor_list

    Returns:
        包含相关性矩阵和元信息的字典

    Note:
        - 普通因子：需要rank(axis=1)后再计算相关性
        - _fold结尾因子：读取原始因子后用rank+get_abs处理，已等效于rank
    """
    # 读取并处理所有因子数据
    factor_data = {}
    missing_factors = []

    for name in factor_names:
        df = load_and_process_factor(factor_version, name)
        if df is not None:
            factor_data[name] = df
        else:
            missing_factors.append(name)

    if not factor_data:
        return {
            "success": False,
            "message": "没有找到任何有效的因子数据",
            "missing_factors": missing_factors,
        }

    # 计算两两相关性
    valid_names = list(factor_data.keys())
    n = len(valid_names)
    corr_matrix = np.zeros((n, n))

    for i in range(n):
        corr_matrix[i, i] = 1.0
        for j in range(i + 1, n):
            df1 = factor_data[valid_names[i]]
            df2 = factor_data[valid_names[j]]

            # 对齐日期
            common_dates = df1.index.intersection(df2.index)
            if len(common_dates) == 0:
                corr_matrix[i, j] = np.nan
                corr_matrix[j, i] = np.nan
                continue

            df1_aligned = df1.loc[common_dates]
            df2_aligned = df2.loc[common_dates]

            # 根据因子类型决定是否需要rank
            # fold因子已经过rank+get_abs处理，普通因子需要rank
            if is_fold_factor(valid_names[i]):
                df1_processed = df1_aligned
            else:
                df1_processed = df1_aligned.rank(axis=1)

            if is_fold_factor(valid_names[j]):
                df2_processed = df2_aligned
            else:
                df2_processed = df2_aligned.rank(axis=1)

            # 每天计算相关性，然后取时间序列均值
            daily_corr = df1_processed.corrwith(df2_processed, axis=1)
            mean_corr = daily_corr.mean()

            corr_matrix[i, j] = mean_corr
            corr_matrix[j, i] = mean_corr

    return {
        "success": True,
        "factor_version": factor_version,
        "factor_names": valid_names,
        "correlation_matrix": corr_matrix.tolist(),
        "missing_factors": missing_factors,
    }


def calculate_correlation_matrix_v2(factor_list: List[Dict]) -> Dict:
    """
    计算多个因子之间的相关性矩阵（支持跨版本）

    Args:
        factor_list: 因子列表，每个元素为 {name: str, version: str}

    Returns:
        包含相关性矩阵和元信息的字典
    """
    if not factor_list or len(factor_list) < 2:
        return {
            "success": False,
            "message": "至少需要2个因子",
        }

    # 读取并处理所有因子数据
    factor_data = {}
    missing_factors = []

    for item in factor_list:
        name = item["name"]
        version = item["version"]
        df = load_and_process_factor(version, name)
        if df is not None:
            factor_data[f"{name}@{version}"] = df
        else:
            missing_factors.append(f"{name}@{version}")

    if not factor_data:
        return {
            "success": False,
            "message": "没有找到任何有效的因子数据",
            "missing_factors": missing_factors,
        }

    # 计算两两相关性
    valid_keys = list(factor_data.keys())
    n = len(valid_keys)
    corr_matrix = np.zeros((n, n))

    for i in range(n):
        corr_matrix[i, i] = 1.0
        for j in range(i + 1, n):
            df1 = factor_data[valid_keys[i]]
            df2 = factor_data[valid_keys[j]]

            # 对齐日期
            common_dates = df1.index.intersection(df2.index)
            if len(common_dates) == 0:
                corr_matrix[i, j] = np.nan
                corr_matrix[j, i] = np.nan
                continue

            df1_aligned = df1.loc[common_dates]
            df2_aligned = df2.loc[common_dates]

            # 根据因子类型决定是否需要rank
            # fold因子已经过rank+get_abs处理，普通因子需要rank
            key_i = valid_keys[i]
            key_j = valid_keys[j]
            # 从key中提取因子名（去掉@version后缀）
            name_i = key_i.split("@")[0]
            name_j = key_j.split("@")[0]

            if is_fold_factor(name_i):
                df1_processed = df1_aligned
            else:
                df1_processed = df1_aligned.rank(axis=1)

            if is_fold_factor(name_j):
                df2_processed = df2_aligned
            else:
                df2_processed = df2_aligned.rank(axis=1)

            # 每天计算相关性，然后取时间序列均值
            daily_corr = df1_processed.corrwith(df2_processed, axis=1)
            mean_corr = daily_corr.mean()

            corr_matrix[i, j] = mean_corr
            corr_matrix[j, i] = mean_corr

    # 提取版本信息（用于显示）
    versions = list(set(item["version"] for item in factor_list))

    return {
        "success": True,
        "factor_version": versions[0]
        if len(versions) == 1
        else f"混合版本({len(versions)}个)",
        "factor_names": valid_keys,  # 使用 name@version 格式
        "correlation_matrix": corr_matrix.tolist(),
        "missing_factors": missing_factors,
    }


def get_correlation_history() -> List[Dict]:
    """获取相关性分析历史记录"""
    if not HISTORY_FILE.exists():
        return []

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"读取历史记录失败: {e}")
        return []


def save_correlation_history(record: Dict) -> bool:
    """保存相关性分析记录到历史"""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    history = get_correlation_history()
    history.insert(0, record)

    # 限制历史记录数量
    if len(history) > 50:
        history = history[:50]

    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"保存历史记录失败: {e}")
        return False


def delete_correlation_history(record_id: str) -> bool:
    """删除指定的历史记录"""
    history = get_correlation_history()
    new_history = [r for r in history if r.get("id") != record_id]

    if len(new_history) == len(history):
        return False

    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(new_history, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"删除历史记录失败: {e}")
        return False
