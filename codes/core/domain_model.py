# -*- coding: utf-8 -*-
"""统一领域模型：定义 SME 决策本体相关的核心实体。

实体字段与 data/ 下各 CSV 表一一对应，用 dataclass 表达结构、
用 dict 承载数据，避免额外抽象。
纯标准库 csv，零依赖。
"""

import csv
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class Product:
    """产品。对应 products.csv(id,name,category,cost,price,supplier)。"""
    id: str
    name: str
    category: str
    cost: float
    price: float
    supplier: str


@dataclass
class Supplier:
    """供应商。对应 suppliers.csv(id,name,on_time_pct,quality_pct,price_rank)。"""
    id: str
    name: str
    on_time_pct: float
    quality_pct: float
    price_rank: int


@dataclass
class Inventory:
    """库存。对应 inventory.csv(product_id,stock,safety_stock,lead_time_days)。"""
    product_id: str
    stock: int
    safety_stock: int
    lead_time_days: int


@dataclass
class Sale:
    """销售。对应 sales.csv(product_id,date,qty)。"""
    product_id: str
    date: str
    qty: int


@dataclass
class Customer:
    """客户。对应 customers.csv(id,name,order_amount,aging_days,credit_limit)。"""
    id: str
    name: str
    order_amount: float
    aging_days: int
    credit_limit: float


@dataclass
class Order:
    """订单（派生数据，无固定 CSV，用于决策计算）。"""
    product_id: str
    qty: int
    amount: float


@dataclass
class Equipment:
    """设备。对应 equipment.csv(id,name,install_date,warranty_months,status)。"""
    id: str
    name: str
    install_date: str
    warranty_months: int
    status: str


# CSV 文件名 -> 目标实体类
_CSV_TO_ENTITY = {
    "products": Product,
    "suppliers": Supplier,
    "inventory": Inventory,
    "sales": Sale,
    "customers": Customer,
    "equipment": Equipment,
}


def _load_csv(data_dir: Path, name: str, entity) -> list[dict]:
    """读取单个 CSV，转成对应实体类的 dict 列表。"""
    path = data_dir / f"{name}.csv"
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out = []
    for row in rows:
        # 保留原始字符串字段，数值字段按列语义转换
        data = dict(row)
        fields = entity.__dataclass_fields__
        for field in fields:
            typ = fields[field].type
            val = data.get(field)
            if val is None or val == "":
                continue
            if typ in (int, float):
                data[field] = typ(val)
        out.append(data)
    return out


def load_all(data_dir) -> dict[str, list[dict]]:
    """读取 data/ 下全部 CSV，返回 {实体名: dict 列表} 映射。"""
    data_dir = Path(data_dir)
    return {
        name: _load_csv(data_dir, name, entity)
        for name, entity in _CSV_TO_ENTITY.items()
    }


def entity_to_dict(entity) -> dict:
    """dataclass 实体转 dict（辅助，避免处处手写）。"""
    return asdict(entity)


if __name__ == "__main__":
    # 自检：可直接运行 python domain_model.py data/
    import sys
    d = load_all(sys.argv[1] if len(sys.argv) > 1 else "../data")
    for k, v in d.items():
        print(k, len(v))
