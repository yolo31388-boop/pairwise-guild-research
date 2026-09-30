"""帮派科技与研究院 - 含6个bug"""
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

class ResearchSystem:
    def __init__(self):
        self.researches: dict[str, Research] = {}
        self.active_research: str = None  # bug1: 不检查互斥

    def start_research(self, rid: str) -> bool:
        # bug1: 不检查是否已有研究在进行
        if rid not in self.researches:
            return False
        self.researches[rid].status = "researching"
        self.researches[rid].start_time = time.time()
        self.active_research = rid
        return True

    def update_progress(self, rid: str, delta_time: float) -> bool:
        # bug2: 用系统时间，时间回退会出问题
        research = self.researches.get(rid)
        if not research or research.status != "researching":
            return False
        research.progress += delta_time
        if research.progress >= 100:
            research.status = "completed"
        return True

    def apply_effect(self, rid: str, base_value: float) -> float:
        # bug3: 不检查是否完成，且乘法当加法
        research = self.researches.get(rid)
        if not research:
            return base_value
        return base_value + research.effect_value

    def check_prerequisite(self, rid: str, completed: list) -> bool:
        # bug4: 只检查直接前置，不检查传递依赖
        research = self.researches.get(rid)
        if not research:
            return False
        for pre in research.prerequisites:
            if pre not in completed:
                return False
        return True

    def cancel_research(self, rid: str) -> bool:
        # bug5: 不返还资源
        research = self.researches.get(rid)
        if not research:
            return False
        research.status = "idle"
        research.progress = 0
        return True

    def get_research_slot_count(self, academy_level: int) -> int:
        # bug6: 升级不加槽
        return 1
