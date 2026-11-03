"""api.prompts"""

import json
from mcp.server.mcpserver.prompts.base import UserMessage

from . import mcp
from ..config.form_catalog import FORM_CATALOG



# ─────────────────────────────────────────────
# Prompts（内置提示词模板）
# ─────────────────────────────────────────────

@mcp.prompt(name="查询采购订单")
def prompt_query_purchase_orders() -> list[UserMessage]:
    """查询已审核采购订单的提示词模板"""
    return [
        UserMessage(
            content="请帮我查询最近20条已审核的采购订单，"
                    "包含单据号、日期、供应商名称和金额，按日期倒序排列。"
        )
    ]


@mcp.prompt(name="查询即时库存")
def prompt_query_inventory() -> list[UserMessage]:
    """查询当前库存的提示词模板"""
    return [
        UserMessage(
            content="请查询当前所有有库存（数量大于0）的物料，"
                    "列出物料编码、名称、仓库和数量。"
        )
    ]


@mcp.prompt(name="新建采购订单")
def prompt_create_purchase_order() -> list[UserMessage]:
    """新建采购订单的提示词模板"""
    return [
        UserMessage(
            content="请帮我新建一张采购订单。需要提供以下信息：\n"
                    "1. 供应商编码（如 S001）\n"
                    "2. 物料编码（如 MAT001）\n"
                    "3. 数量\n"
                    "4. 单价\n"
                    "5. 采购部门编码（如 D001）\n"
                    "请告诉我以上信息，我来帮你创建。"
        )
    ]


# ─────────────────────────────────────────────
# Resources（上下文资源）
# ─────────────────────────────────────────────

@mcp.resource("u9://forms", mime_type="application/json")
def resource_form_catalog() -> str:
    """用友常用表单目录，包含 form_id、中文名称、描述和推荐查询字段"""
    return json.dumps(
        [{
            "form_id": k,
            "name": v["name"],
            "alias": v["alias"],
            "desc": v.get("desc", ""),
            "recommended_fields": v["fields"],
            "db_tables": v.get("db_tables", ()),
            "has_business_rules": bool(v.get("business_rules")),
        } for k, v in FORM_CATALOG.items()],
        ensure_ascii=False, indent=2
    )


@mcp.resource("u9://help", mime_type="text/plain; charset=utf-8")
def resource_help() -> str:
    """用友 MCP Server 使用指南"""
    return """用友 MCP Server 使用指南
====================

## 供应链（SCM）查询
- u9_query_purchase_orders          查询采购订单列表（默认含关联数量/累计入库）
- u9_query_purchase_order_progress 查询采购订单执行进度（表体分录级）
- u9_query_purchase_requisitions    查询采购申请单
- u9_query_purchase_inquiry         查询采购询价单（RFQ）
- u9_query_supplier_quotes          查询供应商报价单
- u9_query_sale_orders              查询销售订单
- u9_query_sale_quotations          查询销售报价单
- u9_query_stock_bills              查询出入库单
- u9_query_stock_transfer_apply     查询调拨申请单
- u9_query_inventory                查询即时库存
- u9_query_quality_inspections     查询来料检验单（IQC）

## 基础资料查询
- u9_query_materials    查询物料档案
- u9_query_partners     查询客户/供应商

## 通用查询
- u9_query_bills        通用单据查询（任意 form_id）

## 写操作（会修改 ERP 数据）
- u9_save_bill      新建或修改单据
- u9_submit_bills   提交单据
- u9_audit_bills    审核单据
- u9_unaudit_bills  反审核单据
- u9_delete_bills   删除单据
- u9_push_bill      下推单据（采购订单→收料通知单/入库单；销售订单→出库单）

## 采购订单核心业务规则
- 关联数量 = 累计收料数量 + 累计入库数量
- 关联数量 >= 订单数量 → 无法下推收料单/入库单
- 勾选控制交货数量 → 关联数量 >= 交货下限无法下推，超交货上限无法保存
- 累计入库数量 >= 交货下限 → 该行自动业务关闭
- 冻结/终止的分录行不允许编辑和关联操作
- 采购订单被付款单关联后，不可反审核

## 销售订单核心业务规则
- 累计出库数量 >= 订单数量 → 该行自动业务关闭
- 冻结/终止的分录行不允许编辑和关联操作

## 采购入库单核心业务规则
- 入库单审核时累加采购订单【累计入库数量】；反审核时扣减
- 勾选控制交货数量时，入库数量不能超过采购订单【交货上限】

## 来料检验核心业务规则
- 物料勾选来料检验时，必须先收料检验合格后再入库
- 合格物料下推入库单至合格品仓库；不合格物料走特采或退货流程

## 单据状态枚举
- A=创建 B=审核中 C=已审核 D=重新审核 Z=暂存
- 业务状态 A=正常 B=业务关闭/冻结/终止

## 元数据
- u9_list_forms   搜索可用表单（不知道 form_id 时先用这个）
- u9_get_fields  获取表单字段列表及业务规则

## SQL 数据库探查
- u9_discover_tables            搜索表名
- u9_discover_columns            搜索列名
- u9_describe_table              查看表结构
- u9_discover_metadata_candidates 查看 form_id 对应的数据库表

## 常用 filter_string 示例
- 已审核: FDocumentStatus='C'
- 指定日期: FDate>='2024-01-01' and FDate<='2024-12-31'
- 模糊搜索: FName like '%关键词%'
- 未关闭: FCloseStatus='A'
- 业务正常: FBusinessClose='A'

## 成本管理（需启用成本模块）
- u9_query_material_cost              查询物料成本库
- u9_query_cost_calculation         查询成本计算单
- u9_query_cost_centers             查询成本中心
- u9_query_cost_items              查询成本项目
- u9_query_product_standard_cost    查询产品标准成本
"""
