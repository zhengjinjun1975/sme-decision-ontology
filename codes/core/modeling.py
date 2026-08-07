#!/usr/bin/env python3
"""modeling.py — AI 原生建模（中庸：规则兜底确定性 + LLM 增强可选）

从台账数据自动建议本体 schema：实体(表)/属性(列+类型)/关系(外键)/约束(唯一/必填)。
规则引擎兜底（确定性，零 token）；LLM 可选增强（中文 label / 补充关系），本地优先。

原则：LLM 生成建议，规则兜底，人拍板。AI 是建模助手。
"""
import os
import json


def _guess_type(vals: list) -> str:
    """从样本猜属性类型（中庸：number/date/enum/string）。"""
    sample = [v for v in vals if v is not None and str(v).strip() != ""][:5]
    if not sample:
        return "string"
    if all(isinstance(v, (int, float)) or str(v).replace(".", "", 1).isdigit() for v in sample):
        return "number"
    if all(str(v).strip().lower() in ("true", "false", "是", "否", "0", "1") for v in sample):
        return "enum"
    if all("-" in str(v) and str(v)[:4].isdigit() for v in sample):
        return "date"
    if len(set(sample)) <= 8 and len(sample) >= 2:
        return "enum"
    return "string"


def suggest_schema(data: dict, table_prefix: str = "") -> dict:
    """规则推断本体 schema：实体/属性/关系/约束（确定性，零 token 兜底）。"""
    entities = []
    relations = []
    constraints = []
    for table, rows in data.items():
        if not rows:
            continue
        eid = table[0].upper() + table[1:]
        cols = list(rows[0].keys())
        attrs = []
        for col in cols:
            if col == "id":
                attrs.insert(0, {"name": col, "type": "string", "label": "编号"})
                continue
            vals = [r.get(col) for r in rows]
            attrs.append({"name": col, "type": _guess_type(vals), "label": col})
        # 主键推断: id 列或 *xx_id 列
        key = "id" if "id" in cols else (cols[0] if "id" in cols else next((c for c in cols if c.endswith("_id")), cols[0]))
        entities.append({"id": eid, "label": eid, "table": table, "key": key,
                         "attributes": attrs, "detail": key not in ("id",) and any(r.get(key) and str(r[key]).startswith("P") for r in rows[:5]) if rows else False})
        # 外键关系推断（单复数词干匹配: products↔product）
        for col in cols:
            if col.endswith("_id") or col.endswith("_code"):
                raw = col.replace("_id", "").replace("_code", "")
                target = raw[0].upper() + raw[1:]
                stem = raw.rstrip("s")  # 去尾 s 匹配复数表名
                # 匹配已有实体(表名/词干)
                matched = next((e["id"] for e in entities if e["id"].lower() == target.lower() or e["id"].lower() == stem.lower() or e["table"].lower().rstrip("s") == stem.lower()), None)
                if matched:
                    relations.append({"id": f"{matched.lower()}_{col}", "from": matched, "to": eid,
                                      "fk": f"{table}.{col}", "cardinality": "N:1", "label": "关联"})
        if "id" in cols:
            constraints.append({"type": "unique", "on": f"{eid}.id", "msg": f"{eid} 编号唯一"})
    return {"version": "1.0", "entities": entities, "relations": relations, "constraints": constraints}


def llm_enhance(schema: dict, use_llm: bool = True) -> dict:
    """LLM 可选增强：中文 label（本地优先，不可用则回落规则推断的 label）。"""
    if not use_llm:
        return schema
    try:
        from core.model_llm import llm_generate
    except ImportError:
        return schema
    # 给实体/属性生成中文 label（若没有）
    need = [(e["id"], e.get("label")) for e in schema["entities"] if e.get("label") == e["id"]]
    if not need:
        return schema
    prompt = "为以下实体生成中文名，仅输出JSON {'实体id':'中文名'}: " + json.dumps([n for n, _ in need], ensure_ascii=False)
    try:
        text = llm_generate(prompt, temperature=0.1, max_tokens=200)
        labels = json.loads(text[text.find("{"):text.rfind("}")+1]) if "{" in text else {}
        for e in schema["entities"]:
            if e["id"] in labels:
                e["label"] = labels[e["id"]]
    except Exception:
        pass
    return schema


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from core.domain_model import load_all
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data = load_all(os.path.join(root, "data"))
    schema = suggest_schema(data)
    print(f"AI 原生建模建议: {len(schema['entities'])} 实体 / {len(schema['relations'])} 关系 / {len(schema['constraints'])} 约束")
    for e in schema["entities"]:
        print(f"  {e['id']} ({e['key']}) 属性={len(e['attributes'])}")
    print("关系:", [(r['from'], r['to']) for r in schema['relations']])
