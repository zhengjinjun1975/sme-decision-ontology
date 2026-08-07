#!/usr/bin/env python3
"""ontology.py — 中庸之道本体建模核心（纯标准库零依赖）

通用本体 schema（实体/属性/关系/约束）→ 校验 → 跨表跨域建统一实例图 → 图遍历。
领域无关：换行业只换 schema + 数据，代码不动。

用法:
  from core.ontology import load_schema, build_graph, validate, traverse
  schema = load_schema("config/ontology.json")
  graph = build_graph(data, schema)     # 跨表 join 成本体图
  issues = validate(data, schema)       # 约束校验
  related = traverse(graph, "Product", "P01")  # 图遍历(跨域)
"""
import os
import json


def load_schema(path: str) -> dict:
    """加载 + 校验本体 schema（实体/关系/约束合法性）。"""
    schema = json.load(open(path, encoding="utf-8"))
    entities = {e["id"]: e for e in schema.get("entities", [])}
    # 校验: 实体 id 唯一
    assert len(entities) == len(schema.get("entities", [])), f"实体 id 重复: {path}"
    # 关系 from/to 必须存在
    for r in schema.get("relations", []):
        assert r["from"] in entities, f"关系 {r['id']} 的 from={r['from']} 不存在"
        assert r["to"] in entities, f"关系 {r['id']} 的 to={r['to']} 不存在"
    schema["_entities"] = entities
    return schema


# ═══════════════ Palantir 风格深化：对象类型/属性语义/类型体系/链接类型 ═══════════════
_REF_HINTS = ("_id", "_code", "_no", "id")
_MEASURE_HINTS = ("qty", "amount", "price", "cost", "stock", "pct", "days", "months", "age", "limit", "rank", "rate", "num", "weight", "size")
_DATE_HINTS = ("date", "time", "day", "install", "create")
_CATEGORY_HINTS = ("category", "type", "status", "state", "kind", "flag", "grade", "level")


def _infer_prop_role(col: str, ptype: str) -> str:
    """属性语义角色分类(identifier/reference/measure/category/timestamp/text) — Palantir Property 语义。"""
    low = col.lower()
    if low == "id" or (low.endswith("_id") and ptype == "string"):
        return "identifier"
    if col.endswith("_id") or col.endswith("_code"):
        return "reference"
    if ptype == "number" or any(h in low for h in _MEASURE_HINTS):
        return "measure"
    if ptype == "date" or any(h in low for h in _CATEGORY_HINTS):
        return "category"
    if any(h in low for h in _DATE_HINTS):
        return "timestamp"
    return "text"


def classify_properties(schema: dict) -> dict:
    """为每个实体的属性标注语义角色(identifier/reference/measure/category/timestamp/text)。"""
    for e in schema.get("entities", []):
        for a in e.get("attributes", []):
            a["role"] = _infer_prop_role(a["name"], a.get("type", "string"))
        # 主键标识
        for a in e.get("attributes", []):
            if a["name"] == e.get("key"):
                a["role"] = "identifier"
    return schema


def build_class_hierarchy(schema: dict) -> list:
    """类型体系(Type hierarchy)：Enterprise → BusinessObject → 业务域类 → 实体(Is-A)。
    Palantir 式对象类型分类，跨行业自适应(实体按 domain 归入业务域类)。"""
    hierarchy = [
        {"name": "Enterprise", "super": None, "label": "企业"},
        {"name": "BusinessObject", "super": "Enterprise", "label": "业务对象"},
    ]
    # 业务域类(来自实体 domain)
    domains = {}
    for e in schema.get("entities", []):
        d = e.get("domain", "其他域")
        domains.setdefault(d, {"name": d, "super": "BusinessObject", "label": d, "children": []})
        domains[d]["children"].append(e["id"])
    for d in domains.values():
        hierarchy.append({"name": d["name"], "super": "BusinessObject", "label": d["label"], "entities": d["children"]})
    # Category 类(产品类别 Is-A)
    for e in schema.get("entities", []):
        if "category" in [a["name"] for a in e.get("attributes", [])]:
            hierarchy.append({"name": f"{e['id']}Category", "super": e["id"], "label": f"{e['label']}类别", "kind": "is_a"})
    return hierarchy


def enrich_links(schema: dict) -> dict:
    """链接类型(Link Types)：关系补 inverse 反向标签 + 类型(kind: data 数据链/derived 派生)。"""
    for r in schema.get("relations", []):
        if r.get("abstract"):
            r["kind"] = "derived"
        else:
            r["kind"] = "data"
        r["inverse"] = {"Product→Supplier": "供应商提供产品", "Product→Inventory": "产品库存", "Product→Sale": "产品销售",
                        "Sale→Customer": "客户购买", "Purchase→Supplier": "供应商供货", "Purchase→Product": "产品被采购",
                        "Production→Product": "产品被生产", "Production→Equipment": "设备被使用", "Payment→Customer": "客户付款"}.get(
            f"{r['from']}→{r['to']}", "关联")
    return schema


def build_ontology_model(data: dict, schema: dict) -> dict:
    """构建 Palantir 风格企业本体模型：对象类型(带属性语义) + 链接类型 + 类型体系 + 语义域。"""
    schema = classify_properties(schema)
    schema = enrich_links(schema)
    return {
        "object_types": schema["entities"],   # 对象类型(含属性语义角色)
        "link_types": schema["relations"],     # 链接类型(含 inverse/kind)
        "type_hierarchy": build_class_hierarchy(schema),  # 类型体系(Is-A)
        "semantic_domains": sorted({e.get("domain", "其他域") for e in schema["entities"]}),
        "instance_counts": {e["id"]: len(data.get(e.get("table", ""), [])) for e in schema["entities"]},
    }


def _infer_relations(data: dict) -> list:
    """外键推断（自动，简化）：`*_id`/`*_code` 列指向另一实体主键 → 关系。"""
    inferred = []
    for table, rows in data.items():
        if not rows:
            continue
        sample = rows[0]
        for col in sample:
            if col.endswith("_id") or col.endswith("_code") or col.endswith("_key"):
                target = col.replace("_id", "").replace("_code", "").replace("_key", "")
                # 目标实体名匹配
                for tname in data:
                    if target.lower() in tname.lower():
                        inferred.append({"id": f"auto_{table}_{col}", "from": _cap(table),
                                         "to": _cap(tname), "fk": f"{table}.{col}", "cardinality": "N:1", "label": "关联", "auto": True})
    return inferred


def _cap(name: str) -> str:
    return name[0].upper() + name[1:] if name else name


def build_graph(data: dict, schema: dict) -> dict:
    """跨表跨域建统一实例图：实体实例 + 关系边（FK join）。"""
    graph = {"nodes": {}, "edges": []}
    entities = schema.get("_entities", {})
    # 外键推断补充关系（跳过 schema 已声明的 FK, 避免重复边）
    declared_fks = {r.get("fk") for r in schema.get("relations", []) if r.get("fk")}
    inferred = [r for r in _infer_relations(data) if r.get("fk") not in declared_fks]
    relations = list(schema.get("relations", [])) + inferred
    # 节点: 各实体实例（明细实体按行建实例, 主实体按主键）
    node_ids = {}
    for eid, ent in entities.items():
        table = ent["table"]
        if table not in data:
            continue
        key = ent["key"]
        detail = ent.get("detail", False)
        for i, row in enumerate(data[table]):
            kid = row.get(key)
            node_id = f"{eid}:{kid}@{i}" if detail else f"{eid}:{kid}"
            graph["nodes"][node_id] = {"entity": eid, "id": kid, "idx": i, "data": row}
            node_ids.setdefault(eid, []).append(node_id)
    # 类别类层级(本体层次深入): 实体含 category 属性 → 建类别类节点 + isA 边
    for eid, ent in entities.items():
        table = ent["table"]
        if table not in data or "category" not in data[table][0]:
            continue
        key = ent["key"]
        detail = ent.get("detail", False)
        cat_nodes = {}
        for i, row in enumerate(data[table]):
            cat = row.get("category")
            if not cat:
                continue
            cat_id = f"Category:{eid}:{cat}"
            if cat_id not in graph["nodes"]:
                graph["nodes"][cat_id] = {"entity": "Category", "id": cat, "data": {"name": cat, "of": eid}}
            src = f"{eid}:{row.get(key)}@{i}" if detail else f"{eid}:{row.get(key)}"
            graph["edges"].append({"from": src, "to": cat_id, "rel": "isA", "label": "属于类别"})
    # 边: FK join 关系（支持 FK 在 from 侧或 to 侧）
    for r in relations:
        if r.get("abstract") or not r.get("fk"):
            continue
        ftable, fcol = r["fk"].split(".")
        if ftable not in data:
            continue
        from_e = entities.get(r["from"], {})
        to_e = entities.get(r["to"], {})
        # 明细实体行号索引（按主键值+行号）
        fk_val_to_nodes = {}
        for nd in node_ids.get(r["to"], []):
            info = graph["nodes"][nd]
            fk_val_to_nodes.setdefault(f"{info['id']}", []).append(nd)
        for i, row in enumerate(data[ftable]):
            val = row.get(fcol)
            if not val:
                continue
            if ftable == from_e.get("table"):
                # FK 在 from 侧: Product.supplier → Supplier.id (或明细实体 Sale.customer_id → Customer)
                if from_e.get("detail"):
                    src = f"{r['from']}:{row.get(from_e['key'])}@{i}"  # 明细实体用行号节点
                else:
                    src = f"{r['from']}:{row.get(from_e['key'])}"
                dsts = fk_val_to_nodes.get(str(val), [])
                for dst in dsts:
                    if src in graph["nodes"]:
                        graph["edges"].append({"from": src, "to": dst, "rel": r["id"], "label": r.get("label", r["id"])})
            else:
                # FK 在 to 侧: inventory.product_id → Product.id
                src = f"{r['from']}:{val}"
                if ftable == to_e.get("table"):
                    # FK 表 = 目标实体表 → 连该行自身节点
                    to_detail = to_e.get("detail", False)
                    dst = f"{r['to']}:{val}@{i}" if to_detail else f"{r['to']}:{val}"
                    if src in graph["nodes"] and dst in graph["nodes"]:
                        graph["edges"].append({"from": src, "to": dst, "rel": r["id"], "label": r.get("label", r["id"])})
                else:
                    for nd in fk_val_to_nodes.get(str(val), []):
                        if src in graph["nodes"]:
                            graph["edges"].append({"from": src, "to": nd, "rel": r["id"], "label": r.get("label", r["id"])})
    return graph


def validate(data: dict, schema: dict) -> list:
    """约束校验：unique/required/positive + 基数。返回问题清单。"""
    issues = []
    entities = schema.get("_entities", {})
    for ent in entities.values():
        table, key = ent["table"], ent["key"]
        if table not in data:
            continue
        seen = set()
        for row in data[table]:
            kid = row.get(key)
            # 明细实体(1:N)主键可重复, 不做唯一
            if not ent.get("detail") and kid in seen:
                issues.append({"severity": "error", "type": "unique", "msg": f"实体 {ent['id']} 主键重复: {kid}"})
            seen.add(kid)
            for attr in ent.get("attributes", []):
                v = row.get(attr["name"])
                if attr.get("required") and (v is None or str(v).strip() == ""):
                    issues.append({"severity": "error", "type": "required", "msg": f"{ent['label']}.{attr['label']} 必填缺失"})
                if attr.get("type") == "number" and v is not None:
                    try:
                        if float(v) < 0 and attr["name"] in ("stock", "price", "cost"):
                            issues.append({"severity": "warn", "type": "positive", "msg": f"{ent['label']}.{attr['label']} 为负: {v}"})
                    except (TypeError, ValueError):
                        pass
    # schema 顶层约束
    for c in schema.get("constraints", []):
        if c.get("type") == "required":
            ent, attr = c["on"].split(".")
            if ent in entities and entities[ent]["table"] in data:
                for row in data[entities[ent]["table"]]:
                    if not row.get(attr):
                        issues.append({"severity": "error", "type": "required", "msg": c.get("msg", "必填缺失")})
                        break
    return issues


def traverse(graph: dict, entity: str, eid) -> list:
    """图遍历（跨域）：从某实体实例出发，经关系到达的所有相关实例。"""
    start = f"{entity}:{eid}"
    if start not in graph["nodes"]:
        return []
    result = []
    for e in graph["edges"]:
        if e["from"] == start:
            result.append({"rel": e["rel"], "label": e["label"], "to": e["to"]})
        elif e["to"] == start:
            result.append({"rel": e["rel"], "label": e["label"], "from": e["from"]})
    return result


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from core.domain_model import load_all
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    schema = load_schema(os.path.join(root, "config", "ontology.json"))
    data = load_all(os.path.join(root, "data"))
    issues = validate(data, schema)
    print(f"约束校验: {len(issues)} 问题", [i["msg"] for i in issues[:5]])
    graph = build_graph(data, schema)
    print(f"本体图: {len(graph['nodes'])} 节点 / {len(graph['edges'])} 关系边")
    rel = traverse(graph, "Supplier", "S01")
    print(f"Supplier S01 关联: {[r['label'] for r in rel[:5]]}")
