# Changelog

## [0.11] — 2026-08-07

### 版本 + 测试 + 审查
- 版本定义为 0.11（run.py + api_server）
- 端到端测试 `e2e_test.py`：17 项全链路（版本/数据→本体/决策/行动/API+前端/MCP/Golden）
- CodeAgent 代码审查（仅 1 已知 SQL 误报 + 1 轻微复杂度）

## [0.10] — 2026-08-07

### 前端 + 部署 + 开源合规
- Web 前端改**亮色/浅色现代审美**（浅灰底 + 白卡片 + 柔和标签）
- 前后端闭环：api_server 托管前端
- 部署：Dockerfile + docker-compose.yml + requirements.txt
- 开源声明：NOTICE.md（代码原创/公式借鉴/架构同门/合成数据/诚实定位）

## [0.1] — 2026-08-07

### MVP：一本体多决策
- 统一领域模型（产品/供应商/客户/订单/库存/设备/成本）
- 4 决策模块组 8 决策（补货/缺货/呆滞/预测/比价/供应商/信用/维护）
- 确定性规则（标准运营管理公式，零 token）
- 选择性部署（deployment.json）
- 行动闭环（action.py：采购单草稿/预警/催收/工单）
- MCP server + NL 决策入口（回显校验）
- 多源数据（CSV/Excel/SQLite/MySQL/PG，表名白名单）
- Golden test（pytest 12 项）
