# 用友U9 MCP Server：让 Claude、Cursor 等 AI 直接操作 ERP

> 本文介绍如何通过 MCP（Model Context Protocol）协议，让 AI 助手直接操作用友U9 ERP，实现采购、销售、库存等业务的自然语言自动化。

## 背景

你有没有遇到过这种场景：

- 业务人员需要查询本月采购订单，要在用友里点好几层菜单
- 想批量审核一批入库单，需要一条条手动操作
- 想用 AI 帮你处理 ERP 数据，但 AI 根本不认识用友

**用友 MCP Server** 就是为了解决这个问题而生的。

## 什么是 MCP？

MCP（Model Context Protocol）是 Anthropic 推出的开放协议，让 AI 助手（Claude、Cursor、Windsurf 等）可以通过标准化接口调用外部工具和服务。

简单理解：**MCP = 给 AI 装上操作外部系统的"手"**。

## 用友 MCP Server 能做什么？

安装后，你可以直接对 AI 说：

- "查询最近 20 条已审核的采购订单"
- "查一下物料编码 MAT001 的即时库存"
- "帮我新建一张采购订单，供应商 S001，物料 MAT001，数量 100"
- "审核这几张入库单：12345, 12346"

AI 会自动调用用友 WebAPI 完成操作，**无需手动登录 ERP 界面**。

## 对实施与开发的价值

**实施阶段**
- 快速验证配置：用自然语言直接查数据，无需逐层点菜单
- 数据核查：批量查询单据状态、库存数量，快速定位问题
- 客户演示：现场说"查一下你们的采购订单"，AI 实时返回结果，演示效果直观

**日常使用**
- 业务人员自助查询，减少依赖实施人员的频率
- 批量提交、审核单据，替代重复的手工操作
- 通过微信 / WhatsApp 直接操作用友，无需打开 ERP 客户端

**开发阶段**
- 用 `u9_list_forms`、`u9_get_fields` 快速探索表单结构，替代翻文档
- 自然语言调试接口，比手写 API 请求效率更高
- 可作为内部工具基础进行二次开发，快速扩展自定义工具

## 支持的功能

目前提供 **86 个工具**，覆盖生产、成本、资产、审计、采购、销售、库存等 **13 大业务域**：

**通用单据（10）**：保存/提交/审核/反审核/删除、查看详情、保存前校验(validate_bill)、复合「新建并审核」「下推并审核」
**生产制造（12）**：生产订单、MRP 运算结果、生产计划、生产汇报、生产入库、生产领料下推
**成本核算（12）**：材料成本、成本计算、成本趋势、实际 vs 标准成本对比、完工产品成本、成本调整单
**固定资产（6）**：资产卡片、资产折旧、资产盘点、资产调拨、资产新增
**库存（9）**：即时库存、出入库单据、调拨（直接/申请）、库存盘点
**审计合规（7）**：操作日志、变更日志、审核日志、复合工作流
**采购（4）**：采购订单、采购申请、采购询价、采购进度
**销售（2）**：销售订单、销售报价单
**工作流/审批（4）**：待审批、审批流、工作流审批
**基础资料/权限（4）**：物料、客户/供应商、用户、角色
**元数据/探查（8）**：字段探查、表单列表、单据模板、SQL Server 表/字段/结构探查
**系统/查询（4）**：系统配置、质量检验、费用报销、数据备份
**统计（2）**：调用统计、用量报告

## 支持的 AI 客户端

- **Claude Desktop**（最推荐，原生支持）
- **Cursor**（写代码的同时查 ERP 数据）
- **Windsurf**
- **Cline**
- **Continue**
- **Claude Code CLI**
- **OpenClaw**（通过微信/WhatsApp/Telegram 操作用友！将本项目 PyPI 地址发给 OpenClaw，它会自动完成安装并引导填写用友配置）

## 快速开始

### 1. 安装

```bash
pip install u9-mcp
```

### 2. 准备用友账号

准备一个用友 U9C 账号（建议专用集成账号，不要用 Administrator），并在 U9C 中创建 OpenAPI 客户端（`clientid` / `clientsecret`）。本服务使用 **OAuth2** 登录，只要该账号有对应模块的操作权限即可。

### 3. 配置 Claude Desktop

编辑 `%APPDATA%\Claude\claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "u9": {
      "command": "uvx",
      "args": ["u9-mcp"],
      "env": {
        "U9_API_SERVER_URL": "https://your-u9c-server",
        "U9_API_CLIENT_ID": "你的客户端ID",
        "U9_API_CLIENT_SECRET": "你的客户端密钥",
        "U9_API_ENT_CODE": "企业编码",
        "U9_API_ORG_CODE": "组织编码",
        "U9_API_USERNAME": "用友账号"
      }
    }
  }
}
```

### 4. 重启客户端，开始使用

> **OpenClaw 用户**：使用 `openclaw mcp set` 配置后会自动热加载，**无需重启网关**。

## 项目地址

- Gitee 镜像（**国内访问最快，推荐**）：https://gitee.com/huangdouu/U9MCP
- GitHub：https://github.com/limo08/U9MCPServer
- 官网文档：https://limo08.github.io/U9MCPServer/
- PyPI：https://pypi.org/project/u9-mcp/

欢迎 Star、Issues 和 PR！

---

**关键词**：用友MCP、用友U9AI、MCP Server、用友ERP自动化、Claude用友、用友API集成、AI操作ERP
