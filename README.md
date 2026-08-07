# 基于企业本体的智能经营决策平台

> **数据与决策之间的薄层，agent 的可信决策 API。** 把企业进销存+运维台账变成**可拍板的确定性决策建议**（本地、零 token、可解释）。企业级价值链本体 → 决策规则 → 行动清单。

[![Version](https://img.shields.io/badge/version-0.11-blue.svg)](CHANGELOG.md)
[![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)

## 它解决什么问题

中小企业有台账（进销存/客户/设备），但**做不了决策**——数据躺着，靠经验拍板。Odoo/ERPNext 太重、InvenTree 只存不决、金蝶用友上云数据出厂。

**sme-decision-ontology** 填补真空：把台账自动变成**补货/缺货/呆滞/预测/比价/供应商/信用/维护** 8 类确定性决策建议，本地跑、零 token、每条带公式依据、能导出行动清单。

## 快速开始

```bash
# 1. 克隆后, 直接跑决策(自带合成示例数据)
cd sme-decision-ontology
python codes/run.py decision          # 跑所有启用模块

# 2. Golden test
python -m pytest tests/

# 3. 端到端测试
python codes/e2e_test.py              # 17 项全链路

# 4. Web 前端 + API
pip install -r requirements.txt
python -m uvicorn codes.api_server:app --port 8000
# 打开 http://localhost:8000  → 亮色决策看板
```

示例输出（每条可解释，带公式依据）：
```
🟡 [建议] P01 → 补货 | D1补货: stock=50 < reorder_level=100 (日均出库10×提前期7+安全库存30)
🟠 [预警] P02 → 缺货预警 | D2缺货: stock=20 < safety_stock=25
```

## 换你自己的数据（3 步）

1. 把企业台账放 `data/`（products/inventory/sales/suppliers/customers/equipment.csv）
2. 调阈值 `config/thresholds.json`（安全库存/账龄/周转率）
3. 跑 `python codes/run.py decision` 或 `python codes/e2e_test.py`

## 核心组件

```
codes/
├── core/
│   ├── domain_model.py   # 统一领域模型(产品/供应商/客户/订单/库存/设备/成本)
│   ├── data_mapper.py    # 多源数据接入(CSV/Excel/SQLite/MySQL/PG/手工, 表名白名单)
│   └── registry.py       # 模块注册表 + 选择性部署
├── decisions/            # 4 决策模块组(可选择性部署)
│   ├── inventory.py      # D1补货 + D2缺货 + D3呆滞
│   ├── procurement.py    # D4比价 + D5供应商绩效
│   ├── sales.py          # D6预测 + D7信用
│   └── equipment.py      # D8设备维护
├── action.py             # 决策→行动闭环(采购单草稿/预警/催收/工单/CSV导出)
├── api_server.py         # FastAPI + 前端托管
├── mcp_server.py         # MCP(decide/actions/thresholds)
├── run.py                # CLI
└── e2e_test.py           # 端到端测试(17项)
web/index.html            # 亮色决策看板
```

## 8 个决策（确定性规则，标准运营管理公式）

| 决策 | 公式 |
|------|------|
| 补货 | `reorder = 日均出库×提前期 + 安全库存`（借鉴 ERPNext） |
| 缺货 | 当前库存 < 安全库存 |
| 呆滞 | 周转率 < 阈值 |
| 销售预测 | 移动平均 |
| 采购比价 | 综合成本加权 |
| 供应商绩效 | 交期/质量/价格评分卡 |
| 客户信用 | 账龄分析 / DSO |
| 设备维护 | 保修/服役/状态 |

**原则**：规则算，人拍板。每个建议带依据，零 token、零 ML、可解释。

## AI 原生

- **MCP server**：暴露决策给任意 MCP-native agent（`decide`/`actions`/`thresholds`），可信决策 API
- **自然语言问决策**：`POST /ask` 结构化路由 + 歧义回显校验（NL 是辅助，主入口是结构化）
- **模型层**：本地 Ollama 优先，远端 DeepSeek 降级（`config/model_config.json`）

## 部署（Docker 一键）

```bash
docker compose up -d     # 构建 + 启动 API + 前端
# 访问 http://<服务器IP>:8000
```

- `Dockerfile`：python:3.11-slim + fastapi/uvicorn + 健康检查
- `docker-compose.yml`：挂载 `./data` 放真实台账、`./config` 放阈值
- 可选 nginx HTTPS 反向代理（注释已给）

## 定位与横向对比（诚实）

| 方案 | 部署 | 决策智能 | 轻量 | 本地 |
|------|------|:---:|:---:|:---:|
| Odoo | 重(多模块) | 弱(存储为主) | ❌ | 可 |
| ERPNext | 重 | 弱 | ❌ | 可 |
| InvenTree | 中 | **无决策** | 中 | ✅ |
| 金蝶/用友 | 云 SaaS | 弱 | ❌ | ❌(数据出厂) |
| **sme-decision-ontology** | **极轻** | **✅ 确定性决策** | **✅** | **✅** |

**差异化**：本地 + 轻量 + 确定性决策(零token可解释) + 本体驱动 + 选择性部署——**不是** ERP/OA/CRM 替代品，是补它们缺的**决策层**。

## 设计原则（六条通用经验）

1. 规则算，人拍板——决策是给人，不是替代人
2. 不轻易升维——纯函数规则，不引重型框架
3. 决策不落地就是报表——行动闭环是核心
4. 数据接入是 80% 的活——一等公民
5. 阈值按行业可配——不硬编码
6. 诚实边界——只做进销存+运维，不做财务/人力/战略

## 版本更新记录

- **v0.11**：版本定义 + 端到端测试(17项) + CodeAgent 审查
- **v0.10**：亮色前端 + 前后端闭环 + 部署( Dockerfile/compose/requirements ) + 开源声明(NOTICE)
- **v0.1**：MVP（一本体多决策 + 8 决策 + 行动闭环 + MCP/NL + 多库）

## 文档

- [架构设计-修订版](docs/架构设计-修订版.md)（含 OpenClaw 审查 + 技术完整性分析）
- [开源声明](NOTICE.md)
- [CHANGELOG](CHANGELOG.md)

## 实测验证

- pytest 12 项（决策规则 + AI原生 + 多库）
- e2e 17 项（版本/数据→本体/决策/行动/API+前端/MCP/Golden）
- CodeAgent 代码审查（仅 1 已知 SQL 误报 + 1 轻微复杂度）
- 决策公式参照 ERPNext 权威实现

## 诚实边界

- 决策域限"进销存+运维"运营闭环，**不含财务/人力/战略**
- 决策建议是**辅助**，最终拍板在经营者
- 阈值需按行业/企业调整
- 数据为**合成示例**（彻底虚构），真实落地需真实台账 + 阈值调优
- MySQL/PG 对接已写，但**需真实数据库验证**

## License

[Apache License 2.0](LICENSE) · [开源声明](NOTICE.md)
