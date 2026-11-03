"""表单元数据查询、缓存与字段校验/纠错。"""

import hashlib
import json
import os
import re
from typing import Any, List, Optional

from ..config import settings, u9c_catalog
from ..models.metadata import FieldDef
from ..utils.errors import _zh_field


# 元数据缓存结构版本。U9C 目录生成规则或动作解析变化时递增，
# 避免升级后继续读取旧版本生成的错误缓存。
_CACHE_VERSION = 2


# ─────────────────────────────────────────────
# 元数据缓存（用于自动纠错）
# ─────────────────────────────────────────────
_METADATA_CACHE: dict[str, Optional[dict]] = {}  # form_id -> metadata


class MetadataValidator:
    """
    基于元数据的字段验证和自动修正器。
    元数据来自随包发布的 U9C OpenAPI 规范（离线目录，带缓存）。
    """
    _cache: dict[str, "MetadataValidator"] = {}

    def __init__(self, metadata: dict, form_id: str = ""):
        self.metadata = metadata
        self.form_id = form_id or ""
        self.fields: dict[str, FieldDef] = {}
        self._parse_fields()

    @classmethod
    def get(cls, form_id: str) -> Optional["MetadataValidator"]:
        """获取缓存的验证器"""
        return cls._cache.get(form_id)

    @classmethod
    def set(cls, form_id: str, validator: "MetadataValidator"):
        """设置缓存"""
        cls._cache[form_id] = validator

    @staticmethod
    def _zh_name(name_list: list) -> str:
        """从多语言 Name 数组提取中文名（LocaleId=2052）"""
        if not isinstance(name_list, list):
            return ""
        for item in name_list:
            if isinstance(item, dict) and item.get("Key") == 2052:
                return item.get("Value", "") or ""
        # 退而求其次取第一个
        if name_list and isinstance(name_list[0], dict):
            return name_list[0].get("Value", "") or ""
        return ""

    @staticmethod
    def _field_type_label(f: dict) -> str:
        """根据 LookUpObjectFormId / FieldType 推断字段类型语义"""
        lookup = f.get("LookUpObjectFormId")
        if lookup:
            return f"BaseField->{lookup}"
        # FieldType 是数字编码，无法精确翻译；用 ElementType 辅助
        ft = f.get("FieldType")
        et = f.get("ElementType")
        if ft is None:
            return ""
        return f"FieldType={ft}" + (f",ElementType={et}" if et is not None else "")

    def _parse_fields(self):
        """解析字段定义（适配 U9C 目录生成的统一结构）

        结构：Result.NeedReturnData.Entrys[]
          - FBillHead (ParentKey=None) → 主表字段平铺到顶层
          - 其他 ParentKey=None 的 Entry → 分录/子单头
          - ParentKey != None → 子分录（暂作为父分录的子集忽略）
        """
        nrd = self.metadata.get("Result", {}).get("NeedReturnData")
        if not isinstance(nrd, dict):
            return

        for ent in nrd.get("Entrys", []) or []:
            key = ent.get("Key")
            if not key:
                continue
            if ent.get("ParentKey"):
                # 子分录暂不展开，仅保留父分录信息
                continue

            caption = self._zh_name(ent.get("Name", []))

            if key == "FBillHead":
                # 主表字段：平铺到顶层
                for f in ent.get("Fields", []) or []:
                    fkey = f.get("Key")
                    if not fkey:
                        continue
                    self.fields[fkey] = FieldDef(
                        name=fkey,
                        caption=self._zh_name(f.get("Name", [])),
                        field_type=self._field_type_label(f),
                        field_type_key=str(f.get("FieldType", "")),
                        must_input=bool(f.get("MustInput")),
                        is_entry=False,
                    )
            else:
                # 分录或子单头：作为一个 entry 字段，children 为其内部字段
                children = []
                for f in ent.get("Fields", []) or []:
                    fkey = f.get("Key")
                    if not fkey:
                        continue
                    children.append(FieldDef(
                        name=fkey,
                        caption=self._zh_name(f.get("Name", [])),
                        field_type=self._field_type_label(f),
                        field_type_key=str(f.get("FieldType", "")),
                        must_input=bool(f.get("MustInput")),
                    ))
                self.fields[key] = FieldDef(
                    name=key,
                    caption=caption,
                    is_entry=True,
                    children=children,
                )

    def get_valid_field_names(self) -> List[str]:
        """获取所有有效字段名"""
        names = []
        for name, d in self.fields.items():
            if d.is_entry:
                names.append(name)  # 分录实体名
                for c in d.children:
                    names.append(f"{name}.{c.name}")  # 分录.字段名
            else:
                names.append(name)
        return names

    def get_required_fields(self) -> List[str]:
        """获取必填字段（不含分录内字段）"""
        return [n for n, d in self.fields.items() if d.must_input and not d.is_entry]

    @staticmethod
    def _edit_distance(a: str, b: str) -> int:
        """简单 Levenshtein 编辑距离（小写比较，用于保守模糊匹配）"""
        if a == b:
            return 0
        la, lb = len(a), len(b)
        if la == 0:
            return lb
        if lb == 0:
            return la
        prev = list(range(lb + 1))
        for i in range(1, la + 1):
            cur = [i] + [0] * lb
            for j in range(1, lb + 1):
                cost = 0 if a[i - 1] == b[j - 1] else 1
                cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            prev = cur
        return prev[lb]

    def find_similar_field(self, wrong_name: str, valid_names: Optional[List[str]] = None) -> Optional[str]:
        """
        查找相似字段（智能纠错）。采用保守策略，避免跨语义误改名（如 FCustId→FCustLocId）。

        策略（按优先级）：
          1. 大小写不敏感精确匹配（最优先）——根治大小写不一致导致的静默改名；
          2. 已知显式前缀纠正（仅当纠正后精确命中才采用）；
          3. 保守模糊匹配：长度差≤1 且编辑距离小，且共享≥4 字符公共前缀，
             仅用于纠正明显拼写错（如 FSalesOrgId→FSaleOrgId）。

        valid_names: 当前上下文允许的有效字段名集合（顶层传非分录字段；分录内传该分录子字段）。
        """
        if valid_names is None:
            valid_names = list(self.fields.keys())
        if not valid_names or not wrong_name:
            return None

        # 1. 大小写不敏感精确匹配（FCustId -> FCUSTID 等）
        lower_map = {n.lower(): n for n in valid_names}
        hit = lower_map.get(wrong_name.lower())
        if hit is not None and hit != wrong_name:
            return hit

        # 2. 已知显式前缀纠正（大小写归一后比对，仅精确命中才采用）
        corrections = [
            ("FSales", "FSale"),   # FSalesOrgId -> FSaleOrgId
        ]
        wl = wrong_name.lower()
        for wp, cp in corrections:
            if wp.lower() in wl:
                idx = wl.index(wp.lower())
                candidate = wrong_name[:idx] + cp + wrong_name[idx + len(wp):]
                if candidate in valid_names:
                    return candidate

        # 3. 保守模糊匹配（最后兜底，绝不跨语义）
        best: Optional[str] = None
        best_d = 99
        for valid in valid_names:
            if not valid.startswith("F") or not wrong_name.startswith("F"):
                continue
            if abs(len(valid) - len(wrong_name)) > 1:
                continue
            if valid[:4].lower() != wrong_name[:4].lower():
                continue
            d = self._edit_distance(valid.lower(), wrong_name.lower())
            max_d = 2 if max(len(valid), len(wrong_name)) <= 12 else 3
            if d <= max_d and d < best_d:
                best = valid
                best_d = d
        return best

    def _caption_of(self, field_name: str) -> str:
        """取字段的中文说明（来自元数据 Caption），取不到返回空串。

        支持带路径的写法，让分录内字段也能拿到中文名：
          - 顶层字段：FSaleOrgId
          - FBillHead 下：FBillHead.FDate
          - 分录内字段：FSaleOrderEntry[0].FMaterialId
        """
        if not field_name:
            return ""
        d = self.fields.get(field_name)
        if d is not None:
            return d.caption or ""
        if "." not in field_name:
            return ""
        base, _, child = field_name.partition(".")
        # 分录内字段：Entry[行号].字段
        entry_def = self.fields.get(base.split("[", 1)[0])
        if entry_def is not None and entry_def.is_entry:
            for c in entry_def.children:
                if c.name == child:
                    return c.caption or ""
        # FBillHead.字段 → 顶层字段（FBillHead 的字段在解析时已平铺到顶层）
        d = self.fields.get(child)
        return (d.caption or "") if d is not None else ""

    def validate_and_fix(self, payload: dict) -> tuple[dict, List[dict], List[dict]]:
        """
        验证并修正请求参数

        Returns:
            (修正后的payload, 修正列表, 未知字段列表)
            - 修正列表 [{"from", "to", "from_zh", "to_zh", "location"}]
              from_zh/to_zh 是字段的中文说明（取不到时为空串）
            - 未知字段列表 [{"field", "location", "suggestion"}]
              这些字段既不是有效字段、也没能修正 —— 静默丢弃才是最坑的，
              必须报出来，并给出「用 u9_get_fields 查真实字段名」的建议。
        """
        import copy
        fixed_payload = copy.deepcopy(payload)
        fixes = []
        unknown = []

        # 顶层有效字段候选集（不含分录实体名），用于纠错匹配
        head_fields = [k for k, d in self.fields.items() if not d.is_entry]

        def _record(frm: str, to: str, location: str) -> None:
            fixes.append({
                "from": frm,
                "to": to,
                # from 侧往往是元数据里不存在的错拼名（如 FSalesOrgId），
                # 取不到 Caption 时回退到静态字段词典，至少还能给出中文含义
                "from_zh": self._caption_of(frm) or _zh_field(frm),
                "to_zh": self._caption_of(to) or _zh_field(to),
                "location": location,
            })

        # 1. 修正顶层字段（不含 FBillHead / 已知跳过项 / 有效字段）
        for key in list(fixed_payload.keys()):
            if key in ("FBillHead", "Creator", "CreateDate", "Modifier", "ModifyDate", "FID") or key in self.fields:
                continue
            corrected = self.find_similar_field(key, head_fields)
            if corrected:
                fixed_payload[corrected] = fixed_payload.pop(key)
                _record(key, corrected, "顶层")
            else:
                unknown.append({
                    "field": key,
                    "location": "顶层",
                    "suggestion": (
                        f"「{key}」不是 {self.form_id} 的有效字段，且未能自动匹配。"
                        f"请调用 u9_get_fields 查该单据的真实字段名后重试。"
                    ),
                })

        # 2. 修正 FBillHead 下的字段
        if "FBillHead" in fixed_payload and isinstance(fixed_payload["FBillHead"], dict):
            bill_head = fixed_payload["FBillHead"]
            for key in list(bill_head.keys()):
                if key in self.fields:
                    continue
                corrected = self.find_similar_field(key, head_fields)
                if corrected:
                    bill_head[corrected] = bill_head.pop(key)
                    _record(f"FBillHead.{key}", f"FBillHead.{corrected}", "FBillHead")
                else:
                    unknown.append({
                        "field": f"FBillHead.{key}",
                        "location": "FBillHead",
                        "suggestion": (
                            f"「{key}」不是 {self.form_id} 的有效字段，且未能自动匹配。"
                            f"请调用 u9_get_fields 查该单据的真实字段名后重试。"
                        ),
                    })

        # 3. 修正分录内的字段（候选集限定为该分录子字段，避免误匹配到顶层字段）
        for entry_name, entry_def in self.fields.items():
            if entry_def.is_entry and entry_name in fixed_payload:
                valid_entry_fields = set(c.name for c in entry_def.children)
                if isinstance(fixed_payload[entry_name], list):
                    for idx, entry in enumerate(fixed_payload[entry_name]):
                        if isinstance(entry, dict):
                            for key in list(entry.keys()):
                                if key in valid_entry_fields:
                                    continue
                                corrected = self.find_similar_field(key, list(valid_entry_fields))
                                if corrected:
                                    entry[corrected] = entry.pop(key)
                                    _record(f"{entry_name}[{idx}].{key}", f"{entry_name}[{idx}].{corrected}", entry_name)
                                else:
                                    unknown.append({
                                        "field": f"{entry_name}[{idx}].{key}",
                                        "location": entry_name,
                                        "suggestion": (
                                            f"「{key}」不是 {entry_name} 的有效字段，且未能自动匹配。"
                                            f"请调用 u9_get_fields 查该单据的真实字段名后重试。"
                                        ),
                                    })

        return fixed_payload, fixes, unknown


def _metadata_cache_dir() -> str:
    """元数据磁盘缓存目录（可用 U9_METADATA_CACHE_DIR 覆盖）"""
    d = os.environ.get(
        "U9_METADATA_CACHE_DIR",
        os.path.join(os.path.expanduser("~"), ".workbuddy", "u9_metadata_cache"),
    )
    os.makedirs(d, exist_ok=True)
    return d


def _metadata_cache_path(form_id: str) -> str:
    """按环境(服务地址)+表单 生成缓存文件路径，避免多环境串缓存"""
    base = settings.SERVER_URL or "unknown"
    env_hash = hashlib.md5(base.encode("utf-8")).hexdigest()[:8]
    return os.path.join(_metadata_cache_dir(), f"{env_hash}_{form_id}.json")


_ACTION_ZH = {
    "Create": "新增保存", "NewCreate": "新增保存", "CreateByAutoCode": "新增保存",
    "CreateByAttributes": "按特征新增", "CreateBySrc": "来源单生成",
    "Modify": "修改保存", "Save": "保存", "BatchSave": "批量保存",
    "Delete": "删除", "DelSup": "删除", "Submit": "提交",
    "Approve": "审核", "UnApprove": "反审核", "CancelApprove": "取消审核",
    "Close": "整单关闭", "Open": "打开", "CancelReleaseSO": "取消下达",
    "CancelMo": "取消生产订单",
    "CompleteMo": "完工", "POCreateSO": "采购订单下推销售订单",
}


def _u9c_field_entry(field: dict) -> dict:
    name = field.get("name") or ""
    desc = (field.get("description") or name).replace("\r", " ").replace("\n", " ").strip()
    return {
        "Key": name,
        "Name": [{"Key": 2052, "Value": desc or name}],
        "FieldType": field.get("type") or "",
        "MustInput": bool(field.get("required")),
        "LookUpObjectFormId": field.get("ref") or "",
        "U9CField": True,
    }


def _catalog_metadata(form_id: str) -> Optional[dict]:
    """从打包的 U9C OpenAPI 规范生成元数据（离线，无需 QueryBusinessInfo）。"""
    catalog = u9c_catalog.form_fields(form_id)
    service = catalog.get("service")
    if not service:
        return None

    entries: List[dict] = [{
        "Key": "FBillHead",
        "ParentKey": None,
        "Name": [{"Key": 2052, "Value": "表头"}],
        "Fields": [_u9c_field_entry(f) for f in catalog.get("fields") or [] if f.get("name")],
    }]
    for entry in catalog.get("entries") or []:
        key = entry.get("key") or entry.get("path")
        if not key:
            continue
        caption = entry.get("caption") or key
        entries.append({
            "Key": key,
            "ParentKey": None,
            "Name": [{"Key": 2052, "Value": caption}],
            "Path": entry.get("path"),
            "Fields": [_u9c_field_entry(f) for f in entry.get("fields") or [] if f.get("name")],
        })

    operations = []
    for op in u9c_catalog.form_operations(form_id):
        number = op.get("number") or ""
        summary = op.get("name") or ""
        # 少数 U9C 摘要带有开发批注（如 "解除挂起采购订单 by guojjjuan 20240731"），
        # 去掉尾注后再展示。
        summary = re.sub(r"\s+by\s+\S+.*$", "", summary, flags=re.IGNORECASE).strip()
        # U9C 摘要本身是权威语义（例如 PurchaseOrder.Release=挂起、
        # Hold=解除挂起）；只有摘要不是中文时才回退到本地映射。
        has_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in summary)
        zh = summary if has_cjk else (_ACTION_ZH.get(number) or summary or number)
        operations.append({
            "OperationNumber": number,
            "OperationName": [{"Key": 2052, "Value": zh},
                              {"Key": 1033, "Value": summary or number}],
            "Method": op.get("method"),
            "Path": op.get("path"),
        })

    return {
        "Source": "U9C",
        "CacheVersion": _CACHE_VERSION,
        "FormId": form_id,
        "U9C": {
            "service": service,
            "entity": catalog.get("entity"),
            "dto": catalog.get("dto"),
            "actions": catalog.get("actions") or [],
        },
        "Result": {
            "NeedReturnData": {
                "Entrys": entries,
                "Operations": operations,
            }
        },
    }


async def _query_metadata(form_id: str, force: bool = False) -> Optional[dict]:
    """查询表单元数据（U9C 目录生成；内存 + 磁盘缓存）。

    U9C OpenAPI 没有外部元数据端点。字段目录直接由
    随包发布的 U9C OpenAPI 规范生成；``force=True`` 时重新生成并覆盖磁盘缓存。
    """
    global _METADATA_CACHE

    if not force and form_id in _METADATA_CACHE:
        return _METADATA_CACHE[form_id]

    path = _metadata_cache_path(form_id)
    if not force and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 旧版本缓存来自旧元数据接口，或由旧版 U9C 目录
            # 生成规则产生，字段/动作语义可能已过时，必须重新生成。
            if (
                isinstance(data, dict)
                and data.get("Source") == "U9C"
                and data.get("CacheVersion") == _CACHE_VERSION
            ):
                _METADATA_CACHE[form_id] = data
                return data
        except Exception:
            pass

    data = _catalog_metadata(form_id)
    if data is None:
        return None
    _METADATA_CACHE[form_id] = data
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass
    return data


async def _get_metadata_validator(form_id: str, force: bool = False) -> Optional[MetadataValidator]:
    """获取元数据验证器（带缓存）"""
    # 先检查内存缓存（强制刷新时跳过）
    if not force:
        validator = MetadataValidator.get(form_id)
        if validator:
            return validator

    # 获取元数据
    metadata = await _query_metadata(form_id, force=force)
    if not metadata:
        return None

    # 创建验证器并缓存
    validator = MetadataValidator(metadata, form_id=form_id)
    MetadataValidator.set(form_id, validator)
    return validator
