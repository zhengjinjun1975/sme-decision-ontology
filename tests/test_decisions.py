#!/usr/bin/env python3
"""test_decisions.py — 决策规则单元测试（Golden test，确定性可测）"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "codes"))

from core.domain_model import load_all
DATA = load_all(os.path.join(ROOT, "data"))


def _run(module):
    mod = __import__(f"decisions.{module}", fromlist=["decide"])
    return mod.decide(DATA)


def test_d1_reorder():
    """库存补货: 日均出库×提前期+安全库存, stock<reorder→补货"""
    s = _run("inventory")
    # P03 蝶阀 stock=10 < reorder(约 5.5×10+15≈70) → 应补货
    assert any("P03" in x.get("entity", "") for x in s)


def test_d2_shortage():
    """缺货: stock<safety_stock→预警"""
    s = _run("inventory")
    # P02 stock=20 < safety=25 → 缺货
    assert any("P02" in x.get("entity", "") for x in s)


def test_d7_credit():
    """客户信用: aging>60→告急催收"""
    s = _run("sales")
    # C02 aging=75, C03 aging=90 → 高风险
    assert any("C02" in x.get("entity", "") for x in s)


def test_d8_equipment():
    """设备维护: 状态待修→告急"""
    s = _run("equipment")
    assert any("E03" in x.get("entity", "") for x in s)


def test_decision_structure():
    """每条建议含 entity/action/reason/level"""
    for m in ["inventory", "procurement", "sales", "equipment"]:
        for s in _run(m):
            assert {"entity", "action", "reason", "level"} <= set(s.keys())


def test_selective_deploy():
    """选择性部署: deployment.json enabled"""
    from core.registry import enabled_modules
    cfg = os.path.join(ROOT, "config", "deployment.json")
    enabled = enabled_modules(cfg)
    assert isinstance(enabled, list) and len(enabled) >= 1
