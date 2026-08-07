# -*- coding: utf-8 -*-
"""生成企业本体完整图 PNG 到桌面(PIL 无重依赖)。"""
import os, sys, json
sys.path.insert(0, r"E:\open-source\sme-decision-ontology\codes")
from core.domain_model import load_all
from core import ontology as ont

ROOT = r"E:\open-source\sme-decision-ontology"
data = load_all(os.path.join(ROOT, "data"))
schema = ont.load_schema(os.path.join(ROOT, "config", "ontology.json"))
g = ont.build_graph(data, schema)
dom = {e["id"]: e.get("domain", "其他域") for e in schema["entities"]}
nodes = [{"id": nid, "entity": n["entity"], "domain": dom.get(n["entity"], "其他域"),
          "name": n["data"].get("name") or n["data"].get("id")} for nid, n in g["nodes"].items()]
edges = g["edges"]
print("节点:", len(nodes), "边:", len(edges))

# ---- 布局: 企业顶部 → 业务域列 → 实体实例 ----
W,H = 1800,1200
domains = list(dict.fromkeys(n["domain"] for n in nodes))
cx = W//2
pos = {"__hub__": (cx, 70)}
gap = W//(len(domains)+1)
entity_y = {}
for n in nodes:
    d = n["domain"]
    entity_y.setdefault(d, 200)
    if n["entity"] not in [p for p in pos]:
        pass
# 按域列 + 实体内堆叠
by_entity = {}
for n in nodes:
    by_entity.setdefault(n["entity"], []).append(n)
col = {d: i+1 for i,d in enumerate(domains)}
ent_y = {}
for et, arr in by_entity.items():
    d = arr[0]["domain"]
    dx = col[d]*gap
    y = ent_y.get(d, 200)
    for i, n in enumerate(arr):
        pos[n["id"]] = (dx + (i%4)*70, y + (i//4)*40)
    ent_y[d] = y + ((len(arr)+3)//4)*40 + 40

# ---- PIL 绘制 ----
from PIL import Image, ImageDraw, ImageFont
COLORS = {"Product":"#2f6bff","Supplier":"#27ae60","Inventory":"#f39c12","Sale":"#e74c3c","Customer":"#8e44ad","Equipment":"#16a085","Category":"#95a5a6","Purchase":"#e67e22","Production":"#1abc9c","Payment":"#c0392b"}
font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 11)
fontb = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 16)
img = Image.new("RGB", (W,H), "#ffffff")
dr = ImageDraw.Draw(img)
# 边
for e in edges:
    if e["from"] in pos and e["to"] in pos:
        dr.line([pos[e["from"]], pos[e["to"]]], fill="#d6e4ff", width=1)
# 企业 hub
dr.ellipse([cx-32,40,cx+32,104], fill="#2f6bff")
dr.text((cx-16,58),"企业",fill="#fff",font=fontb)
# 节点
for n in nodes:
    x,y = pos[n["id"]]
    c = COLORS.get(n["entity"],"#7f8c8d")
    dr.ellipse([x-5,y-5,x+5,y+5], fill=c)
    dr.text((x+8,y-6), str(n["name"])[:8], fill="#1a2233", font=font)
# 域标签
for d in domains:
    dr.text((col[d]*gap-20, 180), d, fill="#7f8c8d", font=fontb)
# 保存桌面
desk = os.path.join(os.path.expanduser("~"), "Desktop", "企业本体图.png")
img.save(desk)
print("已保存:", desk)

