# sme-decision-ontology — 本体驱动的中小企业数据决策套件

> 数据与决策之间的薄层，agent 的可信决策 API。仿 factory-ontology，把中小企业进销存台账变成**可拍板的确定性决策建议**（本地、零 token、可解释）。

[![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)

## 定位

**轻量决策层**：替代常规 OA/ERP/CRM 的"报表+决策建议"部分。本地、轻量、确定性、可解释。
- 不做存储流程（ERP 做），做**决策**（本产品做）
- 决策是给人拍板的，**规则算、人拍板**；agent 可调（可信决策 API）

## 一本体多决策

统一领域模型（产品/供应商/客户/订单/库存/设备/成本）建模一次，4 个决策模块组复用：

| 模块组 | 决策 | 规则 |
|--------|------|------|
| **inventory** | 补货/缺货/呆滞 | reorder=(日均出库×提前期)+安全库存（ERPNext 公式） |
| **procurement** | 比价/供应商绩效 | 综合成本加权、评分卡 |
| **sales** | 销售预测/客户信用 | 移动平均、账龄/DSO |
| **equipment** | 设备维护 | 保修/服役/状态 |

**选择性部署**：`config/deployment.json` 只启需要的模块组，不强制全装。

## 用法

```bash
python codes/run.py decision              # 跑所有启用模块的决策
python codes/run.py decision inventory    # 只跑库存决策
python codes/run.py list                  # 列出启用模块
python -m pytest tests/                   # Golden test(决策规则单测)
```

示例输出（可解释，每条带公式依据）：
```
🟡 [建议] P01 → 补货 | D1补货: stock=50 < reorder_level=100 (日均出库10×提前期7+安全库存30)
🟠 [预警] P02 → 缺货预警 | D2缺货: stock=20 < safety_stock=25
```

## 数据多源

`core/data_mapper.py` 抽象多源：CSV / Excel(可选openpyxl) / SQLite / MySQL-PG(ERP对接) / 手工，统一映射到领域模型。SQLite 表名白名单校验（安全加固）。

## AI 原生

- **规则算，LLM 讲**：计算层零 token 确定性，LLM 只做解释
- **MCP server**：暴露决策给任意 MCP-native agent（`decide`/`actions`/`thresholds`，可信决策 API）
- **自然语言问决策**：`POST /ask` 结构化路由 + 歧义回显校验
- **模型层**：本地 Ollama 优先（`config/model_config.json` 的 active），远端 DeepSeek 降级

## 决策到行动闭环

`action.py` 把决策建议变成可执行行动项：
- 库存补货 → **采购单草稿**（产品/数量/供应商）
- 缺货/呆滞 → **库存预警**
- 客户逾期 → **催收清单** / 超额度 → **信用预警**
- 设备 → **维护工单**
- 可导出 CSV（`python action.py`）

## API

```bash
python -m uvicorn codes.api_server:app   # 启动 API
GET  /decisions/inventory   # 跑某决策模块
GET  /decisions            # 全部决策
GET  /actions              # 行动清单
POST /ask {"question":"库存补货"}   # 自然语言问决策(回显校验)
```

## 技术依据

- 8 决策 = 标准运营管理公式（再订货点/账龄/评分卡/移动平均），纯 Python 确定性实现
- 补货公式借鉴 **ERPNext**(37.7k★) 权威实现
- 竞品定位：Odoo/ERPNext 太重、InvenTree 只存不决、金蝶用友上云——本产品是真空

## 架构文档

- [架构设计-修订版](docs/架构设计-修订版.md)（含 OpenClaw 审查 + 技术完整性分析）

## 诚实边界

- 决策域限"进销存+运维"运营闭环，**不含财务/人力/战略**
- 决策建议是**辅助**，最终拍板在经营者
- 阈值需按行业/企业调整（`config/thresholds.json`）
- 数据为**合成示例**（彻底虚构），真实落地需真实台账 + 阈值调优

## License

[Apache License 2.0](LICENSE)
