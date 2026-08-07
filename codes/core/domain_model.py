# -*- coding: utf-8 -*-
"""统一领域模型（动态化，跨行业泛化）。

自动发现数据目录下所有 CSV → 通用实体（表名→实体, 列→属性+类型推断）。
不硬编码任何实体类型：换行业（阀门/食品/机械/服务）只需替换数据目录 + schema。
纯标准库 csv，零依赖。
"""

import csv
from pathlib import Path

# 数值/日期/枚举列名提示(类型推断辅助)
_NUMERIC_HINTS = ("qty", "amount", "price", "cost", "stock", "pct", "age", "limit", "rank", "months", "days", "num")
_DATE_HINTS = ("date", "time", "day", "install", "create")
_ENUM_HINTS = ("status", "state", "type", "category", "kind", "flag", "grade")


def _infer_type(col: str, vals: list) -> str:
    """从列名 + 样本猜属性类型(number/date/enum/string)。"""
    low = col.lower()
    sample = [v for v in vals if v is not None and str(v).strip() != ""][:8]
    if not sample:
        return "string"
    # 数值: 列名提示或全数值
    if any(h in low for h in _NUMERIC_HINTS) or all(str(v).replace(".", "", 1).replace("-", "", 1).isdigit() for v in sample):
        return "number"
    if any(h in low for h in _DATE_HINTS) or all("-" in str(v) and str(v)[:4].isdigit() for v in sample):
        return "date"
    if any(h in low for h in _ENUM_HINTS) or (len(set(sample)) <= 8 and len(sample) >= 2):
        return "enum"
    return "string"


def _load_csv_generic(path: Path) -> list[dict]:
    """读取单个 CSV → dict 列表，数值列转 float/int。"""
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out = []
    for row in rows:
        d = dict(row)
        for col, val in d.items():
            if val is None or val == "":
                continue
            if _infer_type(col, [val]) == "number":
                try:
                    d[col] = int(float(val)) if float(val).is_integer() else float(val)
                except (ValueError, TypeError):
                    pass
        out.append(d)
    return out


def load_all(data_dir) -> dict[str, list[dict]]:
    """自动发现 data_dir 下所有 CSV → {表名: dict 列表}（跨行业通用）。

    任何企业数据目录（含任意表）都可加载，实体类型从表名+列自动推断。
    """
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        return {}
    result = {}
    for path in sorted(data_dir.glob("*.csv")):
        if path.name.startswith("."):
            continue
        name = path.stem  # 表名 = 文件名(去 .csv)
        try:
            result[name] = _load_csv_generic(path)
        except Exception:
            result[name] = []
    return result


def load_table(data_dir, table: str) -> list[dict]:
    """只加载单张表（增量更新用：数据变更只重读变动的表，不全部重建）。"""
    path = Path(data_dir) / f"{table}.csv"
    if not path.exists():
        return []
    return _load_csv_generic(path)


def entity_to_dict(entity) -> dict:
    """兼容旧接口：dict 实体直接返回。"""
    return dict(entity)


if __name__ == "__main__":
    import sys
    d = load_all(sys.argv[1] if len(sys.argv) > 1 else "../data")
    for k, v in d.items():
        print(k, len(v))
