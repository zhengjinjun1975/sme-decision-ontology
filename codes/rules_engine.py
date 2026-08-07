#!/usr/bin/env python3
"""rules_engine.py — 声明式决策规则引擎（跨行业可配置）

通用运营公式(领域无关) + config/decisions.json 声明规则 → 决策建议。
换行业只需改 config/decisions.json(哪些表/哪些公式/哪些阈值)，零 Python。

指标(metric) → 通用公式：
  reorder        补货   reorder_level = (日均出库×提前期) + 安全库存, stock<→补货
  shortage       缺货   stock < 安全库存
  slow_turnover  呆滞   周转率 = 出库量/库存 < 阈值
  aging          账龄   客户账龄 > 阈值(告急)
  warranty       保修   设备保修过期/临期
  forecast       预测   近 window 期销售下滑 > 阈值
  price_compare  比价   同产品多供应商取低成本+议价
  supplier_score 供应商 准时率/合格率评分 < 阈值预警
"""

import json
import os
from datetime import date, datetime

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_rules(path=None):
    path = path or os.path.join(_PROJECT_ROOT, "config", "decisions.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_thresholds(module):
    path = os.path.join(_PROJECT_ROOT, "config", "thresholds.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f).get(module, {})
    except (OSError, ValueError):
        return {}


# ---------- 通用公式指标(领域无关) ----------
def _metric_reorder(data, rule, thr):
    rows = data.get(rule.get("table", "inventory"), [])
    join_key = rule.get("join_key", "product_id")
    sales = data.get(rule.get("sales_table", "sales"), [])
    out = []
    for r in rows:
        pid = r.get(join_key)
        stock = float(r.get("stock", 0))
        safety = float(r.get("safety_stock", thr.get("safety_stock", 14)))
        lead = float(r.get("lead_time_days", thr.get("lead_time_days", 7)))
        # 日均出库 = 该产品总销量 / 有销量天数
        sl = [s for s in sales if s.get(join_key) == pid and s.get("qty")]
        daily = (sum(float(s.get("qty", 0)) for s in sl) / len({s.get("date") for s in sl})) if sl else 0.0
        rl = daily * lead + safety
        if stock < rl:
            out.append({"entity": pid, "action": rule.get("action", "补货"),
                        "reason": rule.get("reason", f"stock={stock:g} < reorder={rl:g}").format(stock=stock, reorder_level=rl),
                        "level": rule.get("level", "建议")})
    return out


def _metric_shortage(data, rule, thr):
    out = []
    for r in data.get(rule.get("table", "inventory"), []):
        pid = r.get("product_id")
        stock = float(r.get("stock", 0))
        safety = float(r.get("safety_stock", thr.get("safety_stock", 14)))
        if stock < safety:
            out.append({"entity": pid, "action": rule.get("action", "缺货预警"),
                        "reason": f"stock={stock:g} < safety={safety:g}", "level": rule.get("level", "预警")})
    return out


def _metric_slow_turnover(data, rule, thr):
    out = []
    sales = data.get("sales", [])
    threshold = float(thr.get("slow_turnover", 1.0))
    for r in data.get("inventory", []):
        pid = r.get("product_id")
        stock = float(r.get("stock", 0))
        if stock <= 0:
            continue
        sl = [s for s in sales if s.get("product_id") == pid and s.get("qty")]
        out_qty = sum(float(s.get("qty", 0)) for s in sl)
        turnover = out_qty / stock
        if turnover < threshold:
            out.append({"entity": pid, "action": rule.get("action", "呆滞处理"),
                        "reason": f"周转率={turnover:.3f} < 阈值{threshold:g}", "level": rule.get("level", "预警")})
    return out


def _metric_aging(data, rule, thr):
    out = []
    aging_thr = int(thr.get("aging_warn", 60))
    critical_thr = int(thr.get("aging_critical", 90))
    for c in data.get(rule.get("table", "customers"), []):
        cid = c.get("id")
        aging = float(c.get("aging_days", 0))
        credit = float(c.get("credit_limit", 0))
        amount = float(c.get("order_amount", 0))
        if aging >= critical_thr:
            out.append({"entity": cid, "action": "催收告急",
                        "reason": f"账龄{aging:g}天≥{critical_thr}天", "level": "告急"})
        elif aging >= aging_thr:
            out.append({"entity": cid, "action": "催收预警",
                        "reason": f"账龄{aging:g}天≥{aging_thr}天", "level": "预警"})
        elif amount > credit:
            out.append({"entity": cid, "action": "超信用额度",
                        "reason": f"欠款{amount:g}>额度{credit:g}", "level": "预警"})
    return out


def _metric_warranty(data, rule, thr):
    out = []
    warn = int(thr.get("warranty_warn_days", 60))
    today = date.today()
    for e in data.get(rule.get("table", "equipment"), []):
        eid = e.get("id")
        install = e.get("install_date", "")
        months = int(e.get("warranty_months", 0))
        status = e.get("status", "")
        if status == "待修":
            out.append({"entity": eid, "action": "维护告急", "reason": f"状态: 待修", "level": "告急"})
            continue
        try:
            end = date.fromisoformat(install[:10])
        except (ValueError, TypeError):
            continue
        from datetime import timedelta
        end = end + timedelta(days=months * 30)
        left = (end - today).days
        if left < 0:
            out.append({"entity": eid, "action": "保修过期", "reason": f"保修已于{end}到期", "level": "预警"})
        elif left <= warn:
            out.append({"entity": eid, "action": "保修临期", "reason": f"保修{left}天后到期", "level": "建议"})
    return out


def _metric_forecast(data, rule, thr):
    out = []
    window = int(thr.get("forecast_window", 4))
    drop = float(thr.get("forecast_drop", 0.3))
    sales = data.get("sales", [])
    # 按产品聚合销售, 最近window期 vs 更早一期
    from collections import defaultdict
    by_p = defaultdict(list)
    for s in sales:
        by_p[s.get("product_id")].append(s)
    for pid, rows in by_p.items():
        rows.sort(key=lambda x: x.get("date", ""))
        if len(rows) < 2:
            continue
        half = max(1, len(rows) // 2)
        recent = sum(float(r.get("qty", 0)) for r in rows[-half:])
        earlier = sum(float(r.get("qty", 0)) for r in rows[:half])
        if earlier > 0 and (earlier - recent) / earlier > drop:
            out.append({"entity": pid, "action": "销售下滑预警",
                        "reason": f"近期销量比前期降{(earlier-recent)/earlier*100:.0f}%", "level": "预警"})
    return out


def _metric_price_compare(data, rule, thr):
    out = []
    # 同产品多供应商: 比价取低成本(products.supplier 关联 suppliers)
    for p in data.get("products", []):
        sid = p.get("supplier")
        sup = next((s for s in data.get("suppliers", []) if s.get("id") == sid), None)
        if sup:
            out.append({"entity": p.get("id"), "action": "比价提示",
                        "reason": f"产品{p.get('id')} 供应商{sup.get('name')} 价格{sup.get('price_rank','')}",
                        "level": "建议"})
    return out


def _metric_supplier_score(data, rule, thr):
    out = []
    score_thr = float(thr.get("supplier_score", 70))
    for s in data.get("suppliers", []):
        on_time = float(s.get("on_time_pct", 100))
        quality = float(s.get("quality_pct", 100))
        score = on_time * 0.5 + quality * 0.5
        if score < score_thr:
            out.append({"entity": s.get("id"), "action": "供应商绩效预警",
                        "reason": f"评分{score:.1f}<阈值{score_thr:g}(准时{on_time:g}/合格{quality:g})",
                        "level": "预警"})
    return out


_METRICS = {
    "reorder": _metric_reorder, "shortage": _metric_shortage, "slow_turnover": _metric_slow_turnover,
    "aging": _metric_aging, "warranty": _metric_warranty, "forecast": _metric_forecast,
    "price_compare": _metric_price_compare, "supplier_score": _metric_supplier_score,
}


def run_rules(data, rules=None, enabled=None):
    """执行规则 → {模块: 决策建议列表}。enabled: 启用的模块列表(来自 deployment.json)。"""
    rules = rules or _load_rules()
    result = {}
    for module, cfg in rules.items():
        if enabled and module not in enabled:
            continue
        if not isinstance(cfg, dict):
            continue
        decisions = []
        thr = _load_thresholds(module)
        for rule in cfg.get("rules", []):
            fn = _METRICS.get(rule.get("metric"))
            if fn:
                decisions.extend(fn(data, rule, thr))
        result[module] = decisions
    return result
