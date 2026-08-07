#!/usr/bin/env python3
"""api_server.py — FastAPI：决策 API + NL 自然语言决策入口（AI 原生）

原则：规则算，LLM 讲。计算层零 token 确定性；NL 是辅助入口（结构化关键字路由 + 回显校验）。
"""
import os
import sys
import json

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from fastapi import FastAPI, UploadFile, File
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


class DataDirReq(BaseModel):
    dir: str


class AskReq(BaseModel):
    question: str


# 全局数据(可切换目录重新加载)
DATA_DIR = os.path.join(ROOT, "..", "data")


def _reload_data():
    global DATA
    DATA = load_all(DATA_DIR)


DATA = load_all(DATA_DIR)


@app.post("/data/set-dir")
def set_data_dir(req: DataDirReq):
    """选择数据目录，重新加载数据（目录接入能力）。"""
    global DATA_DIR
    d = os.path.abspath(req.dir)
    if not os.path.isdir(d):
        return {"ok": False, "error": f"目录不存在: {d}"}
    DATA_DIR = d
    _reload_data()
    return {"ok": True, "data_dir": DATA_DIR, "sources": {k: len(v) for k, v in DATA.items()}}


@app.get("/data/dir")
def get_data_dir():
    return {"ok": True, "data_dir": DATA_DIR}


@app.post("/data/upload")
async def upload_data(files: list[UploadFile] = File(...)):
    """浏览器选择路径上传数据：保存 CSV 到数据目录并重载。"""
    global DATA_DIR
    os.makedirs(DATA_DIR, exist_ok=True)
    saved = []
    for f in files:
        if not f.filename.endswith(".csv"):
            continue
        dest = os.path.join(DATA_DIR, os.path.basename(f.filename))
        content = await f.read()
        with open(dest, "wb") as fh:
            fh.write(content)
        saved.append(f.filename)
    _reload_data()
    return {"ok": True, "uploaded": saved, "sources": {k: len(v) for k, v in DATA.items()}}


@app.post("/model")
def switch_model(req: ModelReq):
    p = os.path.join(ROOT, "..", "config", "model_config.json")
    cfg = json.load(open(p, encoding="utf-8"))
    if req.active not in cfg.get("models", {}):
        return {"ok": False, "error": f"未知模型: {req.active}"}
    cfg["active"] = req.active
    json.dump(cfg, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return {"ok": True, "active": req.active}


class ModelConfigReq(BaseModel):
    key: str
    config: dict


@app.post("/model/config")
def save_model_config(req: ModelConfigReq):
    """模型设置：保存具体配置(base_url/model/api_key/name/type)。"""
    p = os.path.join(ROOT, "..", "config", "model_config.json")
    cfg = json.load(open(p, encoding="utf-8"))
    if req.key not in cfg.get("models", {}):
        return {"ok": False, "error": f"未知模型: {req.key}"}
    allowed = {"name", "type", "base_url", "model", "api_key"}
    for k, v in req.config.items():
        if k in allowed:
            cfg["models"][req.key][k] = v
    json.dump(cfg, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return {"ok": True, "key": req.key, "models": cfg["models"]}


@app.get("/ontology")
def ontology():
    """真实本体 schema + 图统计 + 约束校验（生产级本体建模视图）。"""
    try:
        from core import ontology as ont
        schema = ont.load_schema(os.path.join(ROOT, "..", "config", "ontology.json"))
        graph = ont.build_graph(DATA, schema)
        issues = ont.validate(DATA, schema)
        return {"ok": True,
                "model": {"entities": schema["entities"], "relations": schema["relations"], "constraints": schema.get("constraints", [])},
                "graph": {"nodes": len(graph["nodes"]), "edges": len(graph["edges"])},
                "validation": {"issues": issues}}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/modeling/suggest")
def modeling_suggest():
    """AI 原生建模：从当前数据自动建议本体 schema（规则兜底确定性 + LLM 可选）。"""
    from core import modeling
    schema = modeling.suggest_schema(DATA)
    # LLM 增强(本地优先, 失败回落)
    try:
        schema = modeling.llm_enhance(schema, use_llm=True)
    except Exception:
        pass
    return {"ok": True, "suggested": schema}


@app.get("/graph/{entity}/{eid}")
def graph_traverse(entity: str, eid: str):
    """本体图遍历（跨域）：从某实体实例出发的相关实体。"""
    from core import ontology as ont
    schema = ont.load_schema(os.path.join(ROOT, "..", "config", "ontology.json"))
    graph = ont.build_graph(DATA, schema)
    rel = ont.traverse(graph, entity, eid)
    # 解析关联详情
    out = []
    for r in rel:
        target = r.get("to") or r.get("from")
        node = graph["nodes"].get(target, {})
        out.append({"rel": r.get("rel"), "label": r.get("label"), "entity": node.get("entity"), "id": node.get("id"), "data": node.get("data", {})})
    return {"ok": True, "start": f"{entity}:{eid}", "related": out}


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


@app.get("/decision/summary")
def decision_summary():
    """决策总结报告：汇总 + 最终建议定版（规则聚合，LLM 可选解读）。"""
    dec = _decide()
    all_sug = [s for v in dec.values() for s in v]
    # 按严重度统计
    by_level = {}
    for s in all_sug:
        by_level[s.get("level", "建议")] = by_level.get(s.get("level", "建议"), 0) + 1
    # 告急/预警优先
    urgent = [s for s in all_sug if s.get("level") == "告急"]
    warn = [s for s in all_sug if s.get("level") == "预警"]
    # 最终建议定版
    recs = []
    if urgent:
        recs.append(f"立即处理 {len(urgent)} 项告急：{', '.join(u.get('entity','') for u in urgent[:5])}")
    if warn:
        recs.append(f"关注 {len(warn)} 项预警（缺货/呆滞/信用/供应商绩效）")
    if not urgent and not warn:
        recs.append("各项指标正常，无需紧急干预")
    report = {
        "total": len(all_sug),
        "by_level": by_level,
        "urgent": urgent[:10],
        "warning": warn[:10],
        "final_recommendation": recs,
    }
    return {"ok": True, "report": report}


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
