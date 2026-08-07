#!/usr/bin/env python3
"""mcp_server.py — 轻量 MCP server（纯标准库 stdio JSON-RPC）

暴露 sme-decision-ontology 决策给任意 MCP-native agent（可信决策 API）。
AI 原生：规则算，LLM 讲；agent 可调用决策/预警/行动。

工具:
  decide        跑指定决策模块(或全部)
  actions       决策 → 行动清单(采购单/预警/催收)
  thresholds    查看/当前阈值
"""
import sys
import os
import json

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from core.domain_model import load_all
from core.registry import enabled_modules
import importlib

_DATA = None


def _data():
    global _DATA
    if _DATA is None:
        _DATA = load_all(os.path.join(ROOT, "..", "data"))
    return _DATA


def _run_all():
    data = _data()
    results = {}
    for name in enabled_modules(os.path.join(ROOT, "..", "config", "deployment.json")):
        mod = importlib.import_module(f"decisions.{name}")
        results[name] = mod.decide(data)
    return results


def _decide(module=None):
    data = _data()
    if module:
        mod = importlib.import_module(f"decisions.{module}")
        return {module: mod.decide(data)}
    return _run_all()


def _actions():
    import action as act_mod
    data = _data()
    all_sug = []
    for name, sug in _run_all().items():
        all_sug.extend(sug)
    return act_mod.suggestions_to_actions(all_sug, data)


TOOLS = [
    {"name": "decide", "description": "跑决策模块(库存/采购/销售/设备, 空=全部)", "inputSchema": {"type": "object", "properties": {"module": {"type": "string"}}}},
    {"name": "actions", "description": "决策→行动清单(采购单草稿/预警/催收)", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "thresholds", "description": "查看当前决策阈值", "inputSchema": {"type": "object", "properties": {}}},
]


def _handle(req):
    mid = req.get("id")
    method = req.get("method")
    params = req.get("params") or {}
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": mid, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "sme-decision-mcp", "version": "0.1"}}}
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            if name == "decide":
                out = _decide(args.get("module"))
            elif name == "actions":
                out = _actions()
            elif name == "thresholds":
                out = json.load(open(os.path.join(ROOT, "..", "config", "thresholds.json"), encoding="utf-8"))
            else:
                return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"未知工具: {name}"}}
            return {"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False)}]}}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": str(e)}}
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"未知方法: {method}"}}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = _handle(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
