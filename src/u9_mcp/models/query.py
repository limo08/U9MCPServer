"""查询、保存、下推等单据操作 DTO。"""

from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field



# ─────────────────────────────────────────────
# Pydantic 输入模型
# ─────────────────────────────────────────────

class QueryInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    form_id: str = Field(..., description="单据类型标识（或 U9C Service），如 PUR_PurchaseOrder、SAL_SaleOrder、STK_InStock、PurchaseOrder")
    filter_string: str = Field(
        default="",
        description=(
            "过滤条件，如 \"DocStatus=2 and BusinessDate>='2026-01-01'\""
            "（U9C DocStatus：0=开立、1=审核中、2=已审核、3=关闭）。"
            "旧版 F* 别名也会被翻译，如 \"FDocumentStatus='C'\"。"
        ),
    )
    field_keys: str = Field(
        default="FID,FBillNo,FDate,FDocumentStatus",
        description=(
            "返回字段，逗号分隔。默认保留旧版别名（发送前翻译为 U9C 的 "
            "ID/DocNo/BusinessDate/DocStatus，无效字段会自动剔除）；"
            "建议显式传 U9C 字段名，如 \"ID,DocNo,BusinessDate,DocStatus\"。"
        ),
    )
    order_string: str = Field(
        default="FID DESC",
        description="排序条件；默认 FID DESC 会翻译为 U9C 的 ID DESC，也可直接传 \"ID DESC\"",
    )
    start_row: int = Field(default=0, ge=0, description="分页起始行（从0开始）")
    limit: int = Field(default=20, ge=1, le=100, description="每页条数，最大100")


class ViewInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    form_id: str = Field(..., description="单据类型标识（或 U9C Service）")
    bill_id: str = Field(..., description="单据内码 ID（旧版 FID 也兼容）")
    mode: str = Field(
        default="summary",
        description="返回模式: summary(精简,关联字段只保留 ID/Code/Name) | full(完整原始数据)",
    )


class SaveInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    form_id: str = Field(..., description="单据类型，如 PUR_PurchaseOrder / SAL_SaleOrder")
    model: dict = Field(
        ...,
        description=(
            "单据数据包（U9C DTO 字段名）。新建不传 ID/FID，由服务端生成主键；"
            "修改传 ID（旧版 FID 也兼容）。"
        ),
    )
    need_update_fields: List[str] = Field(
        default_factory=list,
        description="仅为兼容旧调用保留；U9C Modify 不接受局部字段列表，当前忽略",
    )
    is_delete_entry: bool = Field(
        default=True,
        description="仅为兼容旧调用保留；U9C 分录增删由 DTO 内容决定，当前忽略",
    )


class BatchSaveInput(BaseModel):
    """批量保存：U9C 没有 BatchSave 端点，按 ID/FID 拆分为 Create/Modify 调用。"""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    form_id: str = Field(..., description="单据类型，如 PUR_PurchaseOrder / SAL_SaleOrder")
    models: List[dict] = Field(
        ..., min_length=1, max_length=200,
        description=(
            "单据数据包数组，每个元素与 u9_save_bill 的 model 相同；"
            "不传 ID/FID 的元素走 Create，传了 ID/FID 的走 Modify"
        ),
    )
    need_update_fields: List[str] = Field(
        default_factory=list,
        description="仅为兼容旧调用保留；U9C Modify 不接受局部字段列表，当前忽略",
    )
    is_delete_entry: bool = Field(
        default=True,
        description="仅为兼容旧调用保留；U9C 分录增删由 DTO 内容决定，当前忽略",
    )
    need_return_fields: List[str] = Field(
        default_factory=lambda: ["FID", "FBillNo"],
        description="需要返回的字段（U9C Save 返回完整结果；该参数仅为兼容旧调用保留）",
    )


class BillIdsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    form_id: str = Field(..., description="单据类型标识")
    bill_ids: List[str] = Field(..., description="单据内码 ID 列表（旧版 FID 也兼容）", min_length=1)


class PurchaseOrderProgressInput(BaseModel):
    """采购订单行明细/执行进度查询的输入模型。"""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    filter_string: str = Field(
        default="DocStatus=2",
        description=(
            "过滤条件，默认只查已审核单据（U9C DocStatus=2）。"
            "旧版写法 \"FDocumentStatus='C'\" 也可用；"
            "如 \"Supplier.Code='S001'\""
        ),
    )
    start_row: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class MaterialQueryInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    filter_string: str = Field(default="", description="过滤条件，U9C 示例：\"Code like 'HG%'\"（旧版 FNumber 也兼容）")
    field_keys: str = Field(
        default="FMaterialId,FNumber,FName,FSpecification,FMaterialGroup.FName",
        description=(
            "返回字段。默认使用旧版别名（发送前翻译）；建议用 u9_get_fields"
            "('BD_Material') 确认该环境的 U9C 字段名，如 Code/Name/SPECS"
        ),
    )
    start_row: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class PartnerQueryInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    partner_type: str = Field(..., description="BD_Customer（客户，U9C Service: Customer）或 BD_Supplier（供应商，Supplier）")
    filter_string: str = Field(default="", description="过滤条件；U9C 示例：\"Code='C001'\"（旧版 FNumber 也兼容）")
    field_keys: str = Field(
        default="FNumber,FName,FShortName,FContact,FPhone,FDocumentStatus",
        description=(
            "返回字段。默认使用旧版别名（发送前翻译，客户/供应商不存在的字段会自动剔除）；"
            "主键统一为 ID，建议用 u9_get_fields 查看真实字段名"
        ),
    )
    start_row: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class InventoryQueryInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    filter_string: str = Field(default="FBaseQty>0", description="过滤条件，默认只取有库存的记录（旧版 F* 别名会翻译）")
    field_keys: str = Field(
        default="FMaterialId.FNumber,FMaterialId.FName,FStockId.FName,FBaseQty,FBaseUnitId.FName",
        description="返回字段；建议用 u9_get_fields 确认 U9C 库存实体的真实字段名"
    )
    start_row: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class ReceiptQueryInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    filter_string: str = Field(
        default="FDocumentStatus='C'",
        description=(
            "过滤条件，默认只查已审核应收单（旧版 FDocumentStatus='C' 会翻译为 U9C DocStatus=2）。"
            "示例："
            "\"AccrueDate>='2026-01-01' and AccrueDate<='2026-01-31'\"（指定月份）、"
            "\"AccrueCustCode='C001'\"（指定客户）"
            "\n⚠️ 应收单在 U9C 对应 Service ``ARBill``，不同账套/二开字段可能不同；"
            "先调用 u9_get_fields('AR_Receivable') 确认可用字段。"
        ),
    )
    field_keys: str = Field(
        default=(
            "FID,FBillNo,FDATE,FDocumentStatus,"
            "FCUSTOMERID.FName,FCUSTOMERID.FNumber,"
            "FALLAMOUNTFOR,FNOTAXAMOUNTFOR,FRELATEHADPAYAMOUNT,"
            "FWRITTENOFFSTATUS,FOPENSTATUS,FENDDATE_H,"
            "FSETTLEORGID.FName,FISINIT"
        ),
        description=(
            "返回字段，逗号分隔。默认使用旧版别名（无效字段会被剔除）；"
            "U9C ARBill 常见字段为 DocNo/AccrueDate/AccrueCustCode/AccrueCustName。"
            "⚠️ 不同账套字段可能不同，先调用 u9_get_fields('AR_Receivable') 确认。"
        ),
    )
    start_row: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class OutsourceOrderQueryInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    filter_string: str = Field(
        default="FDocumentStatus='C' and FStatus not in ('6','7')",
        description=(
            "过滤条件，默认查已审核且未结案/结算的委外订单（旧版别名会翻译）。"
            "示例："
            "\"FSupplierId.FName like '%华力%'\"（指定供应商）、"
            "\"FPlanFinishDate<='2026-08-31'\"（指定截止日前到期）、"
            "\"FStatus='1'\"（状态值以 U9C 实际单据为准）、"
            "\"FMaterialId.FSpecification='APT32F004B'\"（指定产品型号）、"
            "\"FLot.FNumber='AP5E047'\"（指定批次号）"
        ),
    )
    field_keys: str = Field(
        default=(
            "FID,FBillNo,FDate,FDocumentStatus,FStatus,"
            "FSupplierId.FName,FSupplierId.FNumber,"
            "FTreeEntity_FEntryID,"
            "FMaterialId.FNumber,FMaterialId.FName,FMaterialId.FSpecification,"
            "FQty,FStockInQty,FNoStockInQty,"
            "FPlanFinishDate,FUnitId.FName,"
            "FLot.FNumber,FPurOrderNo"
        ),
        description=(
            "返回字段，逗号分隔。默认使用旧版别名（发送前翻译，无效字段会剔除）；"
            "建议先用 u9_get_fields 确认该环境的 U9C 字段名。"
            "注：F_XTR_Qty 为晶圆辅单位片数（自定义字段，如需可追加到 field_keys）"
        ),
    )
    start_row: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class PushDownInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    form_id: str = Field(..., description="源单据类型，如 PUR_PurchaseOrder、SAL_SaleOrder")
    target_form_id: str = Field(..., description="目标单据类型；U9C 目前仅支持 PurchaseOrder → SO")
    source_bill_nos: List[str] = Field(
        ..., description="源单据编号列表（U9C DocNo / 旧版 FBillNo），如 CGDD000025", min_length=1
    )
    rule_id: str = Field(
        default="",
        description="仅为兼容旧调用保留；U9C 的 POCreateSO 不使用转换规则 ID（当前忽略）"
    )
    enable_default_rule: bool = Field(
        default=False,
        description="仅为兼容旧调用保留；U9C 没有转换规则概念（当前忽略）"
    )
    draft_on_fail: bool = Field(
        default=False,
        description="仅为兼容旧调用保留；U9C 下推失败会直接返回错误（当前忽略）"
    )


# ─────────────────────────────────────────────
# 复合工作流工具（高层）：避免 AI 漏掉中间步骤导致的目标漂移
# ─────────────────────────────────────────────

class CreateAndAuditInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    form_id: str = Field(..., description="单据类型，如 SAL_SaleOrder、PUR_PurchaseOrder")
    model: dict = Field(..., description="单据字段（同 u9_save_bill 的 model）")
    need_update_fields: List[str] = Field(default_factory=list, description="修改时需更新的字段名")
    is_delete_entry: bool = Field(default=True, description="保存时是否清空原分录")


class PushAndAuditInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    form_id: str = Field(..., description="源单据类型；U9C 目前仅支持 PUR_PurchaseOrder")
    target_form_id: str = Field(..., description="目标单据类型；目前仅支持 SAL_SaleOrder（POCreateSO）")
    source_bill_nos: List[str] = Field(..., min_length=1, description="源单编号列表（U9C DocNo / 旧版 FBillNo）")
    rule_id: str = Field(default="", description="仅为兼容旧调用保留；U9C POCreateSO 不使用转换规则（当前忽略）")
    enable_default_rule: bool = Field(default=False, description="仅为兼容旧调用保留；U9C 无转换规则概念（当前忽略）")
    draft_on_fail: bool = Field(default=False, description="仅为兼容旧调用保留；U9C 下推失败直接报错（当前忽略）")
    auto_submit_audit: bool = Field(
        default=True,
        description="为 false 时只下推不审核，目标单留为草稿。需要在 push 后做人工校验时关闭。",
    )


# ─────────────────────────────────────────────
# 二开收/付款单一站式工具
# 解决用友 WebAPI push 不携带字段的问题（push+save 补值+submit+audit 一次完成）
# ─────────────────────────────────────────────

class CreateLxBillingInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    kind: Literal["receipt", "payment"] = Field(
        ..., description="receipt=二开收款单(基于销售订单)；payment=二开付款单(基于采购订单)"
    )
    source_bill_no: str = Field(
        ..., description="源单 FBillNo：receipt 填销售订单号(SAL_SaleOrder)，payment 填采购订单号(PUR_PurchaseOrder)"
    )
    amount: float = Field(..., gt=0, description="收/付款金额，写入 F_TRNV_Amount_bh8")
    business_date: str = Field(default="", description="业务日期 YYYY-MM-DD，空则用 push 时的默认值")

    # receipt 专用
    receive_type: str = Field(
        default="1", description="[receipt] 收款类型 F_TRNV_ReceiveType: 1=预收 / 2=尾款"
    )
    po_no: str = Field(default="", description="[receipt] 客户 PO 号 F_TRNV_PONo")

    # payment 专用
    push_down_type: int = Field(
        default=2, ge=1, le=3,
        description="[payment] 下推类型 F_TRNV_PushDownType: 1=按付款计划 / 2,3=按订单分录"
    )
    so_no: str = Field(
        default="",
        description="[payment] 关联销售订单号 F_TRNV_SONo（毛利闭环必填，否则无法对账）"
    )
    water_bill_number: str = Field(
        default="", description="[payment] 银行流水号 F_TRNV_WaterBillNumber"
    )

    # 通用明细字段
    material_number: str = Field(
        default="",
        description="物料编码（FNumber），写入 F_TRNV_Material(receipt) / F_TRNV_MaterialId(payment)"
    )
    qty: float = Field(
        default=0,
        description="数量：receipt 写入 F_TRNV_Qty2，payment 写入 F_TRNV_Qty"
    )
    original_price: float = Field(default=0, description="原价 F_TRNV_OriginalPrice")
    unit_price: float = Field(default=0, description="单价 F_TRNV_UnitPrice")

    # 工作流控制
    auto_audit: bool = Field(
        default=True,
        description="True 一站式做完 submit+audit；False 仅留草稿（导入后人工核对场景）"
    )
    rule_id: str = Field(default="", description="转换规则 ID，空则用默认")
    enable_default_rule: bool = Field(
        default=True, description="启用默认转换规则（生产环境推荐 True）"
    )


# ─────────────────────────────────────────────
# 成本管理工具（存货核算、产品成本、标准成本）
# ─────────────────────────────────────────────

class MaterialCostQueryInput(QueryInput):
    """物料成本库查询输入模型"""
    pass


# ─────────────────────────────────────────────
# 生产管理工具（生产订单/领料单/入库单）
# ─────────────────────────────────────────────

class ProductionOrderBillIdsInput(BillIdsInput):
    """生产订单单据ID输入模型"""
    pass


class ProductionOrderSaveInput(SaveInput):
    """生产订单保存输入模型"""
    pass


class ProductionPickPushInput(BaseModel):
    """生产订单下推领料单输入"""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    bill_nos: List[str] = Field(description="源单生产订单编号列表")
    rule_id: Optional[str] = Field(default=None, description="转换规则ID")
    draft_on_fail: bool = Field(default=True)


class ProductionStockInPushInput(BaseModel):
    """生产领料单下推入库输入"""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    bill_nos: List[str] = Field(description="源单生产领料单编号列表")
    rule_id: Optional[str] = Field(default=None)
    draft_on_fail: bool = Field(default=True)


# ─────────────────────────────────────────────
# 计划管理 + 生产汇报
# ─────────────────────────────────────────────

class MRPResultQueryInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    filter_string: str = Field(default="", description="过滤条件，如 FMaterialId.FNumber='123'")
    top: int = Field(default=200, description="返回条数限制")
    orderby: str = Field(default="FCreateDate DESC", description="排序字段")


class ProductionPlanQueryInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    filter_string: str = Field(default="", description="过滤条件")
    top: int = Field(default=200, description="返回条数限制")
    orderby: str = Field(default="FCreateDate DESC", description="排序字段")


class ProductionReportQueryInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    filter_string: str = Field(default="", description="过滤条件，如 FMaterialId.FNumber='123'")
    top: int = Field(default=200, description="返回条数限制")
    orderby: str = Field(default="FCreateDate DESC", description="排序字段")


# ─────────────────────────────────────────────
# 财务报表查询（U9C Report/GetReportPdfFile，输出 PDF）
# ─────────────────────────────────────────────

class ReportQueryInput(BaseModel):
    """财务报表导出参数：form_id 为报表用例 ID，data 可覆盖报表标识。"""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    form_id: str = Field(
        ...,
        description="报表用例 ID（ReportCaseID）。若 data 中已指定 ReportCaseID 或 "
                    "SubscirbeReportName，可通过 data 覆盖。",
    )
    data: dict = Field(
        default_factory=dict,
        description=(
            '可选请求体。支持 {"ReportCaseID": "..."} 或 '
            '{"SubscirbeReportName": "..."}（U9C 原字段拼写）。'
            "为空时使用 form_id 作为 ReportCaseID。U9C 返回 PDF 的 "
            "FileName + FileContentBase64，不返回结构化行数据。"
        ),
    )
