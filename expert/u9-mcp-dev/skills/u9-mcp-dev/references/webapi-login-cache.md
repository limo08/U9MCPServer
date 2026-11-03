# U9C OpenAPI 登录机制与元数据缓存

> 适用：WebAPI 集成、工具开发。当前项目统一使用 **U9C OpenAPI**。

## 1. 登录方式

U9C 使用 OAuth2：

```text
GET /webapi/OAuth2/AuthLogin
    ?clientid=<CLIENT_ID>
    &clientsecret=<CLIENT_SECRET>
    &entCode=<企业编码>
    &userCode=<账号>
    &orgCode=<组织编码>
```

可选参数：`loginType` / `loginDate` / `language`。登录成功后，所有请求必须带请求头：

```http
token: <AuthLogin 返回的 token>
```

环境变量：

| 变量 | 说明 |
|------|------|
| `U9_API_SERVER_URL` | U9C 地址，如 `https://your-u9c-server` |
| `U9_API_CLIENT_ID` | OpenAPI 客户端 ID |
| `U9_API_CLIENT_SECRET` | OpenAPI 客户端密钥 |
| `U9_API_ENT_CODE` | 企业编码 `entCode` |
| `U9_API_ORG_CODE` | 组织编码 `orgCode` |
| `U9_API_USERNAME` | 登录账号 `userCode` |
| `U9_API_TOKEN` | 可选：静态 token，设置后跳过 OAuth2 登录 |
| `U9_API_LANGUAGE` | 可选：语言，如 `zh-CN` |

U9C 使用 OAuth2 + `token` 请求头，不依赖 Cookie 会话，也不提供按员工身份
透传的代理调用头。

## 2. 查询与动作

| 目的 | 端点 |
|------|------|
| 查询 | `POST /webapi/CommonEntity/Query` |
| 新增 | `POST /webapi/{Service}/Create` |
| 修改 | `POST /webapi/{Service}/Modify` |
| 删除 | `POST /webapi/{Service}/Delete` |
| 提交 | `POST /webapi/{Service}/Submit` |
| 审核 | `POST /webapi/{Service}/Approve` |
| 反审核 | `POST /webapi/{Service}/UnApprove` |
| 其他动作 | `POST /webapi/{Service}/{Action}` |

响应统一为：

```json
{"ResCode": 0, "Success": true, "ResMsg": "", "Data": [], "Exception": ""}
```

动作语义以 U9C OpenAPI 的 `summary` 为准，不要按经验硬编码。例如：

- `PurchaseOrder.Release` = 挂起采购订单
- `PurchaseOrder.Hold` = 解除挂起采购订单
- `SO.CancelReleaseSO` = 取消下达销售订单
- `SO.ReleaseSO` = 下达销售订单

## 3. 元数据缓存

- 元数据来自随包发布的 `src/u9_mcp/data/u9c_openapi.json`（628 paths / 157 Services / 838 schemas），离线可查。
- 磁盘缓存：`~/.workbuddy/u9_metadata_cache/`；只接受 `Source == "U9C"` 的缓存。
- 探字段：`u9_get_fields`；查动作：`u9_list_form_operations`；强制刷新：`u9_refresh_metadata`。
- 旧 F* 字段是兼容别名，会通过 `u9c_mapping` 翻译为 U9C 字段；新代码应优先使用目录返回的 U9C 字段名。

## 4. 直连排查

1. 调 `AuthLogin` 获取 token。
2. 后续请求带 `token` 请求头。
3. 查询用 `CommonEntity/Query`，不要再用 `ExecuteBillQuery`。
4. 附件用 `AttachmentFileUpload` / `AttachmentFileDownload`；报表用 `Report/GetReportPdfFile`（返回 PDF）。
