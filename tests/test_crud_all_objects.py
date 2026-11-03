"""
1076 个业务对象全量 CRUD 请求构造测试（mock 模式，不连真机账套）

数据源：
- docs/apidoc-formid-map-2026-08-07.json
    —— ApiDoc 全部业务对象 FormId 映射（1076 条，全部含 formid，store_isShow=True）
- api-inventory-raw.json（u9-mcp-dev skill references）
    —— 每对象标准操作名（保存/删除/单据查询/查看 等）

能力分类（直接由操作名盘点得出，与 team-lead 结论口径一致）：
- 有保存操作（保存/批量保存/暂存）          -> 726 个，可测 u9_save_bill 请求构造
- 有删除操作（删除/删除对象）               -> 631 个，可测 u9_delete_bills 请求构造
- 仅查询（有 单据查询/查询报表数据/查看）    -> 319 个，pytest.mark.skip 标注"报表/只读无增删改"
- 无标准动作（自定义 API / 仅特殊动作）      -> 14 个，pytest.mark.skip 标注"无标准动作"

验证目标（全部在 mock 层断言【请求构造 + 参数校验】，不断言真机成功）：
1. u9_query_bills  : 1076 个对象，payload 含 FormId（_post("query", payload)）
2. u9_save_bill    : 726 个对象，_post_raw 收到 ("save", form_id, model)，
                          model 合法（含默认 FID=0），返回结构用 fid（非 id）
3. u9_delete_bills : 631 个对象，_post_raw 收到 ("delete", form_id, {"Ids": "..."})，
                          返回结构用 ids（非 id）
4. 仅查询/无标准动作对象：不跑增删改，跳过并标注原因（仅查询对象 query 链路仍由测试1覆盖）

关键坑位（写入断言，防止回归）：
- _result_status 返回的是 fid / ids，不是 id —— save 断言有 fid 无 id，delete 断言有 ids 无 id
- BillIdsInput bill_ids=[] 触发 Pydantic ValidationError（min_length=1）
- ExecuteActionInput 不传 bill_ids/bill_nos 触发中文校验错误"至少提供一个"
- SaveInput 缺 form_id 触发 ValidationError
"""
import json
import os
import sys
import asyncio

import pytest
from pydantic import ValidationError
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from u9_mcp.server import (  # noqa: E402
    u9_query_bills,
    u9_save_bill,
    u9_delete_bills,
    QueryInput,
    SaveInput,
    BillIdsInput,
    ExecuteActionInput,
)

# ─────────────────────────────────────────────
# 数据文件路径
# ─────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORMID_MAP_PATH = os.environ.get(
    "U9_FORMID_MAP_JSON",
    os.path.join(PROJECT_ROOT, "docs", "apidoc-formid-map-2026-08-07.json"),
)
INVENTORY_PATH = os.environ.get(
    "U9_API_INVENTORY_JSON",
    os.path.join(
        PROJECT_ROOT,
        "expert",
        "u9-mcp-dev",
        "skills",
        "u9-mcp-dev",
        "references",
        "api-inventory-raw.json",
    ),
)

# ─────────────────────────────────────────────
# 能力分类
# ─────────────────────────────────────────────
SAVE_OPS = {"保存", "批量保存", "暂存"}
DELETE_OPS = {"删除", "删除对象"}
QUERY_OPS = {"单据查询", "查询报表数据", "查看"}


def _classify(ops):
    """把对象操作名集合归为能力标签。"""
    has_save = bool(SAVE_OPS & set(ops))
    has_del = bool(DELETE_OPS & set(ops))
    has_qry = bool(QUERY_OPS & set(ops))
    if has_save and has_del:
        return "save+delete+query"
    if has_save:
        return "save+query"
    if has_del:
        return "delete+query"
    if has_qry:
        return "readonly"
    return "no_std_action"


def _load_cases():
    """加载 formid-map 并按 apiinfo_id 关联 inventory 操作名，返回对象用例列表。"""
    if not os.path.exists(FORMID_MAP_PATH):
        raise FileNotFoundError(f"formid 映射文件不存在：{FORMID_MAP_PATH}")
    if not os.path.exists(INVENTORY_PATH):
        raise FileNotFoundError(
            f"操作能力盘点文件不存在：{INVENTORY_PATH}\n"
            "可用环境变量 U9_API_INVENTORY_JSON 指定正确路径。"
        )
    with open(FORMID_MAP_PATH, encoding="utf-8") as f:
        formid_map = json.load(f)
    with open(INVENTORY_PATH, encoding="utf-8") as f:
        inventory = json.load(f)

    id2ops = {}
    for dom in inventory.get("domains", []):
        for cat in dom.get("c", []):
            for obj in cat.get("c", []):
                id2ops[obj["id"]] = [o.get("l", "") for o in obj.get("c", [])]

    cases = []
    for item in formid_map:
        formid = item.get("formid", "")
        if not formid:
            continue
        ops = id2ops.get(item.get("apiinfo_id"), [])
        cases.append({
            "formid": formid,
            "name": item.get("name", ""),
            "domain": item.get("domain", ""),
            "module": item.get("module", ""),
            "ops": ops,
            "cap": _classify(ops),
        })
    return cases


CASES = _load_cases()
ALL_CASES = CASES
SAVE_CASES = [c for c in CASES if c["cap"].startswith("save")]
DELETE_CASES = [c for c in CASES if "delete" in c["cap"]]
READONLY_CASES = [c for c in CASES if c["cap"] == "readonly"]
NO_STD_CASES = [c for c in CASES if c["cap"] == "no_std_action"]

# 用于报告/定位：能力 -> 数量
CAP_COUNTS = {}
for c in CASES:
    CAP_COUNTS[c["cap"]] = CAP_COUNTS.get(c["cap"], 0) + 1


def _cap_label(case):
    return f"{case['cap']}:{case['formid']}"


# ─────────────────────────────────────────────
# 1) u9_query_bills —— 全部 1076 个对象
#    验证请求构造：_post("query", payload) 且 payload["FormId"] == form_id
# ─────────────────────────────────────────────
@pytest.mark.parametrize("case", ALL_CASES, ids=_cap_label)
async def test_query_construct(case):
    formid = case["formid"]
    api_result = {"Result": [{"FID": "1", "FBillNo": "B001"}]}
    with patch("u9_mcp.services.client._post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = api_result
        result = await u9_query_bills(QueryInput(form_id=formid))

    parsed = json.loads(result)
    # 返回结构：form_id / count / has_more / data
    assert parsed["form_id"] == formid
    assert parsed["count"] == 1
    assert parsed["data"][0]["FBillNo"] == "B001"

    # 请求构造：query 端点 + payload.FormId 正确
    call_args = mock_post.call_args
    assert call_args[0][0] == "query"
    payload = call_args[0][1]
    assert payload["FormId"] == formid
    assert payload["FieldKeys"], "默认 field_keys 不应为空"


# ─────────────────────────────────────────────
# 2) u9_save_bill —— 726 个有保存操作对象
#    验证请求构造：_post_raw("save", form_id, model)，
#    返回结构用 fid（非 id），避免 submit/audit 取 id 得 None 的坑
# ─────────────────────────────────────────────
@pytest.mark.parametrize("case", SAVE_CASES, ids=_cap_label)
async def test_save_construct(case):
    formid = case["formid"]
    api_result = {
        "Result": {
            "ResponseStatus": {"IsSuccess": True, "Errors": []},
            "Id": 100,
            "Number": "X001",
        }
    }
    with patch(
        "u9_mcp.services.metadata._get_metadata_validator",
        new_callable=AsyncMock,
        return_value=None,
    ) as mock_validator, patch(
        "u9_mcp.services.client._post_raw", new_callable=AsyncMock
    ) as mock_post:
        mock_post.return_value = api_result
        result = await u9_save_bill(
            SaveInput(form_id=formid, model={"FDate": "2026-01-01"})
        )

    parsed = json.loads(result)
    # 返回结构：op=save，success，fid（非 id）
    assert parsed["op"] == "save"
    assert parsed["success"] is True
    assert parsed.get("fid") == 100
    assert "id" not in parsed, "_result_status 返回 fid 而非 id"

    # 请求构造：save 端点 + form_id + model 合法（含默认 FID=0）
    call_args = mock_post.call_args
    assert call_args[0][0] == "save"
    assert call_args[0][1] == formid
    model_sent = call_args[0][2]
    assert model_sent["FDate"] == "2026-01-01"
    assert model_sent["FID"] == 0, "新建单据应默认 FID=0"


# ─────────────────────────────────────────────
# 3) u9_delete_bills —— 631 个有删除操作对象
#    验证请求构造：_post_raw("delete", form_id, {"Ids": "..."})，
#    返回结构用 ids（非 id）
# ─────────────────────────────────────────────
@pytest.mark.parametrize("case", DELETE_CASES, ids=_cap_label)
async def test_delete_construct(case):
    formid = case["formid"]
    api_result = {
        "Result": {"ResponseStatus": {"IsSuccess": True, "Errors": []}, "Ids": ["5"]}
    }
    with patch("u9_mcp.services.client._post_raw", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = api_result
        result = await u9_delete_bills(
            BillIdsInput(form_id=formid, bill_ids=["5"])
        )

    parsed = json.loads(result)
    # 返回结构：op=delete，success，succeeded_ids（非 id；u9_delete_bills 顶层汇总用 succeeded_ids）
    assert parsed["op"] == "delete"
    assert parsed["success"] is True
    assert parsed.get("succeeded_ids") == ["5"]
    assert "id" not in parsed, "delete 汇总返回 succeeded_ids 而非 id"

    # 请求构造：delete 端点 + form_id + Ids 为单个字符串（勿拆单/勿用数组）
    call_args = mock_post.call_args
    assert call_args[0][0] == "delete"
    assert call_args[0][1] == formid
    assert call_args[0][2] == {"Ids": "5"}


# ─────────────────────────────────────────────
# 4) 仅查询对象（319）—— 跳过增删改，标注"报表/只读无增删改"
# ─────────────────────────────────────────────
@pytest.mark.skip(reason="报表/只读对象无增删改操作（仅查询），跳过增删改用例")
@pytest.mark.parametrize("case", READONLY_CASES, ids=_cap_label)
async def test_readonly_skip_rw(case):
    # 永不执行（skip）。仅用于测试报告中体现该对象“为何没有增删改用例”。
    assert False, f"{case['formid']} 不应执行 RW 断言"


# ─────────────────────────────────────────────
# 5) 无标准动作对象（14）—— 跳过增删改，标注"无标准动作"
# ─────────────────────────────────────────────
@pytest.mark.skip(reason="无标准动作（自定义 API / 仅特殊动作），无 CRUD 通用操作")
@pytest.mark.parametrize("case", NO_STD_CASES, ids=_cap_label)
async def test_no_std_action_skip_rw(case):
    # 永不执行（skip）。
    assert False, f"{case['formid']} 不应执行 RW 断言"


# ─────────────────────────────────────────────
# 6) 参数校验链路（独立于对象的模型级校验）
# ─────────────────────────────────────────────
def test_save_input_missing_form_id_rejected():
    """SaveInput 缺 form_id 必须报错（参数校验链路）。"""
    with pytest.raises(ValidationError):
        SaveInput(model={"FDate": "2026-01-01"})


def test_save_input_extra_field_rejected():
    """SaveInput 未知参数必须报错（extra=forbid）。"""
    with pytest.raises(ValidationError):
        SaveInput(form_id="SAL_SaleOrder", model={}, bogus_field=1)


def test_bill_ids_empty_list_rejected():
    """删除/提交/审核/反审核 空 bill_ids 列表必须报错（min_length=1）。"""
    with pytest.raises(ValidationError):
        BillIdsInput(form_id="SAL_SaleOrder", bill_ids=[])


def test_execute_action_input_no_target_rejected_chinese():
    """ExecuteActionInput 不传 bill_ids/bill_nos 报中文校验错误。"""
    with pytest.raises(ValidationError) as ei:
        ExecuteActionInput(form_id="SAL_SaleOrder")
    assert "至少提供一个" in str(ei.value)


def test_execute_action_input_empty_bill_ids_rejected_chinese():
    """ExecuteActionInput bill_ids=[] 同样命中“至少提供一个”。"""
    with pytest.raises(ValidationError) as ei:
        ExecuteActionInput(form_id="SAL_SaleOrder", bill_ids=[])
    assert "至少提供一个" in str(ei.value)


def test_save_returns_fid_not_id_semantics():
    """_result_status 语义锚点：save 结果用 fid/ids，绝无 id 键。

    这是文档/QA 反复踩的坑（submit/audit 取 result['id'] 得 None），
    这里直接锚定该约定，防止未来重构引入 id 键。
    """
    api_result = {
        "Result": {
            "ResponseStatus": {"IsSuccess": True, "Errors": []},
            "Id": 123,
            "Number": "SEM001",
        }
    }
    with patch(
        "u9_mcp.services.metadata._get_metadata_validator",
        new_callable=AsyncMock,
        return_value=None,
    ), patch("u9_mcp.services.client._post_raw", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = api_result
        result = json.loads(
            asyncio.run(
                u9_save_bill(
                    SaveInput(form_id="SAL_SaleOrder", model={"FDate": "2026-01-01"})
                )
            )
        )
    assert "fid" in result and "id" not in result
    assert result["fid"] == 123
