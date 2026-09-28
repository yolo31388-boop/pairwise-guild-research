"""帮派科技与研究系统 - 含8个bug"""
import time
from dataclasses import dataclass, field

@dataclass
class Tech:
    tid: str
    name: str
    tier: int
    prereq: list = field(default_factory=list)
    cost: dict = field(default_factory=dict)
    duration: float = 3600  # bug7: 固定时间
    effect: dict = field(default_factory=dict)
    researching: bool = False
    complete: bool = False
    start_time: float = 0

class GuildResearch:
    def __init__(self):
        self.techs: dict[str, Tech] = {}
        self.resources: dict[str, int] = {}
        self.research_queue: list[str] = []
        self.max_queue = 1  # bug2: 队列上限
        self.archive: dict = {}  # bug8: 无归档
        self.notifications: list = []

    def can_research(self, tid: str) -> bool:
        # bug1: 不检查前置
        if tid not in self.techs:
            return False
        return True

    def start_research(self, tid: str) -> tuple[bool, str]:
        if not self.can_research(tid):
            return False, "cannot"
        if len(self.research_queue) >= self.max_queue:
            return False, "queue full"
        # bug3: 只检查不扣除
        tech = self.techs[tid]
        for res, amt in tech.cost.items():
            if self.resources.get(res, 0) < amt:
                return False, "no resources"
        tech.researching = True
        tech.start_time = time.time()
        self.research_queue.append(tid)
        return True, "started"

    def get_effect(self, tid: str) -> dict:
        # bug4: 未研究也生效
        if tid not in self.techs:
            return {}
        return self.techs[tid].effect

    def complete_research(self, tid: str):
        tech = self.techs[tid]
        tech.complete = True
        tech.researching = False
        if tid in self.research_queue:
            self.research_queue.remove(tid)
        # bug5: 无通知

    def reset_tech(self, tid: str) -> bool:
        # bug6: 不返还资源
        if tid in self.techs:
            self.techs[tid].complete = False
            self.techs[tid].researching = False
            return True
        return False

    def archive_guild(self, guild_id: str):
        # bug8: 解散不归档
        pass
