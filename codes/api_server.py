#!/usr/bin/env python3
"""api_server.py — FastAPI：决策 API + NL 自然语言决策入口（AI 原生）

原则：规则算，LLM 讲。计算层零 token 确定性；NL 是辅助入口（结构化关键字路由 + 回显校验）。
"""
import os
import sys
import json
from datetime import datetime

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


@app.middleware("http")
async def no_cache(request, call_next):
    """强制浏览器不缓存前端/API(防陈旧文件): 每次重新拉取。"""
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# 前端静态托管（前后端闭环）
WEB = os.path.join(ROOT, "..", "web")
if os.path.isdir(WEB):
    app.mount("/static", StaticFiles(directory=WEB), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(os.path.join(WEB, "index.html"))


# 领域模型定义（本体）：实体 + 关系（前端展示本体建模）
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


def _infer_domain(table: str) -> str:
    """按表名猜业务域(跨行业自适应, 通用企业职能)。"""
    t = table.lower()
    if any(k in t for k in ("purchase", "supplier", "buy", "order", "procure", "raw")):
        return "采购域"
    if any(k in t for k in ("product", "batch", "produc", "work", "equip", "machin", "qc", "quality", "assembly")):
        return "生产域"
    if any(k in t for k in ("inventory", "stock", "warehouse", "store")):
        return "库存域"
    if any(k in t for k in ("sale", "customer", "order", "client", "deliver")):
        return "销售域"
    if any(k in t for k in ("payment", "finance", "invoice", "bill", "receiv")):
        return "财务域"
    return "其他域"


def _effective_schema():
    """当前数据的自适应 schema：config/ontology.json + 数据中未覆盖的表自动扩展(AI建模)。"""
    from core import ontology as ont
    schema = ont.load_schema(os.path.join(ROOT, "..", "config", "ontology.json"))
    covered = {e["table"] for e in schema["entities"]}
    extra = [t for t in DATA if t not in covered]
    if extra:
        from core import modeling
        auto = modeling.suggest_schema(DATA)
        for e in auto["entities"]:
            if e["table"] in extra:
                e["domain"] = _infer_domain(e["table"])
                schema["entities"].append(e)
        # 自动补 FK 关系
        schema_rels = {r.get("fk") for r in schema["relations"] if r.get("fk")}
        for r in auto["relations"]:
            if r.get("fk") not in schema_rels:
                schema["relations"].append(r)
        # 重建实体索引(load_schema时构建, 需包含新增实体)
        schema["_entities"] = {e["id"]: e for e in schema["entities"]}
    return schema


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


class DbConnReq(BaseModel):
    db_type: str  # mysql/pg
    db: str
    host: str = "localhost"
    port: int = 3306
    user: str = "root"
    password: str = ""


@app.post("/data/db-test")
def db_test(req: DbConnReq):
    """测试数据库连接(端口/账号/驱动是否可用)。"""
    from core import data_mapper as dm
    return dm.db_test(req.db_type, req.db, req.host, req.port, req.user, req.password)


@app.post("/data/db-connect")
def db_connect(req: DbConnReq):
    """连接数据库加载表 → 重新本体建模(端口+方法)。"""
    global DATA_DIR
    from core import data_mapper as dm
    try:
        loaded = dm.db_connect(req.db_type, req.db, req.host, req.port, req.user, req.password)
    except ImportError as e:
        return {"ok": False, "error": str(e)}
    if not loaded:
        return {"ok": False, "error": "未加载到任何表(检查库名/表名)"}
    # 存入临时数据目录供本体建模读取
    os.makedirs(DATA_DIR, exist_ok=True)
    for table, rows in loaded.items():
        if "(err)" in table:
            continue
        csv_path = os.path.join(DATA_DIR, f"{table}.csv")
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            if rows:
                import csv as _csv
                w = _csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
    _reload_data()
    return {"ok": True, "db": req.db, "loaded_tables": [k for k in loaded if "(err)" not in k],
            "sources": {k: len(v) for k, v in DATA.items()}}


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
    """真实本体 schema(自适应数据) + 图统计 + 约束校验。"""
    try:
        from core import ontology as ont
        schema = _effective_schema()
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


@app.get("/graph/full")
def graph_full():
    """完整企业实例图(自适应schema)，供前端生成真实 SVG 大图(含业务域, 动态域列)。"""
    from core import ontology as ont
    schema = _effective_schema()
    g = ont.build_graph(DATA, schema)
    # 实体类型 → label/业务域
    entities = {e["id"]: {"label": e["label"], "domain": e.get("domain", "其他域")} for e in schema["entities"]}
    nodes = [{"id": nid, "entity": n["entity"], "label": entities.get(n["entity"], {}).get("label", n["entity"]),
              "domain": entities.get(n["entity"], {}).get("domain", "其他域"),
              "name": n["data"].get("name") or n["data"].get("id"), "id_val": n["id"]}
             for nid, n in g["nodes"].items()]
    edges = [{"from": e["from"], "to": e["to"], "rel": e["rel"], "label": e["label"]} for e in g["edges"]]
    domains = sorted({e.get("domain", "其他域") for e in schema["entities"]})
    return {"ok": True, "nodes": nodes, "edges": edges,
            "counts": {"nodes": len(nodes), "edges": len(edges)}, "domains": domains}


@app.get("/ontology/model")
def ontology_model():
    """Palantir 风格深化企业本体模型：对象类型(属性语义)+链接类型+类型体系+语义域。"""
    from core import ontology as ont
    schema = _effective_schema()
    model = ont.build_ontology_model(DATA, schema)
    return {"ok": True, "model": model}


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
    """用声明式规则引擎(跨行业可配置)产出决策建议。"""
    import rules_engine as reng
    enabled = enabled_modules(os.path.join(ROOT, "..", "config", "deployment.json"))
    res = reng.run_rules(DATA, enabled=enabled)
    if module:
        return {module: res.get(module, [])}
    return res


@app.get("/decision/summary")
def decision_summary():
    """决策总结报告：规则聚合 + LLM 解释层(本地Ollama生成自然语言执行摘要, 失败回落规则)。"""
    dec = _decide()
    all_sug = [s for v in dec.values() for s in v]
    by_level = {}
    for s in all_sug:
        by_level[s.get("level", "建议")] = by_level.get(s.get("level", "建议"), 0) + 1
    urgent = [s for s in all_sug if s.get("level") == "告急"]
    warn = [s for s in all_sug if s.get("level") == "预警"]
    recs = []
    if urgent:
        recs.append(f"立即处理 {len(urgent)} 项告急：{', '.join(u.get('entity','') for u in urgent[:5])}")
    if warn:
        recs.append(f"关注 {len(warn)} 项预警（缺货/呆滞/信用/供应商绩效）")
    if not urgent and not warn:
        recs.append("各项指标正常，无需紧急干预")
    report = {
        "total": len(all_sug), "by_level": by_level,
        "urgent": urgent[:10], "warning": warn[:10],
        "final_recommendation": recs,
    }
    # LLM 解释层("规则算LLM讲"): 用本地 Ollama 生成自然语言执行摘要
    llm_text = None
    try:
        from core.model_llm import llm_generate
        urls = ", ".join(u.get("entity", "") for u in urgent[:5]) if urgent else ("无告急项" )
        warns = ", ".join(w.get("entity", "") for w in warn[:5]) if warn else "无预警项"
        prompt = (f"你是企业运营决策助理。基于以下规则决策结果，写一段简明的经营执行摘要(200字内)：\n"
                  f"共{len(all_sug)}条决策建议(告急{by_level.get('告急',0)}/预警{by_level.get('预警',0)}/建议{by_level.get('建议',0)})；\n"
                  f"告急项：{urls}；预警项：{warns}。\n"
                  f"用中文，指出最需优先处理的事项和理由，语气冷静务实。")
        llm_text = llm_generate(prompt, temperature=0.3, max_tokens=300)
        if llm_text == "[模型不可用]":
            llm_text = None
    except Exception:
        llm_text = None
    report["llm_summary"] = llm_text  # None 时前端回落规则建议
    return {"ok": True, "report": report}


@app.get("/decisions/{module}")
def decisions(module: str):
    return {"ok": True, module: _decide(module).get(module, [])}


@app.get("/decisions")
def all_decisions():
    return {"ok": True, "decisions": _decide()}


@app.get("/actions")
def actions():
    """行动清单（含完成状态, 支持执行闭环）。"""
    import hashlib
    all_sug = [s for v in _decide().values() for s in v]
    acts = act_mod.suggestions_to_actions(all_sug, DATA)
    state = _load_actions_state()
    for a in acts:
        aid = _action_id(a)
        a["id"] = aid
        st = state.get(aid, {})
        a["status"] = st.get("status", "待确认")
        a["completed_at"] = st.get("completed_at")
        a["effect"] = st.get("effect")
    return {"ok": True, "actions": acts}


class ActionReq(BaseModel):
    effect: str = "已完成"


@app.post("/actions/{aid}/complete")
def complete_action(aid: str, req: ActionReq = None):
    """标记行动完成（执行闭环第一步）→ 供效果追踪 + 阈值自适应。"""
    state = _load_actions_state()
    state[aid] = {"status": "完成", "completed_at": datetime.now().isoformat()[:19],
                  "effect": (req.effect if req else "已完成")}
    _save_actions_state(state)
    return {"ok": True, "action": aid, "status": "完成"}


def _action_id(a: dict) -> str:
    import hashlib
    raw = f"{a.get('type')}|{a.get('entity')}|{a.get('action')}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


_ACTIONS_STATE = os.path.join(ROOT, "..", "config", "actions_state.json")


def _load_actions_state() -> dict:
    try:
        with open(_ACTIONS_STATE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_actions_state(state: dict):
    with open(_ACTIONS_STATE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)


@app.get("/decision/threshold-adapt")
def threshold_adapt():
    """执行闭环第三步: 根据已完成行动 + 当前数据, 建议阈值自适应调整。"""
    from collections import Counter
    state = _load_actions_state()
    done = [v for v in state.values() if v.get("status") == "完成"]
    # 分析完成行动的实体, 结合当前数据给出阈值建议(规则驱动, 零token)
    suggestions = []
    if not done:
        return {"ok": True, "completed": 0, "suggestions": [], "note": "尚无已完成行动, 先执行决策行动清单"}
    # 已完成的采购/补货行动 → 看对应产品库存是否仍缺(效果追踪)
    done_entities = Counter(v.get("effect", "") for v in done)
    inventory = DATA.get("inventory", [])
    still_short = [i.get("product_id") for i in inventory
                   if float(i.get("stock", 0)) < float(i.get("safety_stock", 0))]
    if still_short:
        suggestions.append(f"仍有 {len(still_short)} 个产品低于安全库存(如 {', '.join(still_short[:3])})，"
                           f"建议提高 safety_stock 阈值或检查供应链")
    else:
        suggestions.append("已完成补货行动后库存已恢复，当前阈值合理")
    # 供应商绩效类完成 → 综合
    sugg = [s for s in _decide().get("procurement", []) if s.get("level") == "预警"]
    if sugg:
        suggestions.append(f"供应商绩效预警 {len(sugg)} 项，建议纳入供应商评估")
    return {"ok": True, "completed": len(done), "suggestions": suggestions}


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
