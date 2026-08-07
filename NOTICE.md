# NOTICE — 开源声明

## 项目
**sme-decision-ontology**（本体驱动的中小企业数据决策套件）
- 许可协议：**Apache License 2.0**（见 [LICENSE](LICENSE)）
- 仓库：https://github.com/zhengjinjun1975/sme-decision-ontology

## 代码来源声明
本项目**核心代码为原创实现**（纯标准库 Python），不包含对任何第三方开源仓库代码的直接复制。

## 技术依据与借鉴（非代码复制）
1. **决策公式**（再订货点/安全库存/账龄/评分卡/移动平均）为**标准运营管理（Operations Management）公理**，参考了以下开源项目的公式思路作为技术依据，**未复制其代码**：
   - ERPNext（Frappe，GPL-3.0）—— 再订货水平公式 `reorder_level = (日均出库 × 提前期) + 安全库存`
   - InvenTree（MIT）—— 库存/补货字段设计
   - 供应商评分卡、账龄分析、移动平均预测 —— 通用管理科学方法
2. **架构与本体建模思路**借鉴同门项目 **factory-ontology**（Apache-2.0，本账号自研）—— 本地、确定性、可解释、零 token 的定位一脉相承。
3. **MCP 协议**为行业标准（Model Context Protocol），本实现为标准库 stdio JSON-RPC，非复制特定实现。

## 数据声明
`data/` 下所有台账（products/inventory/sales/suppliers/customers/equipment）为**彻底虚构的合成示例**，不涉及任何真实企业数据，不存在隐私/脱敏问题。

## 定位诚实声明
本项目是"数据与决策之间的薄层 / agent 的可信决策 API"，**不是** Odoo/ERPNext 的替代品，也**不包含**财务/人力/战略决策。决策建议是辅助，最终拍板在经营者。

---
*本声明遵循开源合规：原创部分 Apache-2.0；技术公式为行业公理不需署名；无实质性第三方代码派生，故无需附加第三方 LICENSE 全文。*
