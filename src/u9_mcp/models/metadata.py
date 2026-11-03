"""表单元数据字段定义 DTO。"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class FieldDef:
    """字段定义"""

    name: str
    caption: str = ""
    field_type: str = ""
    field_type_key: str = ""
    must_input: bool = False
    is_entry: bool = False
    children: List["FieldDef"] = field(default_factory=list)
