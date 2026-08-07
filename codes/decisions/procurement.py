# -*- coding: utf-8 -*-
"""
采购决策模块（procurement）—— D4 比价 / D5 供应商绩效
======================================================

规则说明（纯标准库，零第三方依赖）：
  D4 比价：同一产品多个供应商时，比较综合成本，建议选择综合成本低者，
           并提示成本较高的供应商可议价/替代。
  D5 供应商绩效：评分 = on_time_pct×delivery权重 + quality_pct×quality权重 + 价格分×price权重
           权重取自 config/thresholds.json 的 procurement.score_weights（默认 price0.4/quality0.3/delivery0.3）。
           价格分由 price_rank 换算（rank=1 最优，逐档递减）。
           低分供应商（<70）预警。

入参：data(dict)，键含 'products'/'suppliers'，各为 list[dict]。
出参：list[dict]，每条含 {entity, action, reason, level}。
"""

import json
import os

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_THRESHOLDS_PATH = os.path.join(_PROJECT_ROOT, "config", "thresholds.json")

_DEFAULT_WEIGHTS = {"price": 0.4, "quality": 0.3, "delivery": 0.3}
_LOW_SCORE = 70.0  # 绩效预警线


def _load_weights():
    """读取 procurement.score_weights；缺失时返回默认权重。"""
    try:
        with open(_THRESHOLDS_PATH, "r", encoding="utf-8") as f:
            weights = json.load(f).get("procurement", {}).get("score_weights", {})
            return {**_DEFAULT_WEIGHTS, **weights}
    except (OSError, ValueError):
        return dict(_DEFAULT_WEIGHTS)


def _price_score(price_rank):
    """price_rank=1 最优(100分)，每落后一档减 10 分，最低 0。"""
    rank = max(1, int(price_rank or 1))
    return max(0.0, 100.0 - (rank - 1) * 10.0)


def _supplier_score(sup, weights):
    """供应商综合绩效评分（0-100）。"""
    on_time = float(sup.get("on_time_pct", 0))
    quality = float(sup.get("quality_pct", 0))
    price = _price_score(sup.get("price_rank"))
    return (
        on_time * float(weights.get("delivery", 0.3))
        + quality * float(weights.get("quality", 0.3))
        + price * float(weights.get("price", 0.4))
    )


def decide(data):
    """根据产品/供应商数据产出采购决策建议列表。"""
    products = data.get("products", [])
    suppliers = data.get("suppliers", [])
    weights = _load_weights()

    # 供应商 id -> 记录 映射
    sup_map = {s.get("id"): s for s in suppliers}

    # D5 供应商绩效：对每个供应商评分
    decisions = []
    for s in suppliers:
        score = _supplier_score(s, weights)
        if score < _LOW_SCORE:
            decisions.append({
                "entity": s.get("id"),
                "action": "关注/整改供应商",
                "reason": f"D5绩效: {s.get('name')} 评分={score:.1f} < 预警线{_LOW_SCORE:g}",
                "level": "预警",
            })

    # D4 比价：按产品名称分组，综合成本选低者
    by_name = {}
    for p in products:
        by_name.setdefault(p.get("name"), []).append(p)
    for name, group in by_name.items():
        if len(group) < 2:
            continue  # 单一供应商无需比价
        costed = sorted(group, key=lambda p: float(p.get("cost", 0)))
        best = costed[0]
        decisions.append({
            "entity": name,
            "action": "建议选择综合成本低者",
            "reason": (
                f"D4比价: {best.get('name')}(供应商{best.get('supplier')}, "
                f"成本{best.get('cost')}) 综合成本最低"
            ),
            "level": "建议",
        })
        # 提示成本更高的供应商可议价
        for p in costed[1:]:
            decisions.append({
                "entity": name,
                "action": "议价/替换供应商",
                "reason": (
                    f"D4比价: 供应商{p.get('supplier')} 成本{p.get('cost')} 高于最优，建议议价或替换"
                ),
                "level": "建议",
            })

    return decisions
