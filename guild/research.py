"""帮派科技与研究院"""
from dataclasses import dataclass, field
import time

@dataclass
class Research:
    rid: str
    name: str
    status: str = "idle"  # idle/researching/completed
    progress: float = 0
    start_time: float = 0
    prerequisites: list = field(default_factory=list)
    effect_type: str = "additive"  # additive/multiplicative
    effect_value: float = 0
    cost: float = 0

class ResearchSystem:
    def __init__(self):
        self.researches: dict[str, Research] = {}
        self.active_research: str = None
        self.last_refund: float = 0

    def start_research(self, rid: str) -> bool:
        if rid not in self.researches:
            return False
        # 互斥：同时只能有一个研究在进行
        if self.active_research is not None:
            return False
        if any(r.status == "researching" for r in self.researches.values()):
            return False
        research = self.researches[rid]
        if research.status != "idle":
            return False
        self.researches[rid].status = "researching"
        # 用单调时钟，避免系统时间回退影响
        self.researches[rid].start_time = time.monotonic()
        self.active_research = rid
        return True

    def update_progress(self, rid: str, delta_time: float) -> bool:
        research = self.researches.get(rid)
        if not research or research.status != "researching":
            return False
        # 时间回退（如NTP校时）时进度不允许倒退
        delta_time = max(0.0, delta_time)
        research.progress += delta_time
        if research.progress >= 100:
            research.progress = 100
            research.status = "completed"
            if self.active_research == rid:
                self.active_research = None
        return True

    def apply_effect(self, rid: str, base_value: float) -> float:
        research = self.researches.get(rid)
        # 只有已完成的科技效果才生效
        if not research or research.status != "completed":
            return base_value
        if research.effect_type == "multiplicative":
            return base_value * (1 + research.effect_value)
        return base_value + research.effect_value

    def check_prerequisite(self, rid: str, completed: list) -> bool:
        research = self.researches.get(rid)
        if not research:
            return False
        # 检查传递闭包：所有间接前置也必须完成
        completed_set = set(completed)
        stack = list(research.prerequisites)
        visited = set()
        while stack:
            pre = stack.pop()
            if pre in visited:
                continue
            visited.add(pre)
            if pre not in completed_set:
                return False
            pre_research = self.researches.get(pre)
            if pre_research:
                stack.extend(pre_research.prerequisites)
        return True

    def cancel_research(self, rid: str) -> bool:
        research = self.researches.get(rid)
        if not research or research.status != "researching":
            return False
        # 按未完成的进度比例返还资源
        self.last_refund = research.cost * (1 - research.progress / 100)
        research.status = "idle"
        research.progress = 0
        research.start_time = 0
        if self.active_research == rid:
            self.active_research = None
        return True

    def get_research_slot_count(self, academy_level: int) -> int:
        # 研究院等级越高研究槽越多，每5级+1个槽
        return max(1, 1 + max(0, academy_level) // 5)
