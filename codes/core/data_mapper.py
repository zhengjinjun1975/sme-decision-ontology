# -*- coding: utf-8 -*-
"""多源数据接入：把不同来源的数据统一成 list[dict]。

支持 CSV / SQLite / Excel(可选 openpyxl)，并做去重与空值清洗。
纯标准库 csv / sqlite3，Excel 仅在安装了 openpyxl 时可用。
"""

import csv
import sqlite3


def load_csv(path) -> list[dict]:
    """读取 CSV 文件，返回字典列表。自动处理 BOM 与表头。"""
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_sqlite(path, table) -> list[dict]:
    """读取 SQLite 数据库某张表的全部行，返回字典列表。"""
    if not table or not table.replace("_", "").isalnum():  # 表名白名单(安全加固)
        raise ValueError(f"非法表名: {table!r}")
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(f'SELECT * FROM "{table}"')
        return [dict(r) for r in cur.fetchall()]


def load_excel(path) -> list[dict]:
    """读取 Excel(.xlsx) 第一个工作表，返回字典列表。

    依赖可选库 openpyxl；未安装时给出清晰错误提示。
    """
    try:
        from openpyxl import load_workbook
    except ImportError:
        raise ImportError(
            "读取 Excel 需要 openpyxl，请先安装：pip install openpyxl"
        )
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    header = next(rows, None)  # 第一行为表头
    if header is None:
        return []
    return [
        {h: v for h, v in zip(header, row) if h is not None}
        for row in rows
    ]


def clean(rows, dedup_keys=()):
    """清洗数据：按 dedup_keys 去重（保留首个），丢弃全空行与纯空值字段。

    返回新的 list[dict]。
    """
    seen = set()
    out = []
    for row in rows:
        # 过滤掉键为空的项
        data = {k: v for k, v in row.items() if k is not None and v is not None}
        if not data:                      # 全空行，丢弃
            continue
        if dedup_keys:                    # 去重
            key = tuple(str(data.get(k)) for k in dedup_keys)
            if key in seen:
                continue
            seen.add(key)
        out.append(data)
    return out


if __name__ == "__main__":
    # 自检：python data_mapper.py <csv路径>
    import sys
    rows = load_csv(sys.argv[1])
    print(clean(rows, dedup_keys=[sys.argv[2] if len(sys.argv) > 2 else "id"])[:3])
