"""U9C 没有成本类 Service 时的明确降级行为。"""

import inspect
import json

from u9_mcp.api import cost
from u9_mcp.models.query import SaveInput


COST_TOOLS = [
    cost.u9_query_material_cost,
    cost.u9_query_material_target_cost,
    cost.u9_query_cost_calculation,
    cost.u9_query_cost_centers,
    cost.u9_query_cost_items,
    cost.u9_query_product_standard_cost,
    cost.u9_query_cost_adjustments,
    cost.u9_save_cost_adjustment,
    cost.u9_query_instant_cost_compare,
    cost.u9_query_cost_trend,
    cost.u9_query_finished_product_cost,
    cost.u9_query_material_cost_usage,
]


async def test_save_cost_adjustment_returns_unsupported():
    out = json.loads(await cost.u9_save_cost_adjustment(
        SaveInput(form_id="STK_CostAdjust", model={})
    ))

    assert out["success"] is False
    assert out["unsupported"] is True
    assert out["form_id"] == "STK_CostAdjust"
    assert "U9C" in out["error"]
    assert "u9_query_table" in out["next_action"]


def test_cost_tools_document_u9c_limitation():
    for fn in COST_TOOLS:
        assert "U9C OpenAPI 未提供成本类" in inspect.getsource(fn), fn.__name__
