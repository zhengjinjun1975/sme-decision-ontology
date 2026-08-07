#!/usr/bin/env python3
"""run.py — sme-decision-ontology CLI（最小代码）

用法:
  python run.py setup <data_dir>     # 加载数据到内存
  python run.py decision <模块>       # 跑某决策模块(inventory/procurement/sales/equipment)
  python run.py decision             # 跑所有启用模块
  python run.py list                 # 列出决策模块
"""
import sys, os, json

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

__version__ = "0.11"


def _load_data(data_dir=None):
    from core.domain_model import load_all
    data_dir = data_dir or os.path.join(ROOT, "..", "data")
    return load_all(data_dir)


def _enabled():
    from core.registry import enabled_modules
    cfg_path = os.path.join(ROOT, "..", "config", "deployment.json")
    return enabled_modules(cfg_path)


def main():
    if len(sys.argv) < 2:
        print(__doc__); return
    cmd = sys.argv[1]
    if cmd == "list":
        from core.registry import REGISTRY
        for name in sorted(_enabled()):
            print(f"  ✅ {name}")
        return
    if cmd == "decision":
        data = _load_data()
        mods = [sys.argv[2]] if len(sys.argv) > 2 else _enabled()
        for name in mods:
            try:
                mod = __import__(f"decisions.{name}", fromlist=["decide"])
                suggestions = mod.decide(data)
                print(f"\n══ {name} ({len(suggestions)} 条建议) ══")
                for s in suggestions[:10]:
                    mark = {"告急": "🔴", "预警": "🟠", "建议": "🟡"}.get(s.get("level", ""), "·")
                    print(f"  {mark} [{s.get('level')}] {s.get('entity')} → {s.get('action')} | {s.get('reason')}")
            except ImportError as e:
                print(f"  ❌ 模块 {name} 未启用或缺失: {e}")
        return
    print(__doc__)


if __name__ == "__main__":
    main()
