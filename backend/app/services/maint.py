"""维保工单业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "maint"
REQUIRED_FIELDS = ["工单编号", "关联设备", "故障现象"]
# 可随登记/受理/派工/编辑回写的业务字段；工单编号建单后不改，状态只能靠动作流转
EDITABLE_FIELDS = ["关联设备", "故障现象", "紧急程度", "报修人", "受理班组", "期望完成时间"]
ALL_FIELDS = REQUIRED_FIELDS + [
    field for field in EDITABLE_FIELDS if field not in REQUIRED_FIELDS
]
STATUS_ORDER = ["待受理", "处理中", "待验收", "已关闭"]
# 每个动作允许在哪些状态下执行，避免跳步流转和已关闭工单重复操作
ACTION_RULES: dict[str, dict[str, Any]] = {
    "受理工单": {"target": "处理中", "from": {"待受理"}},
    "派工处理": {"target": "待验收", "from": {"处理中"}},
    # 处理中可以直接关闭（验收合格当场关），待验收是正常关闭入口
    "关闭工单": {"target": "已关闭", "from": {"处理中", "待验收"}},
}
# 派工处理只补充维修安排，受理班组归属必须沿用受理时的结果，不允许被覆盖
ACTION_FIELD_GUARDS: dict[str, set[str]] = {"派工处理": {"受理班组"}}
NEGATIVE_ACTIONS = []


class MaintService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("工单编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        # 把选填字段一并落库，避免详情页再次打开时期望完成时间等信息丢失
        for field in ALL_FIELDS:
            value = values.get(field)
            if value is not None and str(value).strip():
                entry[field] = value
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def update_entry(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"维保工单 {entry_id} 不存在或已归档"
        if entry.get("status") == STATUS_ORDER[-1]:
            return None, "工单已关闭，不能再修改字段"
        self._merge_fields(entry, values, guarded=set())
        return entry, "维保工单字段已更新"

    def run_action(
        self, entry_id: int, action: str, values: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"维保工单 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于维保工单可执行范围"

        rule = ACTION_RULES[action]
        current = entry.get("status")
        target = rule["target"]
        if current not in rule["from"]:
            if current == STATUS_ORDER[-1]:
                return None, "工单已关闭，不能重复执行动作"
            return None, f"工单当前为「{current}」状态，不能执行「{action}」"
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"

        # 回写动作携带的业务字段；受保护字段（如派工时的受理班组）保留原有归属
        self._merge_fields(entry, values or {}, guarded=ACTION_FIELD_GUARDS.get(action, set()))
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"维保工单已{action}"

    @staticmethod
    def _merge_fields(entry: dict[str, Any], values: dict[str, Any], *, guarded: set[str]) -> None:
        """把提交的业务字段合并进工单；空值视为不修改，受保护字段保持原值。"""
        for field in EDITABLE_FIELDS:
            if field in guarded:
                continue
            if field not in values:
                continue
            value = values.get(field)
            if value is None or not str(value).strip():
                continue
            entry[field] = value
