# -*- coding: utf-8 -*-
"""
设备维护决策模块（equipment）—— D8 设备维护
=============================================

规则说明（纯标准库，零第三方依赖）：
  依据安装日期 + 保修月数计算保修到期日，结合设备状态给出维护建议：
    - 状态为「待修」                      → 告急，立即维修
    - 保修已过期                          → 告急/预警，安排检修
    - 保修将在 warranty_warn_days 内到期  → 预警，提前安排续保或大修
  阈值取 config/thresholds.json 的 equipment.warranty_warn_days（默认 30 天）。

入参：data(dict)，键含 'equipment'，为 list[dict]。
出参：list[dict]，每条含 {entity, action, reason, level}。
"""

import json
import os
from datetime import date

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_THRESHOLDS_PATH = os.path.join(_PROJECT_ROOT, "config", "thresholds.json")


def _load_warranty_days():
    """读取 equipment.warranty_warn_days；缺失时返回默认 30 天。"""
    defaults = {"warranty_warn_days": 30}
    try:
        with open(_THRESHOLDS_PATH, "r", encoding="utf-8") as f:
            return json.load(f).get("equipment", {}).get(
                "warranty_warn_days", defaults["warranty_warn_days"]
            )
    except (OSError, ValueError):
        return defaults["warranty_warn_days"]


def _warranty_end(install_date, warranty_months):
    """根据安装日期与保修月数推算保修到期日；解析失败返回 None。"""
    try:
        y, m, d = (int(x) for x in str(install_date).split("-"))
        im = (m - 1) + int(warranty_months)
        return date(y + im // 12, im % 12 + 1, d)
    except (ValueError, TypeError, AttributeError):
        return None


def decide(data):
    """根据设备台账产出维护决策建议列表。"""
    equipment = data.get("equipment", [])
    warn_days = _load_warranty_days()
    today = date.today()
    decisions = []

    for eq in equipment:
        eid = eq.get("id")
        status = eq.get("status")
        end = _warranty_end(eq.get("install_date"), eq.get("warranty_months"))

        # 状态待修：最高优先级
        if status and "待修" in str(status):
            decisions.append({
                "entity": eid,
                "action": "立即维修",
                "reason": f"D8维护: {eq.get('name')} 状态={status}，需立即维修",
                "level": "告急",
            })

        if end is not None:
            remain = (end - today).days
            if remain < 0:
                decisions.append({
                    "entity": eid,
                    "action": "安排检修/评估更换",
                    "reason": (
                        f"D8维护: {eq.get('name')} 保修已于{end.isoformat()}到期({-remain}天前)，"
                        "建议检修并评估续保"
                    ),
                    "level": "告急",
                })
            elif remain <= warn_days:
                decisions.append({
                    "entity": eid,
                    "action": "提前安排续保/大修",
                    "reason": (
                        f"D8维护: {eq.get('name')} 保修将于{end.isoformat()}到期，"
                        f"剩余{remain}天 ≤ 预警线{warn_days}天"
                    ),
                    "level": "预警",
                })

    return decisions
