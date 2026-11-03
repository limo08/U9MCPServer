# U9C 单据附件上传与下载

依据 U9C OpenAPI 的 `AttachmentFile` 服务实现：

- 上传：`POST /webapi/AttachmentFile/AttachmentFileUpload`
- 下载：`POST /webapi/AttachmentFile/AttachmentFileDownload?handler=...`
- 按单据列附件：`AttachmentFile/AttachmentFileDownloadByDocID?docid=...`
- 删除：`AttachmentFile/AttachmentFileDelete`

工具只传输 Base64，不读取或写入 MCP 服务器本地文件；调用方负责文件读写和编解码。
示例编号为占位数据，请替换成目标账套中有权限访问的已存在单据。

> ⚠️ U9C 没有 4 MiB 分块 / `FileId` 续传协议，也不支持该接口的
> 分录级附件。一次上传一个完整文件，只支持表头附件。

## 1. 上传表头附件

```json
{
  "params": {
    "form_id": "PUR_PurchaseOrder",
    "bill_id": "100723",
    "bill_no": "CGDD000198",
    "file_name": "说明.txt",
    "send_byte": "MTIzNA=="
  }
}
```

`MTIzNA==` 是文本 `1234` 的 Base64。

MCP 生成的实际请求体：

```json
{
  "EntityID": "100723",
  "EntityType": "UFIDA.U9.PM.PO.PurchaseOrder",
  "files": [
    {"FileName": "说明.txt", "FileSize": 4, "FileContent": "MTIzNA=="}
  ]
}
```

- `EntityType` 默认取 catalog 中该 form_id 的实体全名，也可通过 `entity_type` 覆盖；
- `flow_id` 可选，映射 `FlowID`；
- `bill_no` 保留用于兼容，U9C 以 `bill_id`（EntityID）为准；
- `is_last` 必须为 `true`；
- `file_id` / `entry_key` / `entry_id` 必须为空，否则模型校验直接拒绝；
- 单文件上限 4 MiB（MCP 本地限制）。

成功响应（U9C `FileResult`）：

```json
{
  "op": "upload_attachment",
  "success": true,
  "handler": "h-1",
  "file_id": "h-1",
  "file_name": "说明.txt",
  "file_size": 4,
  "is_last": true,
  "attachment_ids": ["h-1"],
  "next_action": null
}
```

`Handler` 是后续下载标识；`file_id` 是兼容旧调用方的别名。

## 2. 字段映射

| MCP 参数 | U9C 字段 | 说明 |
|----------|----------|------|
| `bill_id` | `EntityID` | 已存在单据 ID |
| `form_id` / `entity_type` | `EntityType` | 实体全名 |
| `flow_id` | `FlowID` | 审批流 ID，可选 |
| `file_name` | `files[].FileName` | 含扩展名，不是路径 |
| `send_byte` | `files[].FileContent` | 完整文件标准 Base64 |
| `decoded_size` | `files[].FileSize` | 由 MCP 自动计算 |
| `bill_no` | — | 兼容字段，不发送 |
| `alias_file_name` | — | 兼容字段，不发送 |
| `entry_key` / `entry_id` | — | 不支持，必须为空 |

## 3. 下载

```json
{
  "params": {"handler": "23d8a447a9254a788f2d12a499898755"}
}
```

`file_id` 仍可作为 `handler` 的兼容别名；`start_index` 必须为 0。

U9C 返回：

```json
{
  "IsSuccess": true,
  "Handler": "23d8...",
  "FileName": "说明.txt",
  "FileSize": 4,
  "FileUrl": "https://..."
}
```

MCP 处理：

1. 若 `FileResult.FileContent` 存在，直接作为 Base64 返回；
2. 否则请求 `FileUrl`，把响应字节编码为 Base64；
3. 返回 `file_part` / `file_name` / `file_size` / `handler` / `is_last=true`。

响应示例：

```json
{
  "op": "download_attachment",
  "success": true,
  "handler": "23d8...",
  "file_id": "23d8...",
  "file_name": "说明.txt",
  "file_size": 4,
  "file_part": "MTIzNA==",
  "start_index": 0,
  "is_last": true,
  "next_action": null
}
```

调用方应把 `file_part` Base64 解码为字节，并核对 `file_size`。远端 `file_name`
视为不可信文件名，写入用户选定位置前需防路径穿越。

## 4. 失败处理

- 业务失败：返回 `success=false` + `errors[].message`，不自动重试；
- 上传网络中断/响应无法解析：返回 `outcome_unknown=true`，先到 U9C 单据附件页核对，
  不要直接重传；
- 仅 HTTP 401 / token 过期会自动重登并重试一次；
- 下载返回 `FileUrl` 后取文件失败会返回 `附件文件下载 HTTP <code>`；
- 日志不记录附件内容、文件名、Handler 或 token。

## 5. 验证建议

1. 先用 `u9_view_bill` 确认单据 ID；
2. 上传小文件，确认返回 `Handler`；
3. 用同一 `Handler` 下载并比对字节与大小；
4. 中文文件名、大文件（接近 4 MiB）各测一次；
5. 上传不会触发提交/审核，验证后按需删除测试附件。

U9C 附件接口为一次性上传，没有分块游标，因此不存在“续传/拼接”步骤。
