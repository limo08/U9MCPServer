"""系统/权限/审批/日志/标准动作相关 DTO。"""

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator



# ─────────────────────────────────────────────
# 标准动作执行工具（U9C Service/{Action}）
# 撤销 / 作废 / 整单关闭 / 反关闭 / 禁用 / 反禁用
# 端点：POST /webapi/{Service}/{Action}，请求体为 OptDocRData[]（ID/Code/OtherID）。
# 动作名以 U9C OpenAPI 为准（如 PurchaseOrder.Release=挂起、Hold=解除挂起）；
# 只能调用 u9_list_form_operations 返回的真实 Action，不要猜测。
# ─────────────────────────────────────────────

class ExecuteActionInput(BaseModel):
    """U9C 标准动作输入（撤销/作废/整单关闭/反关闭/禁用/反禁用等）。

    bill_ids 与 bill_nos 至少提供一个；都传时优先用 bill_ids（ID）。
    """
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    form_id: str = Field(
        ..., description="单据/基础资料 FormId，如 SAL_SaleOrder、PUR_Requisition、BD_Customer"
    )
    bill_ids: Optional[List[str]] = Field(
        default=None, description="单据内码 ID 列表（优先），如 ['100123'] 或 ['100123','100124']"
    )
    bill_nos: Optional[List[str]] = Field(
        default=None, description="单据编号 DocNo/Code 列表，如 ['CGDD000025']（bill_ids 未提供时使用）"
    )
    operation: Optional[str] = Field(
        default=None,
        description="显式 U9C Action 名，如 Release、Hold、Approve、CreateSO。"
                    "不同 Service 的动作不同，请先用 u9_list_form_operations 查询。",
    )

    @model_validator(mode="after")
    def _check_at_least_one_target(self) -> "ExecuteActionInput":
        if not self.bill_ids and not self.bill_nos:
            raise ValueError(
                "bill_ids 与 bill_nos 至少提供一个：请传单据内码 ID 列表（bill_ids）"
                "或单据编号列表（bill_nos）"
            )
        if self.bill_ids is not None and len(self.bill_ids) == 0:
            raise ValueError("bill_ids 不能为空列表")
        if self.bill_nos is not None and len(self.bill_nos) == 0:
            raise ValueError("bill_nos 不能为空列表")
        return self


class ExecuteOperationInput(ExecuteActionInput):
    """通用标准动作：operation 必填，作为 U9C Service 的 Action 名。"""

    operation: str = Field(
        ...,
        description=(
            "U9C Action 名（必填），如 Approve、UnApprove、Release、Hold、"
            "Submit、Delete；不同 Service 支持的动作不同，请先用 "
            "u9_list_form_operations 查询真实 Action"
        ),
    )


class FormOperationListInput(BaseModel):
    """查询指定表单对应的 U9C Service 支持的动作列表。"""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    form_id: str = Field(..., description="表单 FormId，如 PUR_PurchaseOrder、SAL_SaleOrder、BD_Customer")
    refresh_metadata: bool = Field(
        default=False, description="为 true 时先强制刷新该表单的 U9C 目录缓存，再读取操作列表"
    )


# ─────────────────────────────────────────────
# 系统设置工具：用户/角色/权限/编码规则/系统配置查询
# ─────────────────────────────────────────────

class UserQueryInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    filter_string: str = Field(default="", description="过滤条件，如 \"Code='admin'\"")
    field_keys: str = Field(default="ID,Code,Name,DisplayName,Contact,UserGroup,IsAlive,Effective", description="返回字段")
    start_row: int = Field(default=0, ge=0, description="分页起始行")
    limit: int = Field(default=20, ge=1, le=100, description="每页条数")


class RoleQueryInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    filter_string: str = Field(default="", description="过滤条件")
    field_keys: str = Field(default="ID,Code,Name,Description,Effective", description="返回字段（U9C 未开放角色 Service 时会报错）")
    start_row: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class PermissionQueryInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    filter_string: str = Field(default="", description="过滤条件（U9C 未开放独立权限 Service）")
    field_keys: str = Field(default="ID,Code,Name,Description", description="返回字段（U9C 未开放独立权限 Service 时会报错）")
    start_row: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class SequenceQueryInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    filter_string: str = Field(default="", description="过滤条件")
    field_keys: str = Field(default="ID,Code,Name,Description", description="返回字段（U9C 未开放独立编码规则 Service 时会报错）")
    start_row: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class NumberRuleQueryInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    filter_string: str = Field(default="", description="过滤条件（U9C 未开放独立编号规则 Service）")
    field_keys: str = Field(default="ID,Code,Name,Description", description="返回字段（U9C 未开放独立编号规则 Service 时会报错）")
    start_row: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class SystemConfigInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    filter_string: str = Field(default="", description="过滤条件（U9C 未开放独立系统配置 Service）")
    field_keys: str = Field(default="ID,Code,Name,Value,Description", description="返回字段（U9C 未开放独立系统配置 Service 时会报错）")
    start_row: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


# ─────────────────────────────────────────────
# 元数据查询工具
# ─────────────────────────────────────────────

class FormSearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    keyword: str = Field(default="", description="搜索关键词，如'员工'、'采购'、'库存'等，留空返回所有")


class FieldQueryInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    form_id: str = Field(..., description="表单标识，如 BD_Material、PUR_PurchaseOrder")
    entry_key: str = Field(
        default="",
        description="分录 Key（如 POLineDTOList / SOLineDTOList，旧版 F* 别名也可用），传入则只返回该分录字段。默认返回主表字段+所有分录概览",
    )
    verbose: bool = Field(
        default=False,
        description="True 时返回所有主表字段；默认仅返回必填字段+关联基础资料字段（base field），其余压缩为名称列表",
    )


# ─────────────────────────────────────────────
# 审批流工具
# ─────────────────────────────────────────────

class WorkflowQueryInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    form_id: str = Field(default="", description="单据类型，如 ER_ExpenseReimburse（费用报销单），留空查询所有")
    status: str = Field(default="pending", description="状态：pending(待审批)、approved(已通过)、rejected(已驳回)、all(全部)")
    limit: int = Field(default=20, ge=1, le=100, description="返回数量")


class WorkflowActionInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    form_id: str = Field(..., description="单据类型，如 ER_ExpenseReimburse")
    bill_id: str = Field(..., description="单据内码 ID（旧版 FID 也兼容）")
    action: str = Field(..., description="操作：approve(通过)、reject(驳回)")
    opinion: str = Field(default="", description="审批意见")


class WorkflowStatusInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    form_id: str = Field(..., description="单据类型")
    bill_id: str = Field(..., description="单据内码 ID（旧版 FID 也兼容）")


# ─────────────────────────────────────────────
# 审计合规工具（Audit & Compliance）
# ─────────────────────────────────────────────

class AuditLogInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    form_id: str = Field(default="", description="单据类型，如 PUR_PurchaseOrder（留空查询所有）")
    bill_id: str = Field(default="", description="单据内码 ID（旧版 FID 也兼容）")
    bill_no: str = Field(default="", description="单据编号，支持模糊查询")
    user_name: str = Field(default="", description="审核人，支持模糊查询")
    start_date: str = Field(default="", description="开始日期，格式 YYYY-MM-DD")
    end_date: str = Field(default="", description="结束日期，格式 YYYY-MM-DD")
    result: str = Field(default="", description="审核结果：pass(通过)、reject(驳回)、cancel(取消)、all(全部)")
    filter_string: str = Field(default="", description="额外的过滤条件（U9C 字段；旧版 F* 别名会被翻译）")
    order_string: str = Field(default="FCREATEDATE DESC", description="排序条件")
    start_row: int = Field(default=0, ge=0, description="分页起始行")
    limit: int = Field(default=50, ge=1, le=2000, description="每页条数，最大2000")


class ChangeLogInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    form_id: str = Field(default="", description="单据类型，如 PUR_PurchaseOrder")
    bill_id: str = Field(default="", description="单据内码 ID（旧版 FID 也兼容）")
    bill_no: str = Field(default="", description="单据编号，支持模糊查询")
    user_name: str = Field(default="", description="修改人，支持模糊查询")
    start_date: str = Field(default="", description="开始日期，格式 YYYY-MM-DD")
    end_date: str = Field(default="", description="结束日期，格式 YYYY-MM-DD")
    field_name: str = Field(default="", description="字段名称，如 FQty、FPrice 等")
    filter_string: str = Field(default="", description="额外的过滤条件（U9C 字段；旧版 F* 别名会被翻译）")
    order_string: str = Field(default="FCREATEDATE DESC", description="排序条件")
    start_row: int = Field(default=0, ge=0, description="分页起始行")
    limit: int = Field(default=50, ge=1, le=2000, description="每页条数，最大2000")


class ApprovalFlowInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    form_id: str = Field(..., description="单据类型，如 PUR_PurchaseOrder")
    bill_id: str = Field(default="", description="单据内码 ID（旧版 FID 也兼容；留空查询该类型所有单据的审批流）")
    bill_no: str = Field(default="", description="单据编号（与 bill_id 二选一）")
    status: str = Field(default="all", description="审批状态：pending(进行中)、approved(已完成)、rejected(已驳回)、all(全部)")
    start_date: str = Field(default="", description="开始日期，格式 YYYY-MM-DD")
    end_date: str = Field(default="", description="结束日期，格式 YYYY-MM-DD")
    filter_string: str = Field(default="", description="额外的过滤条件（U9C 字段；旧版 F* 别名会被翻译）")
    order_string: str = Field(default="FCREATEDATE DESC", description="排序条件")
    start_row: int = Field(default=0, ge=0, description="分页起始行")
    limit: int = Field(default=50, ge=1, le=2000, description="每页条数，最大2000")


class PermissionChangeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    user_name: str = Field(default="", description="用户名称，支持模糊查询")
    target_type: str = Field(default="", description="授权对象类型：User/Role/Position 等")
    object_type: str = Field(default="", description="被授权对象类型：Form/Bill/Report 等")
    object_name: str = Field(default="", description="被授权对象名称")
    action: str = Field(default="", description="操作类型：Grant/Revoke/Modify 等")
    start_date: str = Field(default="", description="开始日期，格式 YYYY-MM-DD")
    end_date: str = Field(default="", description="结束日期，格式 YYYY-MM-DD")
    filter_string: str = Field(default="", description="额外的过滤条件（U9C 字段；旧版 F* 别名会被翻译）")
    order_string: str = Field(default="FCREATEDATE DESC", description="排序条件")
    start_row: int = Field(default=0, ge=0, description="分页起始行")
    limit: int = Field(default=50, ge=1, le=2000, description="每页条数，最大2000")


class DataBackupInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    backup_type: str = Field(default="", description="备份类型：Full(完整)、Incremental(增量)、Config(配置) 等")
    status: str = Field(default="", description="备份状态：Success/Failed/Restore 等")
    operator: str = Field(default="", description="操作人，支持模糊查询")
    start_date: str = Field(default="", description="开始日期，格式 YYYY-MM-DD")
    end_date: str = Field(default="", description="结束日期，格式 YYYY-MM-DD")
    filter_string: str = Field(default="", description="额外的过滤条件（U9C 字段；旧版 F* 别名会被翻译）")
    order_string: str = Field(default="FCREATEDATE DESC", description="排序条件")
    start_row: int = Field(default=0, ge=0, description="分页起始行")
    limit: int = Field(default=50, ge=1, le=2000, description="每页条数，最大2000")


class OperationLogInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    user_name: str = Field(default="", description="操作用户名，支持模糊查询")
    start_date: str = Field(default="", description="开始日期，格式 YYYY-MM-DD")
    end_date: str = Field(default="", description="结束日期，格式 YYYY-MM-DD")
    operate_type: str = Field(default="", description="操作类型，如 Save/Submit/Audit/Delete/View 等")
    bill_no: str = Field(default="", description="关联单据号，支持模糊查询")
    form_name: str = Field(default="", description="表单名称，如 采购订单、销售订单 等")
    filter_string: str = Field(default="", description="额外的过滤条件（U9C 字段；旧版 F* 别名会被翻译）")
    order_string: str = Field(default="FDATETIME DESC", description="排序条件")
    start_row: int = Field(default=0, ge=0, description="分页起始行")
    limit: int = Field(default=50, ge=1, le=2000, description="每页条数，最大2000")
