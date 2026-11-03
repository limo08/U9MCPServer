# 更新日志 (Changelog)

本项目所有重要变更都会记录在此文件。

格式参考 [Keep a Changelog](https://keepachangelog.com/)，版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

## [0.0.9] - 2026-11-02

U9Mcp 首次提交，作为项目初始版本发布。

### Added（新增）

- **U9C OpenAPI 协议接入**
  - 认证：`GET /webapi/OAuth2/AuthLogin?clientid&clientsecret&entCode&userCode&orgCode`，业务请求统一使用 `token` 请求头；token 过期时自动重登并重试。
  - 查询：`POST /webapi/CommonEntity/Query`，使用 `EntityFullName`、`Filters`、`ReturnFields` 和分页参数。
  - 写操作：`POST /webapi/{Service}/{Action}`，请求体直接传 DTO 或 `OptDocRData[]`。
  - 响应：统一解析 `{"ResCode":0,"Success":true,"ResMsg":"","Data":...}`。
- **107 个 MCP 工具，覆盖 17 个业务域**
  - 通用单据：查询、查看、新增、修改、批量保存、提交、审核、弃审、删除、关闭、打开、作废、挂起/解除挂起等。
  - 采购、销售、库存、生产制造、委外加工、财务收款、成本、固定资产、工作流审批、基础资料、系统与审计等业务域查询。
  - 复合链路：`u9_create_and_audit`、`u9_push_and_audit`。
- **离线 U9C 元数据目录**
  - 随包发布 U9C OpenAPI 规范快照（628 个 Path、157 个 Service、838 个 Schema）。
  - `u9_list_forms` / `u9_get_fields` / `u9_get_bill_template` / `u9_list_form_operations` 无需连接租户即可查看真实 Service、实体、字段与动作。
  - 建立旧版 `F*` 字段/过滤条件到 U9C 字段的兼容翻译层，并在动作解析时以 U9C 摘要为准，避免把 `PurchaseOrder.Release`（挂起）误解为解除挂起。
- **数据库只读直查**
  - `u9_query_table`：按 `u9_schema.json` 与 `INFORMATION_SCHEMA` 双重校验表名/字段名，支持结构化过滤、排序、分页与总数统计。
  - `u9_execute_sql`：执行单条只读 `SELECT` / `WITH`，用于跨表 JOIN 和聚合查询。
  - 所有过滤值参数化绑定；内置只读守卫，拒绝 `INSERT`、`UPDATE`、`DELETE`、`MERGE`、DDL、`EXEC`、`SELECT ... INTO`、`BACKUP/RESTORE` 等写操作。
- **单据附件**
  - `u9_upload_attachment` / `u9_download_attachment` 对接 `AttachmentFileUpload` / `AttachmentFileDownload`。
  - 支持表头附件，Base64 一次性上传下载（U9C 无分块/FileId 续传协议）。
- **财务报表**
  - `u9_query_report` 对接 `Report/GetReportPdfFile`，按 `ReportCaseID` 或订阅报表名生成 PDF，返回 `FileName` + `FileContentBase64`。
- **部署与运行**
  - 支持 stdio 与 streamable-http 两种 MCP 传输方式。
  - 提供 `start.sh`，支持 `start` / `run` / `stop` / `restart` / `status` / `logs` / `check` / `install`。
  - 提供 Dockerfile、docker-compose 与 PyPI 发布流程。
  - MCP 客户端可通过 `.env` 配置 U9C OAuth2、SQL Server 只读连接及服务运行参数。

### Security（安全）

- U9C 认证凭证与 SQL Server 连接信息全部通过环境变量注入，不写入代码仓库。
- SQL Server 直连始终保持只读：U9 的业务规则、审核流与编号规则必须在服务端执行，禁止绕过 WebAPI 直接写业务表。
- 数据库工具对表名、字段名和 SQL 语句做白名单校验与只读守卫，降低注入和误写风险。

### Known limitations（已知限制）

- U9C OpenAPI 未开放成本核算、审计/上机日志、角色权限、编码规则、系统配置、数据备份等 Service/实体；相关工具会返回明确的不支持说明。
- 采购询价、供应商报价、MRP/生产计划/生产汇报、资产折旧调拨等对象没有查询 Service/实体，可通过 `U9_API_ENTITY_MAP` 映射账套自定义实体，或改用数据库只读查询。
- U9C 没有通用下推接口，当前仅支持 `PurchaseOrder/POCreateSO → SO`；其他下推请在 U9 单据转换/界面中配置。
- U9C 没有通用 `BatchSave`、`ExecuteOperation` + `opNumber`、结构化报表等协议，本项目已按 U9C 实际接口替代或返回明确错误。
