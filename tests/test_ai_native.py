#!/usr/bin/env python3
"""test_ai_native.py — AI 原生(行动闭环/MCP/NL) + 多库测试"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "codes"))

from core.domain_model import load_all
from decisions import inventory, sales, equipment, procurement
DATA = load_all(os.path.join(ROOT, "data"))


def _all_suggestions():
    return inventory.decide(DATA) + sales.decide(DATA) + equipment.decide(DATA) + procurement.decide(DATA)


def test_action_loop():
    """决策→行动闭环: 生成采购单草稿/预警"""
    import action
    acts = action.suggestions_to_actions(_all_suggestions(), DATA)
    assert acts
    assert any(a["type"] == "采购单草稿" for a in acts)
    for a in acts:
        assert {"type", "entity", "action", "reason"} <= set(a.keys())


def test_action_export():
    """行动清单可导出 CSV"""
    import action
    acts = action.suggestions_to_actions(_all_suggestions(), DATA)
    out = os.path.join(ROOT, "_test_actions.csv")
    action.export_actions(acts, out)
    assert os.path.exists(out)
    os.remove(out)


def test_mcp_handshake_and_tools():
    import mcp_server
    r = mcp_server._handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert "sme-decision-mcp" in r["result"]["serverInfo"]["name"]
    tools = mcp_server._handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert {"decide", "actions", "thresholds"} <= {t["name"] for t in tools["result"]["tools"]}


def test_mcp_decide():
    import mcp_server
    r = mcp_server._handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                            "params": {"name": "decide", "arguments": {"module": "inventory"}}})
    out = r["result"]["content"][0]["text"]
    assert "inventory" in out


def test_nl_routing():
    """NL 结构化路由 + 歧义回显校验"""
    import api_server
    from fastapi.testclient import TestClient
    c = TestClient(api_server.app)
    assert c.post("/ask", json={"question": "库存补货"}).json()["module"] == "inventory"
    assert c.post("/ask", json={"question": "设备维护"}).json()["module"] == "equipment"
    # 歧义 → 回显校验
    r = c.post("/ask", json={"question": "采购和库存"}).json()
    assert r["mode"] == "confirm" and len(r.get("candidates", [])) >= 2


def test_multidb_graceful_degrade():
    """MySQL/PG 未装 → 清晰报错(优雅降级)"""
    from core.data_mapper import load_mysql, load_pg, load_sqlite
    try:
        load_mysql("db", "t")
        assert False
    except ImportError:
        pass
    try:
        load_pg("db", "t")
        assert False
    except ImportError:
        pass
    # SQLite 可用
    import sqlite3
    import tempfile
    db = os.path.join(tempfile.gettempdir(), "_sme_t.db")
    conn = sqlite3.connect(db); conn.execute("CREATE TABLE IF NOT EXISTS items(id TEXT)"); conn.commit(); conn.close()
    assert isinstance(load_sqlite(db, "items"), list)
    try:
        os.remove(db)
    except OSError:
        pass
