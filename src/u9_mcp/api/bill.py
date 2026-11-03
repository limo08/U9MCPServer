"""api.bill"""

from typing import Any

from ._delegates import _get_metadata_validator, _post_raw, _query_metadata
from . import mcp
from ..config import u9c_catalog
from ..config.bill_templates import BILL_TEMPLATES
from ..models.query import BatchSaveInput, BillIdsInput, CreateAndAuditInput, CreateLxBillingInput, PushAndAuditInput, PushDownInput, SaveInput
from ..models.system import ExecuteActionInput, ExecuteOperationInput
from ..services.bill_ops import _operation_resolve_error, _resolve_execute_operation, _run_execute_action
from ..services.metadata import MetadataValidator
from ..utils.errors import _err, _result_status
from ..utils.formatting import _fmt



@mcp.tool(
    name="u9_save_bill",
    annotations={"title": "新建或修改单据", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": False}
)
async def u9_save_bill(params: SaveInput) -> str:
    """新建或修改 U9C 单据（采购订单、销售订单等）。

    - 新建：model 中不传 ID/FID，服务端生成主键
    - 修改：model 中传 ID（旧版 FID 也兼容）
    - 自动纠错：按 U9C 目录修正字段名，并报告无法识别的字段
    - 底层：新建调 `POST /webapi/{Service}/Create`，修改调
      `POST /webapi/{Service}/Modify`（Service 不提供 Modify 时会明确报错）

    新建采购订单 model 示例（U9C 字段名）：
    {
      "BusinessDate": "2026-01-15",
      "Supplier": {"Code": "S001"},
      "PurDept": {"Code": "D001"},
      "POLineDTOList": [
        {"ItemInfo": {"Code": "MAT001"}, "ReqQtyTU": 100,
         "FinallyPriceTC": 10.5, "DeliveryDate": "2026-02-01"}
      ]
    }

    旧版 F* 字段（FDate / FSupplierId / FPOOrderEntry / FQty 等）仍会通过
    `u9c_mapping` 翻译，便于历史调用迁移。

    Returns:
        str: JSON，含保存结果的 ID / DocNo（旧版返回 FID / FBillNo）
    """
    try:
        # 构建 U9 Save API 格式：
        # data 内部 Model（单据字段）和 NeedUpDateFields 等是同级兄弟节点
        model = dict(params.model)
        # 新建时不传 ID/FID（U9C 由服务端生成），修改时保留原 ID/FID
        if model.get("ID") in (None, "", 0, "0") and model.get("FID") in (None, "", 0, "0"):
            model.setdefault("FID", 0)

        # 尝试自动修正字段名（基于元数据）
        auto_fixes = []
        unknown_fields = []
        validator = await _get_metadata_validator(params.form_id)
        if validator:
            model, auto_fixes, unknown_fields = validator.validate_and_fix(model)

        # ⚠️ 本环境用友 Save 对字段顺序敏感：财务信息(含 FIN，如 FQUOTATIONFIN)
        # 必须排在分录(含 ENTRY，如 FQUOTATIONENTRY)之前，否则分录单价被判定为 0
        # 而报“含税单价不能小于等于0”。做防御性排序：所有非 ENTRY 键（含 FIN/表头）
        # 统一置于 ENTRY 键之前，保持表头→FIN→ENTRY 的已知可用顺序。
        _keys = list(model.keys())
        _entry_keys = [k for k in _keys if "ENTRY" in k.upper()]
        _non_entry = [k for k in _keys if k not in _entry_keys]
        if _entry_keys and len(_non_entry) != len(_keys):
            model = {k: model[k] for k in _non_entry + _entry_keys}

        result = await _post_raw(
            "save",
            params.form_id,
            model,
            need_update_fields=params.need_update_fields,
            need_return_fields=["FID", "FBillNo"],
            is_delete_entry=params.is_delete_entry,
        )

        # 提取新建单据的 FID 和 FBillNo，使用结构化结果
        status_data = _result_status(result, "save")
        if status_data.get("success"):
            status_data["tip"] = "单据已保存为草稿，需要提交+审核后才能生效"
            # 如果有自动修正，记录到结果中（含中文字段名）
            if auto_fixes:
                status_data["auto_fixes"] = auto_fixes
                status_data["tip"] += f"（自动修正了 {len(auto_fixes)} 处字段名，详见 auto_fixes）"
            # 无法识别的字段必须报出来 —— 它们会被用友静默丢弃，用户以为传进去了
            if unknown_fields:
                status_data["unknown_fields"] = unknown_fields
                status_data["tip"] += (
                    f"（另有 {len(unknown_fields)} 个字段无法识别、用友可能不认，"
                    f"详见 unknown_fields）"
                )
        else:
            # 保存失败时也要报出字段问题 —— 这才是用户真正卡住的地方
            if auto_fixes:
                status_data["auto_fixes"] = auto_fixes
            if unknown_fields:
                status_data["unknown_fields"] = unknown_fields
                status_data["field_hint"] = (
                    "部分字段无法识别（见 unknown_fields），"
                    "请用 u9_get_fields 查该单据的真实字段名后重试"
                )
        return _fmt(status_data)
    except Exception as e:
        return _err(e, op="save")


@mcp.tool(
    name="u9_validate_bill",
    annotations={"title": "保存前校验单据", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_validate_bill(params: SaveInput) -> str:
    """保存前校验单据模型（不真正保存），秒级反馈结构是否正确，避免反复试错。

    返回：
    - ok: 是否通过（无缺失必填、无结构问题）
    - is_new: 是否新建（model 无 FID）
    - auto_fixes: 将被自动更名的字段 [{"from","to","location"}]（如 FCustId→FCUSTID）
    - missing_required: 缺失的顶层必填字段
    - entry_issues: 分录中缺失的必填子字段 / 结构异常
    - suggestions: 修正建议清单

    典型用法：先用本工具校验 -> 按 suggestions 修正 -> 再调用 u9_save_bill，一次成功。
    """
    try:
        model = dict(params.model)
        if model.get("ID") in (None, "", 0, "0") and model.get("FID") in (None, "", 0, "0"):
            model.setdefault("FID", 0)

        validator = await _get_metadata_validator(params.form_id)
        if not validator:
            return _fmt({"ok": False, "error": "无法获取该表单元数据，无法校验（请检查 form_id 是否正确或网络是否可达）"})

        fixed, fixes, unknown = validator.validate_and_fix(model)

        # 缺失必填（顶层，非分录）
        head_field_names = {k for k, d in validator.fields.items() if not d.is_entry}
        present_top = set(fixed.keys())
        missing_required = [req for req in validator.get_required_fields() if req not in present_top]

        # 分录必填检查
        entry_issues = []
        for entry_name, entry_def in validator.fields.items():
            if not entry_def.is_entry or entry_name not in fixed:
                continue
            req_children = {c.name for c in entry_def.children if c.must_input}
            entries = fixed[entry_name]
            if not isinstance(entries, list):
                entry_issues.append({"entry": entry_name, "issue": "应为数组"})
                continue
            for idx, ent in enumerate(entries):
                if not isinstance(ent, dict):
                    continue
                miss = [c for c in req_children if c not in ent]
                if miss:
                    entry_issues.append({"entry": entry_name, "row": idx, "missing_required": miss})

        ok = (len(missing_required) == 0 and len(entry_issues) == 0 and len(unknown) == 0)
        suggestions = []
        if missing_required:
            suggestions.append(f"补齐顶层必填字段：{', '.join(missing_required)}")
        for ei in entry_issues:
            if "missing_required" in ei:
                suggestions.append(f"{ei['entry']} 第{ei['row']}行缺失必填：{', '.join(ei['missing_required'])}")
        if fixes:
            suggestions.append(
                f"保存时将自动修正 {len(fixes)} 处字段名（详见 auto_fixes，含中文字段名对照）"
            )
        for u in unknown:
            suggestions.append(
                f"字段「{u['field']}」无法识别，将被忽略 —— "
                f"请用 u9_get_fields 查真实字段名（详见 unknown_fields）"
            )

        return _fmt({
            "ok": ok,
            "is_new": model.get("ID", model.get("FID", 0)) in (0, None, ""),
            "auto_fixes": fixes,
            "unknown_fields": unknown,
            "missing_required": missing_required,
            "entry_issues": entry_issues,
            "suggestions": suggestions,
            "tip": "校验通过，可直接调用 u9_save_bill；如有缺失请补齐后重试" if ok else "请按 suggestions 修正后再保存",
        })
    except Exception as e:
        return _err(e, op="validate")


@mcp.tool(
    name="u9_get_bill_template",
    annotations={"title": "获取单据模板", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
)
async def u9_get_bill_template(form_id: str) -> str:
    """获取常用单据的「已验证 model 骨架」模板（销售报价单/销售订单/采购订单等）。

    返回该表单的正确字段名、必填项、分录必填字段组成的 model 示例，AI 只需替换占位符填业务数据，
    跳过字段摸索。占位符形如 <客户编码>。保存前建议再用 u9_validate_bill 校验。

    支持的 form_id：SAL_Quotation / SAL_SaleOrder / PUR_PurchaseOrder（其它表单返回提示）。
    """
    try:
        tpl = BILL_TEMPLATES.get(form_id)
        if not tpl:
            return _fmt({
                "ok": False,
                "form_id": form_id,
                "supported": list(BILL_TEMPLATES.keys()),
                "tip": "该表单暂无预置模板，请用 u9_get_fields 查真实字段后自行构造 model，并用 u9_validate_bill 校验",
            })
        return _fmt({
            "ok": True,
            "form_id": form_id,
            "desc": tpl.get("_desc", ""),
            "template": {k: v for k, v in tpl.items() if k != "_desc"},
            "tip": "替换 <...> 占位符后调用 u9_validate_bill 校验，再 u9_save_bill 保存",
        })
    except Exception as e:
        return _err(e, op="get_bill_template")


@mcp.tool(
    name="u9_refresh_metadata",
    annotations={"title": "刷新表单元数据缓存", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": False}
)
async def u9_refresh_metadata(form_id: str) -> str:
    """强制重建指定表单的 U9C 元数据缓存（忽略内存/磁盘缓存）。

    元数据重新从随包发布的 U9C OpenAPI 目录生成，不访问 U9 租户接口。
    返回是否成功及字段数量；刷新后 u9_validate_bill / u9_save_bill 使用新定义。
    """
    try:
        metadata = await _query_metadata(form_id, force=True)
        if not metadata:
            return _fmt({"ok": False, "form_id": form_id, "error": "U9C 目录中没有该 form_id 对应的 Service/字段"})
        validator = MetadataValidator(metadata, form_id=form_id)
        MetadataValidator.set(form_id, validator)
        return _fmt({
            "ok": True,
            "form_id": form_id,
            "field_count": len(validator.fields),
            "tip": "元数据已刷新，校验/保存将使用新定义",
        })
    except Exception as e:
        return _err(e, op="refresh_metadata")


@mcp.tool(
    name="u9_submit_bills",
    annotations={"title": "提交单据", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": False}
)
async def u9_submit_bills(params: BillIdsInput) -> str:
    """提交单据（草稿 → 待审核）。

    返回结构化结果：success=true 时包含 next_action 字段，建议调用 u9_audit_bills 完成审核。

    Returns:
        str: JSON，含 success / next_action / bill_ids 字段
    """
    try:
        succeeded, failed = [], []
        for bill_id in params.bill_ids:
            try:
                r = await _post_raw("submit", params.form_id, {"Ids": bill_id})
                s = _result_status(r, "submit")
                if s.get("success"):
                    succeeded.append(bill_id)
                else:
                    failed.append({"id": bill_id, "errors": s.get("errors", [])})
            except Exception as ex:
                failed.append({"id": bill_id, "error": f"{type(ex).__name__}: {ex}"[:300]})
        return _fmt({
            "op": "submit", "success": len(failed) == 0,
            "total": len(params.bill_ids),
            "succeeded_count": len(succeeded), "failed_count": len(failed),
            "succeeded_ids": succeeded, "failed_details": failed,
            "next_action": "audit" if len(succeeded) > 0 else None,
            "next_action_desc": "建议调用 u9_audit_bills 审核已提交单据" if succeeded else None,
        })
    except Exception as e:
        return _err(e, op="submit")


@mcp.tool(
    name="u9_audit_bills",
    annotations={"title": "审核单据", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": False}
)
async def u9_audit_bills(params: BillIdsInput) -> str:
    """审核单据（待审核 → 已审核）。

    返回结构化结果：success=true 时表示单据已生效，next_action=null。

    Returns:
        str: JSON，含 success / bill_ids 字段
    """
    try:
        succeeded, failed = [], []
        for bill_id in params.bill_ids:
            try:
                r = await _post_raw("audit", params.form_id, {"Ids": bill_id})
                s = _result_status(r, "audit")
                if s.get("success"):
                    succeeded.append(bill_id)
                else:
                    failed.append({"id": bill_id, "errors": s.get("errors", [])})
            except Exception as ex:
                failed.append({"id": bill_id, "error": f"{type(ex).__name__}: {ex}"[:300]})
        return _fmt({
            "op": "audit", "success": len(failed) == 0,
            "total": len(params.bill_ids),
            "succeeded_count": len(succeeded), "failed_count": len(failed),
            "succeeded_ids": succeeded, "failed_details": failed,
            "tip": "单据已审核生效。如需修改，请先调用 u9_unaudit_bills 反审核" if succeeded else None,
        })
    except Exception as e:
        return _err(e, op="audit")


@mcp.tool(
    name="u9_unaudit_bills",
    annotations={"title": "反审核单据", "readOnlyHint": False, "destructiveHint": True,
                 "idempotentHint": False, "openWorldHint": False}
)
async def u9_unaudit_bills(params: BillIdsInput) -> str:
    """反审核单据（已审核 → 待审核）。反审核后可重新修改和提交。

    返回结构化结果：success=true 时表示单据已回到待审核状态。

    Returns:
        str: JSON，含 success / bill_ids 字段
    """
    try:
        succeeded, failed = [], []
        for bill_id in params.bill_ids:
            try:
                r = await _post_raw("unaudit", params.form_id, {"Ids": bill_id})
                s = _result_status(r, "unaudit")
                if s.get("success"):
                    succeeded.append(bill_id)
                else:
                    failed.append({"id": bill_id, "errors": s.get("errors", [])})
            except Exception as ex:
                failed.append({"id": bill_id, "error": f"{type(ex).__name__}: {ex}"[:300]})
        return _fmt({
            "op": "unaudit", "success": len(failed) == 0,
            "total": len(params.bill_ids),
            "succeeded_count": len(succeeded), "failed_count": len(failed),
            "succeeded_ids": succeeded, "failed_details": failed,
            "tip": "已反审核，可修改后重新提交+审核" if succeeded else None,
        })
    except Exception as e:
        return _err(e, op="unaudit")


@mcp.tool(
    name="u9_delete_bills",
    annotations={"title": "删除单据", "readOnlyHint": False, "destructiveHint": True,
                 "idempotentHint": False, "openWorldHint": False}
)
async def u9_delete_bills(params: BillIdsInput) -> str:
    """删除单据（仅草稿状态可删除，已提交/已审核的单据需先反审核）。

    返回结构化结果：success=true 时表示删除成功。

    Returns:
        str: JSON，含 success / bill_ids 字段
    """
    try:
        succeeded, failed = [], []
        for bill_id in params.bill_ids:
            try:
                r = await _post_raw("delete", params.form_id, {"Ids": bill_id})
                s = _result_status(r, "delete")
                if s.get("success"):
                    succeeded.append(bill_id)
                else:
                    failed.append({"id": bill_id, "errors": s.get("errors", [])})
            except Exception as ex:
                failed.append({"id": bill_id, "error": f"{type(ex).__name__}: {ex}"[:300]})
        return _fmt({
            "op": "delete", "success": len(failed) == 0,
            "total": len(params.bill_ids),
            "succeeded_count": len(succeeded), "failed_count": len(failed),
            "succeeded_ids": succeeded, "failed_details": failed,
            "tip": "已删除成功的单据不可恢复，请重新创建" if succeeded else None,
        })
    except Exception as e:
        return _err(e, op="delete")


@mcp.tool(
    name="u9_cancel_bills",
    annotations={"title": "撤销单据/基础资料", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": False}
)
async def u9_cancel_bills(params: ExecuteActionInput) -> str:
    """撤销/取消下达（U9C 服务端动作，默认解析 CancelReleaseSO / CancelAssign）。

    - 适用于提供“取消下达/撤销”动作的 Service，例如销售订单 ``SO`` 的
      ``CancelReleaseSO``（取消下达）。
    - 不同 Service 的撤销语义不同；目标 Service 没有对应 Action 时会返回明确错误。
    - 传参：bill_ids（ID 列表，优先）或 bill_nos（DocNo/Code 列表），至少一个。
    - 二开或特殊 Service 可显式传 operation（真实 U9C Action 名）。
    - 端点：``POST /webapi/{Service}/{Action}``，请求体 ``OptDocRData[]``。

    Returns:
        str: JSON，含 success / fid / ids / action / endpoint 字段
    """
    if params.operation:
        return await _run_execute_action(params, params.operation, "cancel_assign", "explicit")
    return await _run_execute_action(params, "CancelAssign", "cancel_assign", "fixed",
                                     endpoint="cancel_assign")


@mcp.tool(
    name="u9_void_bills",
    annotations={"title": "作废单据", "readOnlyHint": False, "destructiveHint": True,
                 "idempotentHint": False, "openWorldHint": False}
)
async def u9_void_bills(params: ExecuteActionInput) -> str:
    """终止/作废单据（默认 U9C Action：Cancel）。

    - U9C 动作语义以 OpenAPI 摘要为准。例如 ``PurchaseOrder.Cancel`` 的摘要为
      “终止采购订单”；不同 Service 可能没有 Cancel。
    - 传参：bill_ids（ID 列表，优先）或 bill_nos（DocNo/Code 列表），至少一个。
    - 目标 Service 不支持 Cancel 时会返回明确错误（可用
      u9_list_form_operations 查看真实 Action）；可用 operation 显式覆盖。
    - 端点：``POST /webapi/{Service}/{Action}``。

    Returns:
        str: JSON，含 success / fid / ids / action / endpoint 字段
    """
    action = params.operation or "Cancel"
    source = "explicit" if params.operation else "fixed"
    return await _run_execute_action(params, action, "void", source)


@mcp.tool(
    name="u9_close_bill",
    annotations={"title": "整单关闭单据", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": False}
)
async def u9_close_bill(params: ExecuteActionInput) -> str:
    """整单关闭单据（U9C 常见 Action：Close）。

    - 适用于提供整单关闭动作的 Service（如 ``PurchaseOrder.Close``、
      ``SO.Close``）；行关闭是 ``CloseLine``，本工具不处理行级动作。
    - 解析优先级：显式 operation > U9C 动作摘要按中文名「整单关闭/关闭单据」匹配 >
      固定候选 ``Close``。
    - 传参：bill_ids（ID 列表，优先）或 bill_nos（DocNo/Code 列表），至少一个。
    - 端点：``POST /webapi/{Service}/{Action}``。

    Returns:
        str: JSON，含 success / fid / ids / action / action_source / endpoint 字段
    """
    if params.operation:
        action, source, matched = params.operation, "explicit", ""
    else:
        action, source, matched, available = await _resolve_execute_operation(
            params.form_id, None,
            match_names=["整单关闭", "关闭单据", "关闭"],
            exclude_names=["反", "业务", "行", "应付", "终止", "冻结", "打开"],
        )
        if not action:
            action, source = "Close", "fixed"
    return await _run_execute_action(params, action, "close", source, matched)


@mcp.tool(
    name="u9_unclose_bill",
    annotations={"title": "整单反关闭单据", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": False}
)
async def u9_unclose_bill(params: ExecuteActionInput) -> str:
    """整单反关闭/打开单据（U9C 常见 Action：Open）。

    - 适用于提供整单打开动作的 Service（如 ``PurchaseOrder.Open``、
      ``SO.Open``）；行打开是 ``OpenLine``，本工具不处理行级动作。
    - 解析优先级：显式 operation > U9C 动作摘要按中文名「整单反关闭/反关闭/打开」
      匹配 > 固定候选 ``Open``。
    - 传参：bill_ids（ID 列表，优先）或 bill_nos（DocNo/Code 列表），至少一个。
    - 端点：``POST /webapi/{Service}/{Action}``。

    Returns:
        str: JSON，含 success / fid / ids / action / action_source / endpoint 字段
    """
    if params.operation:
        action, source, matched = params.operation, "explicit", ""
    else:
        action, source, matched, available = await _resolve_execute_operation(
            params.form_id, None,
            match_names=["整单反关闭", "反关闭", "打开"],
            exclude_names=["业务", "行", "应付", "关闭"],
        )
        if not action:
            action, source = "Open", "fixed"
    return await _run_execute_action(params, action, "unclose", source, matched)


@mcp.tool(
    name="u9_forbid_bills",
    annotations={"title": "禁用基础资料", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": False}
)
async def u9_forbid_bills(params: ExecuteActionInput) -> str:
    """挂起/禁用基础资料（按 U9C 动作摘要自动解析）。

    - U9C 命名不统一：``PurchaseOrder.Release`` 摘要为“挂起采购订单”，
      ``Receivement.HoldLine`` 才是行挂起；因此本工具读取 OpenAPI 摘要，
      选择含「挂起/禁用/冻结/停用」且不含「解除/启用」的动作。
    - 若无法从摘要解析，再尝试固定候选 Forbid/Disable/Suspend。
    - 传参：bill_ids（ID 列表，优先）或 bill_nos（Code 列表），至少一个。
    - 目标 Service 没有挂起/禁用动作时返回明确错误；可显式传 operation。

    Returns:
        str: JSON，含 success / fid / ids / action / endpoint 字段
    """
    if params.operation:
        return await _run_execute_action(params, params.operation, "forbid", "explicit")
    action, source = "Forbid", "fixed"
    return await _run_execute_action(params, action, "forbid", source)


@mcp.tool(
    name="u9_enable_bills",
    annotations={"title": "反禁用基础资料", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": False}
)
async def u9_enable_bills(params: ExecuteActionInput) -> str:
    """解除挂起/反禁用基础资料（按 U9C 动作摘要自动解析）。

    - U9C 命名不统一：``PurchaseOrder.Hold`` 摘要为“解除挂起采购订单”；
      因此本工具读取 OpenAPI 摘要，选择含「解除/反禁用/启用/恢复/解冻」的动作。
    - 若无法从摘要解析，再尝试固定候选 Enable/UnForbid/Resume。
    - 传参：bill_ids（ID 列表，优先）或 bill_nos（Code 列表），至少一个。
    - 目标 Service 没有解除动作时返回明确错误；可显式传 operation。

    Returns:
        str: JSON，含 success / fid / ids / action / endpoint 字段
    """
    if params.operation:
        return await _run_execute_action(params, params.operation, "enable", "explicit")
    action, source = "Enable", "fixed"
    return await _run_execute_action(params, action, "enable", source)


@mcp.tool(
    name="u9_push_bill",
    annotations={"title": "下推单据", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": False}
)
async def u9_push_bill(params: PushDownInput) -> str:
    """源单据下推生成目标单据。

    ⚠️ U9C OpenAPI **没有通用下推接口**，每个 Service 只暴露自己的转换动作。
    当前实现明确支持：

    - 采购订单 → 销售订单（协同）：
      ``form_id=PUR_PurchaseOrder``、``target_form_id=SAL_SaleOrder``，
      调用 ``PurchaseOrder/POCreateSO``，源单据编号放在 ``Numbers``。

    其他下推（销售出库、采购入库、收料、退货等）需要在 U9 单据转换/UI 中配置，
    或使用目标 Service 的 ``CreateXxxBySrc`` 动作。本工具不会伪造通用 Push 端点，
    遇到不支持组合会返回明确错误。

    U9C 动作通常直接作用于源单据编号（DocNo/Code），不依赖旧版的
    RuleId / IsEnableDefaultRule / IsDraftWhenSaveFail 参数。

    Returns:
        str: JSON，含 success / source_bill_nos / target_form_id，成功时含目标单据信息
    """
    try:
        push_data: dict[str, Any] = {
            "TargetFormId": params.target_form_id,
            "Numbers": params.source_bill_nos,
        }
        if params.rule_id:
            push_data["RuleId"] = params.rule_id
        if params.enable_default_rule:
            push_data["IsEnableDefaultRule"] = "true"
        if params.draft_on_fail:
            push_data["IsDraftWhenSaveFail"] = "true"
        result = await _post_raw("push", params.form_id, push_data)
        status_data = _result_status(result, "push")
        # 提取生成的目标单据编号
        rs = result.get("Result", result) if isinstance(result, dict) else {}
        numbers = rs.get("Numbers", [])
        ids = rs.get("Ids", [])
        if status_data.get("success"):
            status_data["source_bill_nos"] = params.source_bill_nos
            status_data["target_form_id"] = params.target_form_id
            if numbers:
                status_data["target_bill_nos"] = numbers
            if ids:
                status_data["target_fids"] = ids if isinstance(ids, list) else [ids]
            status_data["tip"] = (
                f"已生成 {len(numbers)} 张目标单据，"
                "请依次调用 u9_submit_bills + u9_audit_bills 完成提交和审核"
            )
        return _fmt(status_data)
    except Exception as e:
        return _err(e, op="push")


@mcp.tool(
    name="u9_create_and_audit",
    annotations={"title": "创建并审核单据（一站式）", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": False}
)
async def u9_create_and_audit(params: CreateAndAuditInput) -> str:
    """一次性走完 Save → Submit → Audit 三步，避免 AI 漏掉中间步骤。

    任意一步失败即停止（不自动重试），返回 halted_at 和 recovery_hint 告诉 AI
    从哪里手动接手。失败日志按整体 op="create_and_audit" 记录一次（不会三倍膨胀）。

    适用场景：明确要"一条龙"创建并使单据生效，没有中间审批/校验需求。
    需要中间步骤校验时，请改用手工链路 u9_save_bill → u9_submit_bills → u9_audit_bills。

    Returns:
        str: JSON。成功：success=true、halted_at=null、steps 三条均 success。
             失败：success=false、halted_at 指出卡点、recovery_hint 给出下一步建议。
    """
    steps: list[dict] = []
    out: dict[str, Any] = {"op": "create_and_audit", "success": False, "halted_at": None, "steps": steps}

    # Step 1: Save
    try:
        model = dict(params.model)
        if model.get("ID") in (None, "", 0, "0") and model.get("FID") in (None, "", 0, "0"):
            model.setdefault("FID", 0)
        save_result = await _post_raw(
            "save",
            params.form_id,
            model,
            need_update_fields=params.need_update_fields,
            need_return_fields=["FID", "FBillNo"],
            is_delete_entry=params.is_delete_entry,
        )
    except Exception as e:
        steps.append({"op": "save", "success": False, "exception": f"{type(e).__name__}: {e}"})
        out["halted_at"] = "save"
        out["recovery_hint"] = "Save 抛异常未生成草稿，无需清理。修正 model 后重试 u9_create_and_audit 或调用 u9_save_bill。"
        return _err(e, extra_errors=[{"step": "save", "stage_summary": out}], op="create_and_audit")

    save_status = _result_status(save_result, "save")
    fid = save_status.get("fid")
    bill_no = save_status.get("bill_no")
    step_save = {"op": "save", "success": save_status.get("success", False)}
    if fid:
        step_save["fid"] = fid
        out["fid"] = fid
    if bill_no:
        step_save["bill_no"] = bill_no
        out["bill_no"] = bill_no
    if not save_status.get("success"):
        step_save["errors"] = save_status.get("errors", [])
        steps.append(step_save)
        out["halted_at"] = "save"
        out["errors"] = save_status.get("errors", [])
        out["recovery_hint"] = "Save 失败：检查 errors[].matched.suggestion；修正 model 后重试。"
        # 失败日志只在 composite 层记一次
        try:
            from scripts.failure_log import FailureLogger
            FailureLogger().log("create_and_audit", out)
        except Exception:
            pass
        return _fmt(out)
    steps.append(step_save)

    # Step 2: Submit
    try:
        submit_result = await _post_raw("submit", params.form_id, {"Ids": str(fid)})
    except Exception as e:
        steps.append({"op": "submit", "success": False, "exception": f"{type(e).__name__}: {e}"})
        out["halted_at"] = "submit"
        out["recovery_hint"] = (
            f"草稿已生成 (fid={fid}, bill_no={bill_no})。Submit 抛异常。"
            f"可手动调用 u9_submit_bills(form_id=\"{params.form_id}\", bill_ids=[\"{fid}\"]) 重试，"
            f"或先 u9_delete_bills 清理草稿。"
        )
        return _err(e, extra_errors=[{"step": "submit", "stage_summary": out}], op="create_and_audit")

    submit_status = _result_status(submit_result, "submit")
    step_submit = {"op": "submit", "success": submit_status.get("success", False)}
    if not submit_status.get("success"):
        step_submit["errors"] = submit_status.get("errors", [])
        steps.append(step_submit)
        out["halted_at"] = "submit"
        out["errors"] = submit_status.get("errors", [])
        out["recovery_hint"] = (
            f"草稿已生成 (fid={fid})。Submit 失败：检查 errors[].matched.suggestion。"
            f"修正后调用 u9_submit_bills(form_id=\"{params.form_id}\", bill_ids=[\"{fid}\"]) 重试。"
        )
        try:
            from scripts.failure_log import FailureLogger
            FailureLogger().log("create_and_audit", out)
        except Exception:
            pass
        return _fmt(out)
    steps.append(step_submit)

    # Step 3: Audit
    try:
        audit_result = await _post_raw("audit", params.form_id, {"Ids": str(fid)})
    except Exception as e:
        steps.append({"op": "audit", "success": False, "exception": f"{type(e).__name__}: {e}"})
        out["halted_at"] = "audit"
        out["recovery_hint"] = (
            f"已 Save+Submit (fid={fid})。Audit 抛异常。"
            f"可手动调用 u9_audit_bills(form_id=\"{params.form_id}\", bill_ids=[\"{fid}\"]) 重试。"
        )
        return _err(e, extra_errors=[{"step": "audit", "stage_summary": out}], op="create_and_audit")

    audit_status = _result_status(audit_result, "audit")
    step_audit = {"op": "audit", "success": audit_status.get("success", False)}
    if not audit_status.get("success"):
        step_audit["errors"] = audit_status.get("errors", [])
        steps.append(step_audit)
        out["halted_at"] = "audit"
        out["errors"] = audit_status.get("errors", [])
        out["recovery_hint"] = (
            f"已 Save+Submit (fid={fid})。Audit 失败（典型原因：必录字段未补、关联数据缺失）："
            f"检查 errors[].matched.suggestion；修正后调用 u9_audit_bills 重试。"
        )
        try:
            from scripts.failure_log import FailureLogger
            FailureLogger().log("create_and_audit", out)
        except Exception:
            pass
        return _fmt(out)
    steps.append(step_audit)

    out["success"] = True
    out["next_action"] = None
    out["tip"] = "工作流完成，单据已审核生效。如需修改，请先 u9_unaudit_bills 反审核。"
    return _fmt(out)


@mcp.tool(
    name="u9_push_and_audit",
    annotations={"title": "下推并审核目标单（一站式）", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": False}
)
async def u9_push_and_audit(params: PushAndAuditInput) -> str:
    """一次性走完 Push → (可选 Submit + Audit) 全流程。

    Push 生成的目标单默认是草稿；本工具自动批量提交+审核所有生成的目标单 FID。
    任何一步失败即停止；失败日志按整体 op="push_and_audit" 记录一次。

    auto_submit_audit=False 时退化为纯 push（与 u9_push_bill 等价，但返回 steps 结构）。

    Returns:
        str: JSON。含 steps、target_bill_nos、target_fids、halted_at / recovery_hint。
    """
    steps: list[dict] = []
    out: dict[str, Any] = {
        "op": "push_and_audit", "success": False, "halted_at": None, "steps": steps,
        "source_bill_nos": params.source_bill_nos, "target_form_id": params.target_form_id,
    }

    # Step 1: Push
    push_data: dict[str, Any] = {
        "TargetFormId": params.target_form_id,
        "Numbers": params.source_bill_nos,
    }
    if params.rule_id:
        push_data["RuleId"] = params.rule_id
    if params.enable_default_rule:
        push_data["IsEnableDefaultRule"] = "true"
    if params.draft_on_fail:
        push_data["IsDraftWhenSaveFail"] = "true"

    try:
        push_result = await _post_raw("push", params.form_id, push_data)
    except Exception as e:
        steps.append({"op": "push", "success": False, "exception": f"{type(e).__name__}: {e}"})
        out["halted_at"] = "push"
        out["recovery_hint"] = "Push 抛异常，未生成目标单。检查源单状态/转换规则/连通性后重试。"
        return _err(e, extra_errors=[{"step": "push", "stage_summary": out}], op="push_and_audit")

    push_status = _result_status(push_result, "push")
    rs = push_result.get("Result", push_result) if isinstance(push_result, dict) else {}
    target_bill_nos = rs.get("Numbers", []) or []
    target_fids_raw = rs.get("Ids", []) or []
    target_fids = [str(x) for x in (target_fids_raw if isinstance(target_fids_raw, list) else [target_fids_raw])]

    step_push: dict[str, Any] = {"op": "push", "success": push_status.get("success", False)}
    if target_bill_nos:
        step_push["target_bill_nos"] = target_bill_nos
        out["target_bill_nos"] = target_bill_nos
    if target_fids:
        step_push["target_fids"] = target_fids
        out["target_fids"] = target_fids
    if not push_status.get("success"):
        step_push["errors"] = push_status.get("errors", [])
        steps.append(step_push)
        out["halted_at"] = "push"
        out["errors"] = push_status.get("errors", [])
        out["recovery_hint"] = (
            "Push 失败：检查 errors[].matched.suggestion；常见原因——关联数量已达上限、"
            "转换规则不匹配、源单未审核。"
        )
        try:
            from scripts.failure_log import FailureLogger
            FailureLogger().log("push_and_audit", out)
        except Exception:
            pass
        return _fmt(out)
    steps.append(step_push)

    # 不需要后续 submit+audit
    if not params.auto_submit_audit:
        out["success"] = True
        out["tip"] = (
            f"已生成 {len(target_bill_nos)} 张目标草稿单。auto_submit_audit=False，"
            "请按需手动 u9_submit_bills + u9_audit_bills。"
        )
        out["next_action"] = "submit+audit"
        return _fmt(out)

    if not target_fids:
        out["halted_at"] = "submit"
        out["recovery_hint"] = "Push 成功但未返回目标 FID，无法自动 Submit。请用 target_bill_nos 反查 FID。"
        out["errors"] = [{"message": "Push response missing Ids"}]
        return _fmt(out)

    # Step 2: Submit（逐条，因用友 API 每次只接受单个 Ids）
    submit_succeeded, submit_failed = [], []
    for fid in target_fids:
        try:
            r = await _post_raw("submit", params.target_form_id, {"Ids": fid})
            s = _result_status(r, "submit")
            if s.get("success"):
                submit_succeeded.append(fid)
            else:
                submit_failed.append({"id": fid, "errors": s.get("errors", [])})
        except Exception as ex:
            submit_failed.append({"id": fid, "error": f"{type(ex).__name__}: {ex}"[:300]})
    step_submit = {"op": "submit", "success": len(submit_failed) == 0,
                   "succeeded": submit_succeeded, "failed": submit_failed}
    if not step_submit["success"]:
        steps.append(step_submit)
        out["halted_at"] = "submit"
        out["errors"] = submit_failed
        out["recovery_hint"] = (
            f"目标草稿已生成 fids={target_fids}。Submit 部分或全部失败：检查 failed[].errors。"
        )
        try:
            from scripts.failure_log import FailureLogger
            FailureLogger().log("push_and_audit", out)
        except Exception:
            pass
        return _fmt(out)
    steps.append(step_submit)

    # Step 3: Audit（逐条）
    audit_ids = submit_succeeded
    audit_succeeded, audit_failed = [], []
    for fid in audit_ids:
        try:
            r = await _post_raw("audit", params.target_form_id, {"Ids": fid})
            s = _result_status(r, "audit")
            if s.get("success"):
                audit_succeeded.append(fid)
            else:
                audit_failed.append({"id": fid, "errors": s.get("errors", [])})
        except Exception as ex:
            audit_failed.append({"id": fid, "error": f"{type(ex).__name__}: {ex}"[:300]})
    step_audit = {"op": "audit", "success": len(audit_failed) == 0,
                  "succeeded": audit_succeeded, "failed": audit_failed}
    if not step_audit["success"]:
        steps.append(step_audit)
        out["halted_at"] = "audit"
        out["errors"] = audit_failed
        out["recovery_hint"] = (
            f"已 Push+Submit 目标单 fids={target_fids}。Audit 部分或全部失败：检查 failed[].errors；"
            f"修正后调用 u9_audit_bills 重试。"
        )
        try:
            from scripts.failure_log import FailureLogger
            FailureLogger().log("push_and_audit", out)
        except Exception:
            pass
        return _fmt(out)
    steps.append(step_audit)

    out["success"] = True
    out["next_action"] = None
    out["tip"] = (
        f"工作流完成：已下推并审核 {len(target_fids)} 张目标单 ({params.target_form_id})。"
    )
    return _fmt(out)


@mcp.tool(
    name="u9_create_lx_billing",
    annotations={"title": "创建二开收/付款单（一站式）", "readOnlyHint": False,
                 "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}
)
async def u9_create_lx_billing(params: CreateLxBillingInput) -> str:
    """二开收款单(TRNV_Receipt)/付款单(TRNV_PaymentSlip) 一站式创建（仅旧版数据模型可用）。

    ⚠️ U9C OpenAPI 没有通用 push，也没有 TRNV_Receipt / TRNV_PaymentSlip 的
    Service 或 DTO。使用标准 U9C 规范时会直接返回明确的“不支持”错误；如账套
    已为该二开单据提供 U9C Service，请改用 u9_save_bill + u9_submit_bills +
    u9_audit_bills 分步完成。以下流程仅保留给旧版环境。

    旧版流程：push → save 补字段 → submit → audit。
    1. push: 源单(SAL_SaleOrder/PUR_PurchaseOrder) → 草稿目标单（保留 _LK 上下游关联）
    2. save: 把 amount / material / qty / so_no 等业务字段写入草稿（is_delete_entry=false 不破坏 _LK）
    3. submit + audit（auto_audit=True 时）

    任一步失败立即停止，返回 halted_at 和 recovery_hint 指引手工接手。

    Returns:
        str: JSON。含 steps、target_bill_no、target_fid、halted_at / recovery_hint。
    """
    is_receipt = params.kind == "receipt"
    target_form_id = "TRNV_Receipt" if is_receipt else "TRNV_PaymentSlip"
    source_form_id = "SAL_SaleOrder" if is_receipt else "PUR_PurchaseOrder"
    op_name = "create_lx_receipt" if is_receipt else "create_lx_payment"

    if not u9c_catalog.has_service(target_form_id):
        return _fmt({
            "op": op_name,
            "success": False,
            "unsupported": True,
            "kind": params.kind,
            "target_form_id": target_form_id,
            "error": (
                f"U9C OpenAPI 未提供 {target_form_id} 的 Service/DTO，"
                "也没有通用 push 接口。"
            ),
            "next_action": (
                "请改用 u9_save_bill 直接创建二开单据（如账套已开放对应 Service），"
                "再调用 u9_submit_bills / u9_audit_bills；或联系 U9 管理员确认该二开"
                "单据的 U9C 接口。"
            ),
        })

    steps: list[dict] = []
    out: dict[str, Any] = {
        "op": op_name, "success": False, "halted_at": None, "steps": steps,
        "kind": params.kind, "source_bill_no": params.source_bill_no,
        "target_form_id": target_form_id,
    }

    # ── Step 1: Push 生成草稿 ──────────────────────────
    push_data: dict[str, Any] = {
        "TargetFormId": target_form_id,
        "Numbers": [params.source_bill_no],
    }
    if params.rule_id:
        push_data["RuleId"] = params.rule_id
    if params.enable_default_rule:
        push_data["IsEnableDefaultRule"] = "true"

    try:
        push_result = await _post_raw("push", source_form_id, push_data)
    except Exception as e:
        steps.append({"op": "push", "success": False, "exception": f"{type(e).__name__}: {e}"})
        out["halted_at"] = "push"
        out["recovery_hint"] = "Push 抛异常，未生成目标单。检查源单状态/连通性后重试。"
        return _err(e, extra_errors=[{"step": "push", "stage_summary": out}], op=op_name)

    push_status = _result_status(push_result, "push")
    rs = push_result.get("Result", push_result) if isinstance(push_result, dict) else {}
    response_status = rs.get("ResponseStatus", {}) if isinstance(rs, dict) else {}
    success_entities = response_status.get("SuccessEntitys", []) or []
    target_fids = [str(x) for x in (rs.get("Ids", []) or [])]
    if not target_fids and success_entities:
        target_fids = [
            str(e.get("Id"))
            for e in success_entities
            if isinstance(e, dict) and e.get("Id") not in (None, "", 0)
        ]
    target_bill_nos = rs.get("Numbers", []) or []
    if not target_bill_nos and success_entities:
        target_bill_nos = [
            e.get("Number")
            for e in success_entities
            if isinstance(e, dict) and e.get("Number")
        ]

    step_push: dict[str, Any] = {"op": "push", "success": push_status.get("success", False)}
    if target_bill_nos:
        step_push["target_bill_nos"] = target_bill_nos
        out["target_bill_no"] = target_bill_nos[0]
    if target_fids:
        step_push["target_fids"] = target_fids
        out["target_fid"] = target_fids[0]

    if not push_status.get("success") or not target_fids:
        step_push["errors"] = push_status.get("errors", [])
        steps.append(step_push)
        out["halted_at"] = "push"
        out["errors"] = push_status.get("errors", [])
        out["recovery_hint"] = (
            "Push 失败：检查源单是否已审核且未关闭；二开单据要求源单为已审核状态。"
        )
        return _fmt(out)
    steps.append(step_push)

    target_fid = target_fids[0]

    # 从 SuccessEntitys 取明细 EntryIds（避免 save 时用友把 _LK 关联当作新行重建）
    entry_ids: list = []
    if success_entities and isinstance(success_entities[0], dict):
        eids_obj = success_entities[0].get("EntryIds", {})
        if isinstance(eids_obj, dict):
            entry_ids = eids_obj.get("FEntity", []) or []

    # ── Step 2: Save 补业务字段 ──────────────────────────
    entry_row: dict[str, Any] = {"F_TRNV_Amount_bh8": params.amount}
    if entry_ids:
        # 关键：保持原分录 EntryID，避免覆盖丢失 _LK 关联
        entry_row["FEntryID"] = entry_ids[0]

    if is_receipt:
        if params.receive_type:
            entry_row["F_TRNV_ReceiveType"] = params.receive_type
        if params.po_no:
            entry_row["F_TRNV_PONo"] = params.po_no
        if params.material_number:
            entry_row["F_TRNV_Material"] = {"FNumber": params.material_number}
        if params.qty:
            entry_row["F_TRNV_Qty2"] = params.qty
    else:
        entry_row["F_TRNV_PushDownType"] = params.push_down_type
        if params.so_no:
            entry_row["F_TRNV_SONo"] = params.so_no
        if params.water_bill_number:
            entry_row["F_TRNV_WaterBillNumber"] = params.water_bill_number
        if params.material_number:
            entry_row["F_TRNV_MaterialId"] = {"FNumber": params.material_number}
        if params.qty:
            entry_row["F_TRNV_Qty"] = params.qty

    if params.original_price:
        entry_row["F_TRNV_OriginalPrice"] = params.original_price
    if params.unit_price:
        entry_row["F_TRNV_UnitPrice"] = params.unit_price

    save_model: dict[str, Any] = {
        "FID": int(target_fid),
        "FEntity": [entry_row],
    }
    if params.business_date:
        save_model["F_TRNV_BusinessDate"] = params.business_date

    try:
        save_result = await _post_raw(
            "save", target_form_id, save_model,
            need_return_fields=["FID", "FBillNo"],
            is_delete_entry=False,  # 关键：保留 push 时建立的 _LK 关联
        )
    except Exception as e:
        steps.append({"op": "save", "success": False, "exception": f"{type(e).__name__}: {e}"})
        out["halted_at"] = "save"
        out["recovery_hint"] = (
            f"Push 已生成草稿 fid={target_fid}, billno={out.get('target_bill_no')}。"
            f"Save 抛异常，手动 view_bill 后用 save_bill 补字段。"
        )
        return _err(e, extra_errors=[{"step": "save", "stage_summary": out}], op=op_name)

    save_status = _result_status(save_result, "save")
    step_save = {"op": "save", "success": save_status.get("success", False)}
    if not save_status.get("success"):
        step_save["errors"] = save_status.get("errors", [])
        steps.append(step_save)
        out["halted_at"] = "save"
        out["errors"] = save_status.get("errors", [])
        out["recovery_hint"] = (
            f"Push 成功但 Save 字段补值失败 fid={target_fid}。"
            f"检查 errors[].suggestion；常见：物料编码不存在、金额格式错误。"
        )
        return _fmt(out)
    steps.append(step_save)

    if not params.auto_audit:
        out["success"] = True
        out["next_action"] = "submit+audit"
        out["tip"] = (
            f"已生成 {target_form_id} 草稿 fid={target_fid} ({out.get('target_bill_no')})，"
            f"业务字段已补值。auto_audit=False，请手动调用 u9_submit_bills + u9_audit_bills。"
        )
        return _fmt(out)

    # ── Step 3: Submit ──────────────────────────
    try:
        submit_result = await _post_raw("submit", target_form_id, {"Ids": [target_fid]})
    except Exception as e:
        steps.append({"op": "submit", "success": False, "exception": f"{type(e).__name__}: {e}"})
        out["halted_at"] = "submit"
        out["recovery_hint"] = (
            f"Push+Save 已成功 fid={target_fid}。Submit 异常，"
            f"手动 u9_submit_bills(form_id=\"{target_form_id}\", bill_ids=[\"{target_fid}\"]) 重试。"
        )
        return _err(e, extra_errors=[{"step": "submit", "stage_summary": out}], op=op_name)

    submit_status = _result_status(submit_result, "submit")
    step_submit = {"op": "submit", "success": submit_status.get("success", False)}
    if not submit_status.get("success"):
        step_submit["errors"] = submit_status.get("errors", [])
        steps.append(step_submit)
        out["halted_at"] = "submit"
        out["errors"] = submit_status.get("errors", [])
        out["recovery_hint"] = (
            f"Submit 失败 fid={target_fid}。检查 errors[].suggestion；"
            f"常见：必填字段缺失、币别未配汇率。"
        )
        return _fmt(out)
    steps.append(step_submit)

    # ── Step 4: Audit ──────────────────────────
    try:
        audit_result = await _post_raw("audit", target_form_id, {"Ids": [target_fid]})
    except Exception as e:
        steps.append({"op": "audit", "success": False, "exception": f"{type(e).__name__}: {e}"})
        out["halted_at"] = "audit"
        out["recovery_hint"] = (
            f"Submit 已成功 fid={target_fid}。Audit 异常，"
            f"手动 u9_audit_bills(form_id=\"{target_form_id}\", bill_ids=[\"{target_fid}\"]) 重试。"
        )
        return _err(e, extra_errors=[{"step": "audit", "stage_summary": out}], op=op_name)

    audit_status = _result_status(audit_result, "audit")
    step_audit = {"op": "audit", "success": audit_status.get("success", False)}
    if not audit_status.get("success"):
        step_audit["errors"] = audit_status.get("errors", [])
        steps.append(step_audit)
        out["halted_at"] = "audit"
        out["errors"] = audit_status.get("errors", [])
        out["recovery_hint"] = (
            f"Audit 失败 fid={target_fid}。常见：金额=0 / 工作流权限不足。"
        )
        return _fmt(out)
    steps.append(step_audit)

    out["success"] = True
    out["next_action"] = None
    closing = (
        f"工作流完成：{target_form_id} {out.get('target_bill_no')} 已审核生效，金额={params.amount}"
    )
    if not is_receipt and params.so_no:
        closing += f"（关联销售订单 F_TRNV_SONo={params.so_no}，毛利闭环已建立）"
    out["tip"] = closing
    return _fmt(out)


@mcp.tool(
    name="u9_batch_save_bills",
    annotations={"title": "批量保存单据", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": False}
)
async def u9_batch_save_bills(params: BatchSaveInput) -> str:
    """批量保存同表单的多张单据（最多 200 张）。

    U9C OpenAPI 没有通用 BatchSave 端点；本工具按每张单据是否带
    ID/FID 分组，分别调用该 Service 的 ``Create`` 与 ``Modify``。

    - 新建：models 中每张单据不传 ID/FID
    - 修改：每张单据必须传 ID（或旧版 FID）
    - 自动纠错：逐张按 U9C 目录修正字段名，结果中用 model_index 标出是哪一张
    - 适合批量导入/批量改价；Create 与 Modify 可能各产生一次 HTTP 请求

    返回：
        - success / response_status / errors
        - count：提交保存的单据数量
        - auto_fixes / unknown_fields：字段名修正与无法识别字段（含 model_index）
    """
    try:
        validator = await _get_metadata_validator(params.form_id)
        prepared: list[dict[str, Any]] = []
        auto_fixes: list[dict] = []
        unknown_fields: list[dict] = []

        for index, raw in enumerate(params.models):
            model = dict(raw)
            if model.get("ID") in (None, "", 0, "0") and model.get("FID") in (None, "", 0, "0"):
                model.setdefault("FID", 0)
            if validator:
                model, fixes, unknown = validator.validate_and_fix(model)
                auto_fixes.extend({**item, "model_index": index} for item in fixes)
                unknown_fields.extend({**item, "model_index": index} for item in unknown)

            # 与 u9_save_bill 相同的防御性排序：非 ENTRY 键（含 FIN/表头）必须排在 ENTRY 前
            keys = list(model.keys())
            entry_keys = [k for k in keys if "ENTRY" in k.upper()]
            non_entry = [k for k in keys if k not in entry_keys]
            if entry_keys and len(non_entry) != len(keys):
                model = {k: model[k] for k in non_entry + entry_keys}
            prepared.append(model)

        result = await _post_raw(
            "batch_save",
            params.form_id,
            prepared,
            need_update_fields=params.need_update_fields,
            need_return_fields=params.need_return_fields,
            is_delete_entry=params.is_delete_entry,
        )

        status_data = _result_status(result, "batch_save")
        status_data["count"] = len(prepared)
        status_data["form_id"] = params.form_id
        if status_data.get("success"):
            status_data["tip"] = (
                f"已批量保存 {len(prepared)} 张 {params.form_id} 单据（草稿），"
                "需逐张或批量提交+审核后才生效"
            )
            if auto_fixes:
                status_data["auto_fixes"] = auto_fixes
            if unknown_fields:
                status_data["unknown_fields"] = unknown_fields
                status_data["tip"] += (
                    f"（另有 {len(unknown_fields)} 个字段无法识别，详见 unknown_fields）"
                )
        else:
            if auto_fixes:
                status_data["auto_fixes"] = auto_fixes
            if unknown_fields:
                status_data["unknown_fields"] = unknown_fields
                status_data["field_hint"] = (
                    "部分字段无法识别（见 unknown_fields），"
                    "请用 u9_get_fields 查该单据的真实字段名后重试"
                )
        return _fmt(status_data)
    except Exception as e:
        return _err(e, op="batch_save")


@mcp.tool(
    name="u9_unvoid_bills",
    annotations={"title": "反作废单据", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": False}
)
async def u9_unvoid_bills(params: ExecuteActionInput) -> str:
    """反作废单据（仅当目标 U9C Service 实际提供该动作时可用）。

    - U9C OpenAPI 没有通用的 UnInvalid 动作，本项目不会凭空构造该编码。
    - 解析优先级：显式 operation > U9C 动作摘要按中文名「反作废/取消作废」匹配。
    - 解析不到时返回明确错误，并提示用 u9_list_form_operations 查看真实 Action。
    - 传参：bill_ids（ID 列表，优先）或 bill_nos（DocNo/Code 列表），至少一个。

    Returns:
        str: JSON，含 success / fid / ids / action / action_source / endpoint 字段
    """
    if params.operation:
        action, source, matched = params.operation, "explicit", ""
    else:
        action, source, matched, available = await _resolve_execute_operation(
            params.form_id, None,
            match_names=["反作废", "取消作废"],
            exclude_names=["终止", "关闭", "冻结"],
        )
        if not action:
            return _fmt({
                "error": True, "op": "unvoid", "success": False,
                "form_id": params.form_id,
                "message": _operation_resolve_error(params.form_id, "反作废", available),
            })
    return await _run_execute_action(params, action, "unvoid", source, matched)


@mcp.tool(
    name="u9_execute_operation",
    annotations={"title": "执行标准动作（通用）", "readOnlyHint": False, "destructiveHint": True,
                 "idempotentHint": False, "openWorldHint": False}
)
async def u9_execute_operation(params: ExecuteOperationInput) -> str:
    """执行任意 U9C Service 动作（通用入口）。

    当某个动作没有专用工具时使用。operation 必须是该 Service 的真实 Action 名。

    使用步骤：
    1. 先调用 ``u9_list_form_operations(form_id=...)`` 查该 Service 支持的 Action；
    2. 再调用本工具并显式传 operation，例如：
       ``form_id='PUR_PurchaseOrder', bill_ids=['100123'], operation='Close'``

    注意 U9C 动作语义可能和直觉相反：PurchaseOrder 的 ``Release`` 是挂起、
    ``Hold`` 是解除挂起；不要按字面猜测。

    ⚠️ 这是低层通用入口：不会替你校验该动作是否适用于当前单据状态。
    专用工具（u9_cancel_bills / u9_void_bills / u9_close_bill /
    u9_unclose_bill / u9_forbid_bills / u9_enable_bills / u9_unvoid_bills）
    会做语义解析与更友好的错误提示。

    Returns:
        str: JSON，含 success / fid / ids / action / endpoint 字段
    """
    return await _run_execute_action(
        params, params.operation, "execute_operation", "explicit"
    )
