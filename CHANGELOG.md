# Changelog

## [0.12] — 2026-08-07

### 完整模型使用闭环 + 决策执行闭环 + LLM 解释层 + 跨行业泛化 + 增量更新
- **完整模型使用闭环**：`check_active_model` 模型守卫（云端无 key 明确报错）；数据加载(目录/上传/连库)边界守卫；`/model/check`；DeepSeek key 从环境变量 `DEEPSEEK_API_KEY` 读取（权威来源，不落盘不入仓库，实测可用后本地清除）
- **LLM 切实参与本体建模**：`/modeling/suggest` 展示 有LLM(生成中文label) vs 无LLM(英文表名) 区别；本地 Ollama + 云端 DeepSeek 均验证生成 9 实体中文 label
- **LLM 问答兜底**：`/ask` 规则未命中时本地 Ollama/云端参与回答（mode=llm）
- **决策执行闭环**：`/actions/{id}/complete` 标记完成 + actions_state 存储 + `/decision/threshold-adapt` 阈值自适应建议（补货后仍缺→提高 safety_stock）
- **LLM 解释层**：`core/model_llm.py` 新建，`/decision/summary` 生成自然语言执行摘要（按数据 hash 缓存，秒回）
- **增量数据更新**：本体建模确立数据后，数据更新因需而变只变变动部分不全部重建（domain_model.load_table + 按 mtime 只重读变更表）
- **跨行业泛化**：消除硬编码，domain_model 动态发现表/前端域动态构建/自适应 schema；已验证 阀门(178) + 食品(43) 两行业
- **本体图**：ECharts graph（力导向自动分离）+ 企业 hub 连实体 + 决策依据区 + 高清导出桌面（"保存本体图到本地"按钮）
- 版本 0.11 → 0.12

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
