# -*- coding: utf-8 -*-
"""
库存决策模块（inventory）—— D1 补货 / D2 缺货 / D3 呆滞
=======================================================

规则说明（纯标准库，零第三方依赖）：
  D1 补货：reorder_level = (日均出库 × lead_time_days) + safety_stock
          当前 stock < reorder_level  → 建议补货
  D2 缺货：stock < safety_stock      → 预警缺货
  D3 呆滞：周转率 < slow_turnover 阈值 → 预警呆滞（周转率 = 销售出库量 / 当前库存）

入参：data(dict)，由 domain_model.load_all() 加载，键含 'inventory'/'sales'/'products'，
      各为 list[dict]。阈值从 config/thresholds.json 的 inventory 段读取。
出参：list[dict]，每条含 {entity, action, reason, level}，
      level 取值为 建议 / 预警 / 告急。
"""

import json
import os

# 项目根目录 = 本文件上三级（codes/decisions/xxx.py -> 项目根）
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_THRESHOLDS_PATH = os.path.join(_PROJECT_ROOT, "config", "thresholds.json")


def _load_thresholds():
    """读取 config/thresholds.json 的 inventory 段；缺失时返回默认值。"""
    defaults = {
        "safety_stock_days": 14,
        "reorder_lead_time_days": 7,
        "slow_turnover": 1.0,
    }
    try:
        with open(_THRESHOLDS_PATH, "r", encoding="utf-8") as f:
            return {**defaults, **json.load(f).get("inventory", {})}
    except (OSError, ValueError):
        return defaults


def _daily_avg_outbound(sales, product_id):
    """按销售记录统计某产品日均出库量（总销量 / 有销量的天数）。"""
    rows = [s for s in sales if s.get("product_id") == product_id and s.get("qty")]
    if not rows:
        return 0.0
    total = sum(float(r.get("qty", 0)) for r in rows)
    days = len({r.get("date") for r in rows if r.get("date")})
    return total / days if days else 0.0


def decide(data):
    """根据库存/销售数据产出库存决策建议列表。"""
    inventory = data.get("inventory", [])
    sales = data.get("sales", [])
    thr = _load_thresholds()
    slow_turnover = float(thr.get("slow_turnover", 1.0))

    decisions = []
    for inv in inventory:
        pid = inv.get("product_id")
        stock = float(inv.get("stock", 0))
        safety_stock = float(inv.get("safety_stock", thr.get("safety_stock_days", 14)))
        lead_time = float(inv.get("lead_time_days", thr.get("reorder_lead_time_days", 7)))

        # D1 补货
        reorder_level = (_daily_avg_outbound(sales, pid) * lead_time) + safety_stock
        if stock < reorder_level:
            decisions.append({
                "entity": pid,
                "action": "补货",
                "reason": (
                    f"D1补货: stock={stock:g} < reorder_level={reorder_level:g} "
                    f"(日均出库{_daily_avg_outbound(sales, pid):g}×提前期{lead_time:g}+安全库存{safety_stock:g})"
                ),
                "level": "建议",
            })

        # D2 缺货
        if stock < safety_stock:
            decisions.append({
                "entity": pid,
                "action": "缺货预警",
                "reason": f"D2缺货: stock={stock:g} < safety_stock={safety_stock:g}",
                "level": "预警",
            })

        # D3 呆滞
        if stock > 0:
            turnover = _daily_avg_outbound(sales, pid) / stock
            if turnover < slow_turnover:
                decisions.append({
                    "entity": pid,
                    "action": "呆滞处理",
                    "reason": (
                        f"D3呆滞: 周转率={turnover:.3f} < 阈值{slow_turnover:g}"
                    ),
                    "level": "预警",
                })

    return decisions
