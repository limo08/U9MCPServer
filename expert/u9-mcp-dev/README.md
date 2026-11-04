# 用友 MCP 开发团（U9 MCP Dev Squad）

一个 WorkBuddy Team 型专家团，专注把用友U9开放平台 ApiDoc 里的接口全量集成进 [u9-mcp](https://github.com/limo08/U9MCPServer) 这个 Python + MCPServer（mcp 2.x）项目。

## 类型

Team 型（多角色协作团队）


## 核心能力

- 将 `https://openapi.yyu9c.com/doc.html` 的 **16 业务领域 / 77 模块 / 标准 WebAPI 动作集** 集成进 `u9-mcp`。
- 基于真实 U9C 环境（配置 `U9_API_SERVER_URL` 与 OAuth2 五参数）做字段探查与本地联调。
- 规避本环境二开坑：`SAL_SaleOrder` 二开版、`FCUSTID` 全大写客户字段、`TRNV_Receipt` / `TRNV_PaymentSlip` 二开收付款单、`BD_Material` 的 `FBaseUnitId`。
- 复用提速工具：`u9_validate_bill`、`u9_get_bill_template`、`u9_refresh_metadata`。
- 跑全量回归：
  - `python bin/kmcp list-tools` 统计工具数
  - `python bin/kmcp test` 跑 evals/tests
  - `python bin/kmcp coverage` 输出 ApiDoc 覆盖进度
  - `python bin/kmcp build` 构建 wheel / sdist

## 使用示例

- 「把用友 ApiDoc【供应链 → 采购管理】的接口集成进 u9-mcp，先探字段再写工具。」
- 「跑一遍 evals 回归，确认现有 86 个工具没有被破坏。」
- 「准备 0.3.0 发布：更新 CHANGELOG、构建并上传 PyPI。」

## 头像

头像已自动生成在 `avatars/` 目录下（6 张，统一 blue-purple 工程风格，512×512 PNG，单张 < 500 KB）。如需替换为自定义头像，要求：

- 格式：PNG（推荐）或 JPG
- 尺寸：512×512 px
- 大小：单张不超过 500 KB

## 安装

将专家包目录放到专家目录下：

```bash
C:\Users\ZnL\.workbuddy\plugins\marketplaces\my-experts\plugins\u9-mcp-dev\
```

然后运行注册命令使其可见：

```bash
python3 scripts/register_expert.py <expert-dir>
```

## 打包分享

```bash
python3 scripts/package_expert.py plugins/u9-mcp-dev
```

打包产物为 `u9-mcp-dev.zip`，可直接分享或上架。
