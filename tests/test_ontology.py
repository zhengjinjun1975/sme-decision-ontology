#!/usr/bin/env python3
"""test_ontology.py — 本体建模核心测试（schema/建图/约束/遍历/AI建模）"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "codes"))

from core.domain_model import load_all
from core import ontology as ont
DATA = load_all(os.path.join(ROOT, "data"))
SCHEMA = ont.load_schema(os.path.join(ROOT, "config", "ontology.json"))


def test_schema_load():
    """schema 加载 + 校验"""
    assert len(SCHEMA["entities"]) >= 5
    assert len(SCHEMA["relations"]) >= 3


def test_validate_clean():
    """约束校验: 干净数据无问题(明细实体不做唯一)"""
    issues = ont.validate(DATA, SCHEMA)
    errors = [i for i in issues if i["severity"] == "error"]
    assert not errors


def test_build_graph_cross_domain():
    """跨表跨域建图: 178 节点 / 264 边(企业级价值链本体)"""
    g = ont.build_graph(DATA, SCHEMA)
    assert len(g["nodes"]) == 178  # 154 + 8采购 + 8生产 + 8回款
    assert len(g["edges"]) == 264  # 16供应+16库存+88销售+88客户+16isA+8采购From+8采购+8生产+8设备+8回款


def test_customer_relation():
    """企业↔客户关系: 销售售予客户(88条 hasCustomer)"""
    g = ont.build_graph(DATA, SCHEMA)
    cust = [e for e in g["edges"] if e["rel"] == "hasCustomer"]
    assert len(cust) == 88


def test_value_chain():
    """企业级价值流: 采购/生产/回款关系"""
    g = ont.build_graph(DATA, SCHEMA)
    rels = {e["rel"] for e in g["edges"]}
    assert {"purchaseFrom", "purchases", "produces", "usesEquipment", "paidBy"} <= rels


def test_category_hierarchy():
    """本体层次深入: 产品类别类层级(isA)"""
    g = ont.build_graph(DATA, SCHEMA)
    cats = [n for n, v in g["nodes"].items() if v["entity"] == "Category"]
    assert len(cats) == 8
    isa = [e for e in g["edges"] if e["rel"] == "isA"]
    assert len(isa) == 16


def test_traverse():
    """图遍历(跨域): Supplier S01 → 3供应 + 2采购"""
    g = ont.build_graph(DATA, SCHEMA)
    rel = ont.traverse(g, "Supplier", "S01")
    assert len(rel) == 5  # S01 供应 P01/P02/P05 + 采购 PR01/PR03


def test_ai_modeling():
    """AI 原生建模: 规则推断 schema"""
    from core import modeling
    sug = modeling.suggest_schema(DATA)
    assert len(sug["entities"]) >= 5
    assert len(sug["relations"]) >= 2  # product_id FK 推断
    # 单复数匹配: Products↔product
    fks = [r["fk"] for r in sug["relations"]]
    assert any("inventory.product_id" in f for f in fks)


def test_modeling_label_enhance():
    """LLM 增强回落(无 key 不崩)"""
    from core import modeling
    sug = modeling.suggest_schema(DATA)
    enhanced = modeling.llm_enhance(sug, use_llm=False)
    assert enhanced == sug  # use_llm=False 不增强
