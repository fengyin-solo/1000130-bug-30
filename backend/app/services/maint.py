"""维保工单业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "maint"
REQUIRED_FIELDS = ["工单编号", "关联设备", "故障现象"]
# 动作中允许随单回写的业务字段；列表页与详情页展示的就是这些列。
WRITABLE_FIELDS = ["紧急程度", "报修人", "受理班组", "期望完成时间"]
STATUS_ORDER = ["待受理", "处理中", "待验收", "已关闭"]
# 动作 -> (允许执行的前置状态, 目标状态)。状态只能逐段前进，
# 待受理不能直接关闭，已关闭也不能重复关闭。
ACTION_RULES = {
    "受理工单": (["待受理"], "处理中"),
    "派工处理": (["处理中"], "待验收"),
    "关闭工单": (["待验收"], "已关闭"),
}
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
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        self._merge_fields(entry, values)
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"维保工单 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于维保工单可执行范围"
        allowed_statuses, target = ACTION_RULES[action]
        current = str(entry.get("status") or "")
        if current == STATUS_ORDER[-1]:
            return None, "工单已关闭，不能再执行任何状态动作"
        if current not in allowed_statuses:
            return None, f"工单当前为「{current}」状态，不能执行{action}（需先处于{'、'.join(allowed_statuses)}）"
        # 字段回写：只写入本次提交了非空值的字段。派工处理若未重新指派班组，
        # 受理阶段记录的受理班组保持原有归属，不会被空值冲掉。
        self._merge_fields(entry, values or {})
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"维保工单已{action}"

    def _merge_fields(self, entry: dict[str, Any], values: dict[str, Any]) -> None:
        """把动作携带的业务字段合并进工单，空值一律忽略，避免覆盖已有内容。"""
        for field in WRITABLE_FIELDS:
            if field not in values:
                continue
            text = str(values.get(field) or "").strip()
            if text:
                entry[field] = text
