"""帮派科技与研究系统"""
import time
from dataclasses import dataclass, field

# 研究时间按等级指数递增的基数
DURATION_GROWTH = 2.0


@dataclass
class Tech:
    tid: str
    name: str
    tier: int
    prereq: list = field(default_factory=list)
    cost: dict = field(default_factory=dict)
    duration: float = 3600
    effect: dict = field(default_factory=dict)
    researching: bool = False
    complete: bool = False
    start_time: float = 0

    def __post_init__(self):
        # bug7: 研究时间按等级指数递增
        self.duration = self.duration * (DURATION_GROWTH ** (self.tier - 1))


class GuildResearch:
    def __init__(self):
        self.techs: dict[str, Tech] = {}
        self.resources: dict[str, int] = {}
        self.research_queue: list[str] = []
        self.max_queue = 1  # bug2: 队列上限可配置
        self.archive: dict = {}  # bug8: 解散归档
        self.notifications: list = []
        self.refund_rate = 0.5  # bug6: 重置按比例返还
        self.reset_requires_confirm = False  # bug6: 可开启确认

    def _prereqs_complete(self, tid: str, seen: set | None = None) -> bool:
        """bug1: 递归检查前置依赖是否全部完成"""
        if seen is None:
            seen = set()
        if tid in seen:  # 防循环依赖
            return False
        seen.add(tid)
        tech = self.techs.get(tid)
        if tech is None:
            return False
        for pre in tech.prereq:
            pre_tech = self.techs.get(pre)
            if pre_tech is None or not pre_tech.complete:
                return False
            if not self._prereqs_complete(pre, seen):
                return False
        return True

    def can_research(self, tid: str) -> bool:
        tech = self.techs.get(tid)
        if tech is None:
            return False
        if tech.complete or tech.researching:
            return False
        return self._prereqs_complete(tid)

    def start_research(self, tid: str) -> tuple[bool, str]:
        if not self.can_research(tid):
            return False, "cannot"
        if len(self.research_queue) >= self.max_queue:
            return False, "queue full"
        tech = self.techs[tid]
        # bug3: 原子扣除资源，任一步失败全额返还
        deducted = {}
        try:
            for res, amt in tech.cost.items():
                if self.resources.get(res, 0) < amt:
                    raise ValueError("no resources")
                self.resources[res] -= amt
                deducted[res] = amt
        except Exception:
            for res, amt in deducted.items():
                self.resources[res] = self.resources.get(res, 0) + amt
            return False, "no resources"
        tech.researching = True
        tech.start_time = time.time()
        self.research_queue.append(tid)
        return True, "started"

    def get_duration(self, tid: str) -> float:
        """bug7: 返回该科技实际研究时长（按等级指数递增）"""
        tech = self.techs.get(tid)
        if tech is None:
            return 0
        return tech.duration

    def get_effect(self, tid: str) -> dict:
        # bug4: 只有研究完成的科技才生效
        tech = self.techs.get(tid)
        if tech is None or not tech.complete:
            return {}
        return tech.effect

    def complete_research(self, tid: str):
        tech = self.techs[tid]
        tech.complete = True
        tech.researching = False
        if tid in self.research_queue:
            self.research_queue.remove(tid)
        # bug5: 完成时触发事件通知所有在线成员
        self.notifications.append({
            "event": "research_complete",
            "tid": tid,
            "name": tech.name,
            "time": time.time(),
        })

    def reset_tech(self, tid: str, confirm: bool = True) -> bool:
        # bug6: 重置按比例返还资源，可要求确认
        if self.reset_requires_confirm and not confirm:
            return False
        tech = self.techs.get(tid)
        if tech is None:
            return False
        if tid in self.research_queue:
            self.research_queue.remove(tid)
        tech.complete = False
        tech.researching = False
        for res, amt in tech.cost.items():
            refund = int(amt * self.refund_rate)
            if refund > 0:
                self.resources[res] = self.resources.get(res, 0) + refund
        return True

    def archive_guild(self, guild_id: str):
        """bug8: 解散时归档科技数据，可查询可恢复"""
        self.archive[guild_id] = {
            "techs": {
                tid: {
                    "tid": t.tid,
                    "name": t.name,
                    "tier": t.tier,
                    "prereq": list(t.prereq),
                    "cost": dict(t.cost),
                    "duration": t.duration,
                    "effect": dict(t.effect),
                    "researching": t.researching,
                    "complete": t.complete,
                    "start_time": t.start_time,
                }
                for tid, t in self.techs.items()
            },
            "archived_at": time.time(),
        }

    def restore_guild(self, guild_id: str) -> bool:
        """bug8: 从归档恢复科技数据"""
        entry = self.archive.get(guild_id)
        if entry is None:
            return False
        for tid, data in entry["techs"].items():
            tech = Tech(
                data["tid"], data["name"], data["tier"],
                prereq=list(data["prereq"]),
                cost=dict(data["cost"]),
                effect=dict(data["effect"]),
            )
            tech.duration = data["duration"]
            tech.researching = data["researching"]
            tech.complete = data["complete"]
            tech.start_time = data["start_time"]
            self.techs[tid] = tech
            if tech.researching and tid not in self.research_queue:
                self.research_queue.append(tid)
        return True
