#!/usr/bin/env python3
"""action.py — 决策到行动闭环

把决策建议变成可执行的行动项：采购单草稿 / 预警清单 / 维护工单 / 催收清单。
决策不落地就是报表，会弃用——这是核心。

用法:
  from action import suggestions_to_actions, export_actions
  actions = suggestions_to_actions(all_suggestions, data)
  export_actions(actions, "actions.csv")
"""
import os
import json
import datetime

ACTION_TYPES = {
    "补货": "purchase_order",       # 采购单草稿
    "呆滞处理": "slow_moving",       # 呆滞处置建议
    "缺货预警": "shortage_alert",   # 缺货预警
    "按预测排产/备货": "forecast",    # 预测备货
    "催收": "collection",           # 催收清单
    "超额度": "credit_limit",       # 超信用额度
    "维护": "maintenance_order",    # 维护工单
    "比价": "sourcing",             # 比价/采购
}


def suggestions_to_actions(suggestions: list, data: dict) -> list:
    """把各模块决策建议汇总成行动清单(含采购单草稿/预警/催收/工单)。"""
    actions = []
    for s in suggestions:
        entity = s.get("entity", "")
        action = s.get("action", "")
        level = s.get("level", "建议")
        typ = ACTION_TYPES.get(action, "note")
        if typ == "purchase_order":
            # 采购单草稿: 从产品表找供应商
            product = next((p for p in data.get("products", []) if str(p.get("id")) == str(entity)), {})
            actions.append({
                "type": "采购单草稿", "priority": {"告急": "紧急", "预警": "高", "建议": "中"}.get(level, "中"),
                "entity": entity, "name": product.get("name", entity),
                "action": f"采购 {entity}（补货，当前库存低于再订货水平）",
                "supplier": product.get("supplier", ""), "reason": s.get("reason", ""),
                "status": "待确认",
            })
        elif typ in ("shortage_alert", "slow_moving"):
            actions.append({"type": "库存预警", "priority": {"告急": "紧急", "预警": "高"}.get(level, "中"),
                            "entity": entity, "action": action, "reason": s.get("reason", ""), "status": "待处理"})
        elif typ == "collection":
            actions.append({"type": "催收提醒", "priority": "高", "entity": entity,
                            "action": "联系客户催收（账龄超期）", "reason": s.get("reason", ""), "status": "待催收"})
        elif typ == "credit_limit":
            actions.append({"type": "信用预警", "priority": "高", "entity": entity,
                            "action": "超信用额度，暂停/收紧授信", "reason": s.get("reason", ""), "status": "待确认"})
        elif typ == "maintenance_order":
            actions.append({"type": "维护工单", "priority": {"告急": "紧急", "预警": "高"}.get(level, "中"),
                            "entity": entity, "action": action, "reason": s.get("reason", ""), "status": "待派工"})
        else:
            actions.append({"type": "决策建议", "priority": "中", "entity": entity,
                            "action": action, "reason": s.get("reason", ""), "status": "待确认"})
    return actions


def export_actions(actions: list, outpath: str):
    """导出行动清单为 CSV。"""
    import csv
    with open(outpath, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["type", "priority", "entity", "name", "action", "supplier", "reason", "status"])
        w.writeheader()
        for a in actions:
            w.writerow(a)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from core.domain_model import load_all
    from decisions import inventory, sales, equipment, procurement
    data = load_all(os.path.join(os.path.dirname(__file__), "..", "data"))
    all_sug = inventory.decide(data) + sales.decide(data) + equipment.decide(data) + procurement.decide(data)
    acts = suggestions_to_actions(all_sug, data)
    print(f"══ 行动清单 ({len(acts)} 项) ══")
    for a in acts[:12]:
        print(f"  [{a['type']}][{a['priority']}] {a.get('entity')} → {a['action']}")
    out = os.path.join(os.path.dirname(__file__), "..", "actions.csv")
    export_actions(acts, out)
    print(f"  已导出 → {out}")
