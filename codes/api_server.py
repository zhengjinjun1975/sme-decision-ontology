#!/usr/bin/env python3
"""api_server.py — FastAPI：决策 API + NL 自然语言决策入口（AI 原生）

原则：规则算，LLM 讲。计算层零 token 确定性；NL 是辅助入口（结构化关键字路由 + 回显校验）。
"""
import os
import sys
import json

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from fastapi import FastAPI
from pydantic import BaseModel
from core.domain_model import load_all
from core.registry import enabled_modules
import importlib
import action as act_mod

app = FastAPI(title="sme-decision-ontology API", version="0.1.0", description="本体驱动中小企业数据决策 API")

DATA = load_all(os.path.join(ROOT, "..", "data"))

# NL 路由：问题关键词 → 决策模块（结构化，非 LLM）
NL_ROUTES = {
    "inventory": ["库存", "补货", "缺货", "呆滞", "再订货"],
    "procurement": ["采购", "比价", "供应商", "报价"],
    "sales": ["销售", "预测", "信用", "回款", "催收", "账龄"],
    "equipment": ["设备", "维护", "保修", "工单"],
}


def _decide(module=None):
    if module:
        mod = importlib.import_module(f"decisions.{module}")
        return {module: mod.decide(DATA)}
    return {name: importlib.import_module(f"decisions.{name}").decide(DATA)
            for name in enabled_modules(os.path.join(ROOT, "..", "config", "deployment.json"))}


class AskReq(BaseModel):
    question: str


@app.get("/decisions/{module}")
def decisions(module: str):
    return {"ok": True, module: _decide(module).get(module, [])}


@app.get("/decisions")
def all_decisions():
    return {"ok": True, "decisions": _decide()}


@app.get("/actions")
def actions():
    all_sug = [s for v in _decide().values() for s in v]
    return {"ok": True, "actions": act_mod.suggestions_to_actions(all_sug, DATA)}


@app.get("/thresholds")
def thresholds():
    return json.load(open(os.path.join(ROOT, "..", "config", "thresholds.json"), encoding="utf-8"))


@app.post("/ask")
def ask(req: AskReq):
    """自然语言问决策：结构化关键字路由（规则算），歧义时回显校验（NL 是辅助）。"""
    q = req.question
    hits = [m for m, kws in NL_ROUTES.items() if any(k in q for k in kws)]
    if not hits:
        return {"ok": True, "mode": "miss", "answer": "未识别决策域。可问：库存/采购/销售/设备 相关决策。"}
    if len(hits) == 1:
        return {"ok": True, "mode": "rule", "module": hits[0], "decisions": _decide(hits[0]).get(hits[0], [])}
    # 歧义 → 回显校验（OpenClaw 建议：NL 结果强制确认）
    return {"ok": True, "mode": "confirm", "candidates": hits,
            "answer": f"您问的涉及多个决策域（{'/'.join(hits)}），请问具体要哪个？"}
