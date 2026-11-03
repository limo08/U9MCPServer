"""数据库探查/查询相关 DTO。"""

from typing import Any, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator



# ─────────────────────────────────────────────
# SQL Server 探查工具模型
# ─────────────────────────────────────────────

class SqlSearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    pattern: str = Field(default="", description="搜索关键字（表名/列名），支持模糊匹配，如 'purchase'、'采购订单'、'DocNo'")
    limit: int = Field(default=20, ge=1, le=200, description="最大返回条数")


class SqlDescribeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    table_name: str = Field(..., description="表名（不含 Schema 前缀），如 'PM_PurchaseOrder'（采购订单）、'CBO_ItemMaster'（物料）")


class MetadataCandidateInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    form_id: str = Field(default="", description="用友 form_id，如 'PUR_PurchaseOrder'、'BD_Material'，留空则返回所有候选映射")
    limit: int = Field(default=20, ge=1, le=200, description="最大返回条数")


class SqlFilter(BaseModel):
    """数据库查询的单个过滤条件。"""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    column: str = Field(..., description="字段名（大小写不敏感），如 'DocNo'、'Code'、'Status'")
    operator: Literal[
        "=", "==", "!=", "<>", ">", ">=", "<", "<=",
        "like", "not like", "in", "not in", "between",
        "is null", "is not null",
        "contains", "not contains", "startswith", "endswith",
    ] = Field(
        default="=",
        description=(
            "运算符：= / != / > / >= / < / <= / like / not like / in / not in / "
            "between / is null / is not null；便捷运算符 contains / startswith / endswith"
        ),
    )
    value: Any = Field(
        default=None,
        description=(
            "比较值。in/not in 传数组，between 传两个元素的数组，"
            "is null / is not null 可省略；contains/startswith/endswith 传字符串"
        ),
    )


class SqlTableQueryInput(BaseModel):
    """直接读取 U9 业务表数据（只读）。"""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    table_name: str = Field(
        ...,
        description="U9 真实表名（不含 Schema），如 'PM_PurchaseOrder'、'PM_POLine'、'CBO_ItemMaster'",
    )
    columns: Optional[List[str]] = Field(
        default=None,
        description="要返回的字段列表；省略时返回主键 + 前 40 个业务字段（避免大表返回几百列）",
    )
    filters: List[SqlFilter] = Field(
        default_factory=list,
        description="过滤条件列表，多个条件之间为 AND；列名必须真实存在（防注入）",
    )
    order_by: str = Field(
        default="",
        description="排序，如 'DocNo DESC' 或 'BusinessDate DESC, ID ASC'；省略时按主键/首列排序",
    )
    limit: int = Field(default=100, ge=1, le=1000, description="返回行数（1~1000）")
    offset: int = Field(default=0, ge=0, description="跳过行数，用于分页")
    include_total: bool = Field(default=False, description="是否同时返回满足条件的总行数（多一次 COUNT 查询）")
    all_columns: bool = Field(default=False, description="为 true 时返回全部字段（大表可能响应很大）")

    @model_validator(mode="after")
    def _validate_columns(self):
        if self.columns is not None and not self.columns:
            raise ValueError("columns 为空时请省略该参数；不要传空数组")
        return self


class SqlExecuteInput(BaseModel):
    """执行单条只读 SQL（SELECT/WITH）。"""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    sql: str = Field(
        ...,
        min_length=1,
        description="单条 SELECT 或 WITH 查询；禁止 INSERT/UPDATE/DELETE/DDL/EXEC/多语句",
    )
    params: List[Any] = Field(
        default_factory=list,
        description="按顺序对应 SQL 中 ? 占位符的参数值（强烈建议使用参数化，避免拼接字符串）",
    )
    max_rows: int = Field(default=500, ge=1, le=5000, description="最多返回行数（1~5000），超出会截断")
