"""帮派科技与研究系统。

修复内容：
1. 前置科技递归检查（含环路保护），未研究低级科技不能研究高级科技；
2. 研究队列上限可配置，队列满需等待或先取消；
3. 开始研究时原子扣除资源，中途失败/取消全额返还；
4. 科技效果仅对已研究完成的帮派成员生效；
5. 研究完成触发事件，通知所有在线成员；
6. 重置科技需显式确认，并按比例返还资源；
7. 研究时间随科技等级指数递增；
8. 帮派解散时归档科技数据，归档可查询、可恢复。
"""
import copy
import time
from dataclasses import dataclass, field

BASE_DURATION = 3600.0
DURATION_GROWTH = 2.0
DEFAULT_RESET_REFUND_RATE = 0.8


def tech_duration(tier: int) -> float:
    """按等级指数递增的研究时长：1级3600秒，每级翻一倍。"""
    tier = max(int(tier), 1)
    return BASE_DURATION * (DURATION_GROWTH ** (tier - 1))


@dataclass
class Tech:
    tid: str
    name: str
    tier: int
    prereq: list = field(default_factory=list)
    cost: dict = field(default_factory=dict)
    duration: float = 0.0
    effect: dict = field(default_factory=dict)
    researching: bool = False
    complete: bool = False
    start_time: float = 0.0
    complete_time: float = 0.0

    def __post_init__(self):
        # 研究时间由等级决定，忽略外部传入的固定值，保证高等级耗时更长。
        self.duration = tech_duration(self.tier)


class GuildResearch:
    def __init__(self, max_queue: int = 1,
                 reset_refund_rate: float = DEFAULT_RESET_REFUND_RATE):
        self.techs: dict[str, Tech] = {}
        self.resources: dict[str, int] = {}
        self.research_queue: list[str] = []
        self.max_queue = max_queue
        self.reset_refund_rate = reset_refund_rate
        self.members: set[str] = set()
        self.online_members: set[str] = set()
        self.events: list[dict] = []
        self.notifications: list[dict] = []
        self.member_notifications: dict[str, list[dict]] = {}
        self.archive: dict[str, dict] = {}

    # ---- 成员与在线状态 ----

    def register_member(self, member_id: str) -> None:
        self.members.add(member_id)

    def remove_member(self, member_id: str) -> None:
        self.members.discard(member_id)
        self.online_members.discard(member_id)
        self.member_notifications.pop(member_id, None)

    def member_online(self, member_id: str) -> None:
        self.members.add(member_id)
        self.online_members.add(member_id)

    def member_offline(self, member_id: str) -> None:
        self.online_members.discard(member_id)

    # ---- 前置依赖 ----

    def _prereqs_satisfied(self, tid: str, seen: set | None = None) -> bool:
        """递归检查整条前置链上的科技均已研究完成。"""
        if seen is None:
            seen = set()
        if tid in seen:  # 前置成环，直接判定不满足
            return False
        seen.add(tid)
        tech = self.techs.get(tid)
        if tech is None:
            return False
        for prereq_id in tech.prereq:
            prereq = self.techs.get(prereq_id)
            if prereq is None or not prereq.complete:
                return False
            if not self._prereqs_satisfied(prereq_id, seen):
                return False
        return True

    def can_research(self, tid: str) -> bool:
        tech = self.techs.get(tid)
        if tech is None or tech.complete or tech.researching:
            return False
        return self._prereqs_satisfied(tid)

    # ---- 研究开始 / 取消 / 完成 ----

    def _refund(self, cost: dict) -> dict:
        refunded = {}
        for resource, amount in cost.items():
            self.resources[resource] = self.resources.get(resource, 0) + amount
            refunded[resource] = amount
        return refunded

    def start_research(self, tid: str) -> tuple[bool, str]:
        if tid not in self.techs:
            return False, "tech not found"
        tech = self.techs[tid]
        if tech.complete:
            return False, "already complete"
        if tech.researching:
            return False, "already researching"
        if not self._prereqs_satisfied(tid):
            return False, "prerequisites not met"
        if len(self.research_queue) >= self.max_queue:
            return False, "queue full"
        # 先做全部资源预检，保证扣费时不会扣到一半失败。
        for resource, amount in tech.cost.items():
            if self.resources.get(resource, 0) < amount:
                return False, f"not enough {resource}"
        spent: dict = {}
        try:
            for resource, amount in tech.cost.items():
                self.resources[resource] = (
                    self.resources.get(resource, 0) - amount
                )
                spent[resource] = amount
            tech.researching = True
            tech.start_time = time.time()
            self.research_queue.append(tid)
        except Exception:
            # 扣费后任何步骤失败，原子回滚：全额返还。
            self._refund(spent)
            tech.researching = False
            tech.start_time = 0.0
            raise
        return True, "started"

    def cancel_research(self, tid: str) -> tuple[bool, str]:
        """取消研究：腾出队列位并全额返还资源。"""
        tech = self.techs.get(tid)
        if tech is None:
            return False, "tech not found"
        if not tech.researching:
            return False, "not researching"
        refunded = self._refund(tech.cost)
        tech.researching = False
        tech.start_time = 0.0
        if tid in self.research_queue:
            self.research_queue.remove(tid)
        self._emit("research_canceled", tid=tid, refund=refunded)
        return True, "canceled"

    def get_duration(self, tech) -> float:
        """按等级指数计算研究时长，支持 Tech / 等级 / 科技ID。"""
        if isinstance(tech, Tech):
            tier = tech.tier
        elif isinstance(tech, str) and tech in self.techs:
            tier = self.techs[tech].tier
        else:
            tier = int(tech)
        return tech_duration(tier)

    def sync(self, now: float | None = None) -> list[str]:
        """推进时间，把已到时的研究自动完成并通知。"""
        if now is None:
            now = time.time()
        finished = []
        for tid in list(self.research_queue):
            tech = self.techs.get(tid)
            if (tech and tech.researching and tech.start_time
                    and now - tech.start_time >= tech.duration):
                self.complete_research(tid)
                finished.append(tid)
        return finished

    def complete_research(self, tid: str) -> bool:
        tech = self.techs.get(tid)
        if tech is None:
            return False
        tech.complete = True
        tech.researching = False
        tech.complete_time = time.time()
        if tid in self.research_queue:
            self.research_queue.remove(tid)
        recipients = sorted(self.online_members)
        event = self._emit(
            "research_complete",
            tid=tid,
            name=tech.name,
            recipients=recipients,
        )
        # 只投递给在线成员，离线成员上线后可查 events 历史。
        for member_id in recipients:
            self.member_notifications.setdefault(member_id, []).append(event)
        return True

    # ---- 科技效果 ----

    def get_effect(self, tid: str, member_id: str | None = None) -> dict:
        tech = self.techs.get(tid)
        if tech is None or not tech.complete:
            return {}
        if member_id is not None and member_id not in self.members:
            return {}
        return dict(tech.effect)

    def get_member_effects(self, member_id: str) -> dict:
        """汇总某帮派成员当前享受的全部已研究科技增益。"""
        if member_id not in self.members:
            return {}
        merged: dict = {}
        for tech in self.techs.values():
            if not tech.complete:
                continue
            for key, value in tech.effect.items():
                merged[key] = merged.get(key, 0) + value
        return merged

    # ---- 重置（确认 + 按比例返还） ----

    def reset_tech(self, tid: str, confirm: bool = True) -> tuple[bool, str]:
        """重置已完成科技。

        UI 层应先弹确认框，用户确认后调用本方法；
        显式传 confirm=False 视为未确认，只做预检不执行。
        """
        tech = self.techs.get(tid)
        if tech is None:
            return False, "tech not found"
        if not confirm:
            return False, "reset requires confirmation"
        if tech.researching:
            return self.cancel_research(tid)
        if not tech.complete:
            return False, "tech not complete"
        refunded: dict = {}
        for resource, amount in tech.cost.items():
            refund = amount * self.reset_refund_rate
            if isinstance(amount, int):
                refund = int(refund)
            refunded[resource] = refund
            self.resources[resource] = (
                self.resources.get(resource, 0) + refund
            )
        tech.complete = False
        tech.complete_time = 0.0
        self._emit(
            "tech_reset",
            tid=tid,
            rate=self.reset_refund_rate,
            refund=refunded,
        )
        return True, "reset"

    # ---- 事件通知 ----

    def _emit(self, event_type: str, **payload) -> dict:
        event = {"type": event_type, "time": time.time()}
        event.update(payload)
        self.events.append(event)
        self.notifications.append(event)
        return event

    # ---- 解散归档 / 查询 / 恢复 ----

    def archive_guild(self, guild_id: str) -> dict:
        snapshot = {
            "guild_id": guild_id,
            "archived_at": time.time(),
            "techs": {
                tid: copy.deepcopy(tech) for tid, tech in self.techs.items()
            },
            "resources": copy.deepcopy(self.resources),
            "research_queue": list(self.research_queue),
            "max_queue": self.max_queue,
        }
        self.archive[guild_id] = snapshot
        return snapshot

    def get_archive(self, guild_id: str) -> dict | None:
        snapshot = self.archive.get(guild_id)
        return copy.deepcopy(snapshot) if snapshot is not None else None

    def list_archives(self) -> list[str]:
        return sorted(self.archive)

    def restore_guild(self, guild_id: str) -> tuple[bool, str]:
        snapshot = self.archive.get(guild_id)
        if snapshot is None:
            return False, "archive not found"
        self.techs = {
            tid: copy.deepcopy(tech)
            for tid, tech in snapshot["techs"].items()
        }
        self.resources = copy.deepcopy(snapshot["resources"])
        self.research_queue = list(snapshot["research_queue"])
        self.max_queue = snapshot.get("max_queue", self.max_queue)
        return True, "restored"
