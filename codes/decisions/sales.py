# -*- coding: utf-8 -*-
"""
销售决策模块（sales）—— D6 销售预测 / D7 客户信用
==================================================

规则说明（纯标准库，零第三方依赖）：
  D6 销售预测：对近 forecast_window 期销量做移动平均，预测下期销量；
               销量下滑超阈值时提示关注。窗口取 config/thresholds.json 的 sales.forecast_window。
  D7 客户信用：aging_days > credit_aging_days      → 高风险/催收（告急）
               order_amount > credit_limit         → 超信用额度（预警）

入参：data(dict)，键含 'sales'/'customers'，各为 list[dict]。
出参：list[dict]，每条含 {entity, action, reason, level}。
"""

import json
import os

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_THRESHOLDS_PATH = os.path.join(_PROJECT_ROOT, "config", "thresholds.json")

_DECLINE_RATIO = 0.3  # 下期预测较上期下滑 30% 视为下滑


def _load_sales_thresholds():
    """读取 sales 段阈值；缺失时返回默认值。"""
    defaults = {"credit_aging_days": 60, "forecast_window": 30}
    try:
        with open(_THRESHOLDS_PATH, "r", encoding="utf-8") as f:
            return {**defaults, **json.load(f).get("sales", {})}
    except (OSError, ValueError):
        return defaults


def _moving_average(rows, window):
    """对销量序列做简单移动平均，返回最后一个窗口的平均销量。"""
    qtys = [float(r.get("qty", 0)) for r in rows]
    if not qtys:
        return 0.0, 0.0
    prev = qtys[-window - 1:-1] if len(qtys) > window else qtys[:-1] if len(qtys) > 1 else []
    last = qtys[-window:]
    avg_prev = sum(prev) / len(prev) if prev else 0.0
    avg_last = sum(last) / len(last)
    return avg_last, avg_prev


def decide(data):
    """根据销售/客户数据产出销售决策建议列表。"""
    sales = data.get("sales", [])
    customers = data.get("customers", [])
    thr = _load_sales_thresholds()
    window = int(thr.get("forecast_window", 30))
    credit_aging = float(thr.get("credit_aging_days", 60))

    decisions = []

    # D6 销售预测：按产品分组做移动平均
    by_product = {}
    for s in sales:
        by_product.setdefault(s.get("product_id"), []).append(s)
    for pid, rows in by_product.items():
        avg, prev_avg = _moving_average(rows, window)
        if avg > 0:
            reason = f"D6预测: {pid} 近{window}期销量移动平均={avg:.2f}"
            if prev_avg > 0 and avg < prev_avg * (1 - _DECLINE_RATIO):
                decisions.append({
                    "entity": pid,
                    "action": "关注销量下滑",
                    "reason": reason + f"，较前期下滑>{(1 - _DECLINE_RATIO) * 100:.0f}%",
                    "level": "预警",
                })
            else:
                decisions.append({
                    "entity": pid,
                    "action": "按预测排产/备货",
                    "reason": reason,
                    "level": "建议",
                })

    # D7 客户信用
    for c in customers:
        aging = float(c.get("aging_days", 0))
        order_amount = float(c.get("order_amount", 0))
        credit_limit = float(c.get("credit_limit", 0))
        if aging > credit_aging:
            decisions.append({
                "entity": c.get("id"),
                "action": "催收/高风险管控",
                "reason": (
                    f"D7信用: {c.get('name')} 账龄{aging:g}天 > 阈值{credit_aging:g}天"
                ),
                "level": "告急",
            })
        if credit_limit > 0 and order_amount > credit_limit:
            decisions.append({
                "entity": c.get("id"),
                "action": "超额度预警/停单",
                "reason": (
                    f"D7信用: {c.get('name')} 订单金额{order_amount:g} > "
                    f"信用额度{credit_limit:g}"
                ),
                "level": "预警",
            })

    return decisions
