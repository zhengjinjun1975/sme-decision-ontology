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
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from core.domain_model import load_all
from core.registry import enabled_modules
import importlib
import action as act_mod
from core import domain_model as dm

app = FastAPI(title="sme-decision-ontology API", version="0.11", description="本体驱动中小企业数据决策 API")

# 前端静态托管（前后端闭环）
WEB = os.path.join(ROOT, "..", "web")
if os.path.isdir(WEB):
    app.mount("/static", StaticFiles(directory=WEB), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(os.path.join(WEB, "index.html"))


# 领域模型定义（本体）：实体 + 关系（前端展示本体建模）
DOMAIN_MODEL = {
    "entities": [
        {"name": "Product", "label": "产品", "fields": ["id", "name", "category", "材质", "规格", "cost", "price"]},
        {"name": "Supplier", "label": "供应商", "fields": ["id", "name", "on_time_pct", "quality_pct"]},
        {"name": "Inventory", "label": "库存", "fields": ["product_id", "stock", "safety_stock", "lead_time_days"]},
        {"name": "Sale", "label": "销售", "fields": ["product_id", "date", "qty"]},
        {"name": "Customer", "label": "客户", "fields": ["id", "name", "order_amount", "aging_days", "credit_limit"]},
        {"name": "Equipment", "label": "设备", "fields": ["id", "name", "install_date", "warranty_months", "status"]},
    ],
    "relations": [
        {"from": "Product", "rel": "suppliedBy", "to": "Supplier", "label": "供应"},
        {"from": "Product", "rel": "hasInventory", "to": "Inventory", "label": "库存"},
        {"from": "Product", "rel": "hasSales", "to": "Sale", "label": "销售"},
        {"from": "Product", "rel": "producedBy", "to": "Equipment", "label": "生产"},
        {"from": "Customer", "rel": "places", "to": "Order", "label": "下单"},
    ],
}


@app.get("/model")
def get_model():
    cfg = json.load(open(os.path.join(ROOT, "..", "config", "model_config.json"), encoding="utf-8"))
    return {"ok": True, "active": cfg.get("active"), "models": cfg.get("models", {})}


class ModelReq(BaseModel):
    active: str


@app.post("/model")
def switch_model(req: ModelReq):
    p = os.path.join(ROOT, "..", "config", "model_config.json")
    cfg = json.load(open(p, encoding="utf-8"))
    if req.active not in cfg.get("models", {}):
        return {"ok": False, "error": f"未知模型: {req.active}"}
    cfg["active"] = req.active
    json.dump(cfg, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return {"ok": True, "active": req.active}


@app.get("/ontology")
def ontology():
    return {"ok": True, "model": DOMAIN_MODEL}


@app.get("/data-sources")
def data_sources():
    # 数据源状态: 各表加载行数 + 文件
    data_dir = os.path.join(ROOT, "..", "data")
    src = {}
    for table, rows in DATA.items():
        f = os.path.join(data_dir, f"{table}.csv")
        src[table] = {"rows": len(rows), "file": os.path.basename(f) if os.path.exists(f) else "未找到"}
    return {"ok": True, "sources": src, "data_dir": data_dir}

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
