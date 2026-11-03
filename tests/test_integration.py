"""
U9 MCP Server 集成测试（真实 API）

依赖环境变量：
  U9_API_SERVER_URL  U9_API_ENT_CODE  U9_API_ORG_CODE  U9_API_USERNAME
  U9_API_CLIENT_ID  U9_API_CLIENT_SECRET（或 U9_API_TOKEN）

运行方式：
  U9_API_SERVER_URL=... U9_API_ENT_CODE=... ... pytest tests/test_integration.py -v
"""

import json
import asyncio
import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from u9_mcp.server import (
    u9_list_forms, u9_get_fields,
    u9_query_bills, u9_view_bill,
    u9_query_purchase_orders, u9_query_sale_orders,
    u9_query_inventory, u9_query_materials,
    u9_query_partners, u9_audit_bills,
    QueryInput, FieldQueryInput, InventoryQueryInput,
    MaterialQueryInput, PartnerQueryInput, BillIdsInput, ViewInput,
    FormSearchInput,
)


# ─── 元数据工具（不需要真实数据） ───────────────────────

class TestMetadataIntegration:
    """元数据工具不修改数据，直接测"""

    @pytest.mark.asyncio
    async def test_list_forms_returns_data(self):
        result = await u9_list_forms(
            FormSearchInput(keyword="采购")
        )
        parsed = json.loads(result)
        assert "count" in parsed
        assert "forms" in parsed
        assert isinstance(parsed["forms"], list)

    @pytest.mark.asyncio
    async def test_get_fields_returns_material_fields(self):
        result = await u9_get_fields(
            FieldQueryInput(form_id="BD_Material")
        )
        parsed = json.loads(result)
        assert parsed["form_id"] == "BD_Material"
        assert "recommended_fields" in parsed


# ─── 查询工具 ───────────────────────────────────────────

class TestQueryIntegration:
    """查询工具只读，测完检查返回结构"""

    @pytest.mark.asyncio
    async def test_query_bills_returns_json_structure(self):
        """查询采购订单，检查返回结构正确"""
        result = await u9_query_bills(
            QueryInput(
                form_id="PUR_PurchaseOrder",
                filter_string="FDocumentStatus='C'",
                limit=5,
            )
        )
        parsed = json.loads(result)
        assert "count" in parsed
        assert "data" in parsed
        assert isinstance(parsed["data"], list)

    @pytest.mark.asyncio
    async def test_query_purchase_orders_returns_valid_structure(self):
        """验证返回结构正确"""
        result = await u9_query_purchase_orders(
            QueryInput(
                form_id="PUR_PurchaseOrder",
                filter_string="FDocumentStatus='Z'",  # 用草稿状态过滤，测试环境可能无数据
                limit=5,
            )
        )
        parsed = json.loads(result)
        assert "count" in parsed
        assert "data" in parsed
        assert isinstance(parsed["data"], list)

    @pytest.mark.asyncio
    async def test_query_inventory_returns_structure(self):
        """查询即时库存"""
        result = await u9_query_inventory(
            InventoryQueryInput(filter_string="FBaseQty>0", limit=5)
        )
        parsed = json.loads(result)
        assert "count" in parsed
        assert "data" in parsed

    @pytest.mark.asyncio
    async def test_query_materials_returns_structure(self):
        """查询物料档案，验证返回结构"""
        result = await u9_query_materials(
            MaterialQueryInput(filter_string="FNumber like 'NOTEXIST%'", limit=5)
        )
        parsed = json.loads(result)
        assert "count" in parsed
        assert "data" in parsed
        assert isinstance(parsed["data"], list)

    @pytest.mark.asyncio
    async def test_query_partners_customer(self):
        """查询客户档案"""
        result = await u9_query_partners(
            PartnerQueryInput(
                partner_type="BD_Customer",
                filter_string="FNumber='NOTEXIST'",
                limit=5,
            )
        )
        parsed = json.loads(result)
        assert parsed["type"] == "BD_Customer"
        assert "count" in parsed

    @pytest.mark.asyncio
    async def test_query_partners_supplier(self):
        """查询供应商档案"""
        result = await u9_query_partners(
            PartnerQueryInput(
                partner_type="BD_Supplier",
                filter_string="FNumber='NOTEXIST'",
                limit=5,
            )
        )
        parsed = json.loads(result)
        assert parsed["type"] == "BD_Supplier"
        assert "count" in parsed


# ─── 写操作工具（只验证不报错，不实际创建数据） ─────────

class TestWriteIntegration:
    """写操作测试：不传入真实 FID，只验证参数校验"""

    @pytest.mark.asyncio
    async def test_audit_with_invalid_id_returns_error(self):
        """用格式正确但不存在的 ID 审核，验证工具能正常处理错误响应"""
        result = await u9_audit_bills(
            BillIdsInput(form_id="PUR_PurchaseOrder", bill_ids=["999999999"])
        )
        parsed = json.loads(result)
        # 新格式：op/success/response_status/error_fields
        assert parsed["op"] == "audit"
        assert parsed["success"] is False
        assert "response_status" in parsed
        assert parsed["response_status"]["IsSuccess"] is False
        # errors 包含业务错误详情
        assert "errors" in parsed
        assert len(parsed["errors"]) > 0

    @pytest.mark.asyncio
    async def test_view_with_invalid_bill_id(self):
        """查看不存在的单据"""
        result = await u9_view_bill(
            ViewInput(form_id="PUR_PurchaseOrder", bill_id="999999999")
        )
        parsed = json.loads(result)
        # view 返回的结构，Result 可能为空或含错误信息
        assert isinstance(parsed, dict)
