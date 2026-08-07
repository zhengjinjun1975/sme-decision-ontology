#!/usr/bin/env python3
"""e2e_test.py — sme-decision-ontology 端到端测试（全链路）"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "codes"))

TOTAL = FAILED = 0


def ck(name, cond, extra=""):
    global TOTAL, FAILED
    TOTAL += 1
    if not cond:
        FAILED += 1
    print(f"  {'✅' if cond else '❌'} {name} {extra}")


def main():
    print("══ 一、版本 ══")
    import run
    ck("版本 0.11", run.__version__ == "0.11", f"({run.__version__})")

    print("\n══ 二、数据→本体 ══")
    from core.domain_model import load_all
    data = load_all(os.path.join(ROOT, "data"))
    ck("加载 6 表", len(data) == 6)
    ck("各表非空", all(len(v) > 0 for v in data.values()))

    print("\n══ 三、决策规则 ══")
    from decisions import inventory, procurement, sales, equipment
    sug_inv = inventory.decide(data)
    sug_sal = sales.decide(data)
    sug_eq = equipment.decide(data)
    ck("库存决策有建议", len(sug_inv) > 0, f"({len(sug_inv)})")
    ck("销售/信用决策", len(sug_sal) > 0, f"({len(sug_sal)})")
    ck("设备维护决策", len(sug_eq) > 0, f"({len(sug_eq)})")
    all_sug = sug_inv + sug_sal + sug_eq + procurement.decide(data)
    ck("建议可解释(含reason/level)", all("reason" in s and "level" in s for s in all_sug))

    print("\n══ 四、行动闭环 ══")
    import action
    acts = action.suggestions_to_actions(all_sug, data)
    ck("生成行动清单", len(acts) > 0, f"({len(acts)})")
    ck("含采购单草稿", any(a["type"] == "采购单草稿" for a in acts))

    print("\n══ 五、API + 前端 ══")
    import api_server
    from fastapi.testclient import TestClient
    c = TestClient(api_server.app)
    ck("前端托管(/)", c.get("/").status_code == 200)
    ck("GET /decisions", c.get("/decisions").json()["ok"])
    ck("GET /actions", c.get("/actions").json()["ok"])
    ck("POST /ask 库存", c.post("/ask", json={"question": "库存补货"}).json()["module"] == "inventory")
    ck("POST /ask 歧义回显", c.post("/ask", json={"question": "采购和库存"}).json()["mode"] == "confirm")

    print("\n══ 六、MCP ══")
    import mcp_server
    r = mcp_server._handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    ck("MCP 握手", "sme-decision-mcp" in r["result"]["serverInfo"]["name"])
    r = mcp_server._handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    ck("MCP tools", {"decide", "actions", "thresholds"} <= {t["name"] for t in r["result"]["tools"]})

    print("\n══ 七、Golden test ══")
    import subprocess
    r = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q"], cwd=ROOT, capture_output=True, text=True, timeout=120)
    ck("pytest 全过", r.returncode == 0 and "passed" in r.stdout, r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "")

    print(f"\n══ E2E 结果: {TOTAL - FAILED}/{TOTAL} 通过 ══")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
