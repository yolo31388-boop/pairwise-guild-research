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


class ResearchError(Exception):
    pass


class ResearchSystem:
    def __init__(self, resources: float = 0):
        self.researches: dict[str, Research] = {}
        self.active_research: str | None = None
        # 研究院共享的资源池，启动研究扣除、取消研究返还
        self.resources: float = resources
        # 上一次取消研究返还的资源量，便于查询/断言
        self.last_refund: float = 0

    # ------------------------------------------------------------------
    # 研究队列
    # ------------------------------------------------------------------
    def start_research(self, rid: str) -> bool:
        """启动一个研究。同一时间只允许一个研究进行（互斥）。"""
        research = self.researches.get(rid)
        if research is None:
            return False
        if research.status != "idle":
            # 已在研究中或已完成的科技不能重复启动
            return False
        if self.active_research is not None:
            current = self.researches.get(self.active_research)
            if current is not None and current.status == "researching":
                # 互斥锁：已有正在进行的研究
                return False
        # 前置依赖（含传递依赖）必须全部完成
        completed = [r.rid for r in self.researches.values()
                     if r.status == "completed"]
        if not self.check_prerequisite(rid, completed):
            return False
        if research.cost > self.resources:
            # 资源不足，不能启动（也不能扣成负数）
            return False

        self.resources -= research.cost
        research.status = "researching"
        research.progress = 0
        # 单调时钟：不受 NTP 校时/系统时间回退影响
        research.start_time = time.monotonic()
        self.active_research = rid
        return True

    def update_progress(self, rid: str, delta_time: float | None = None) -> bool:
        """推进研究进度。基于单调时间；时间回退产生的负增量被钳制为 0。"""
        research = self.researches.get(rid)
        if not research or research.status != "researching":
            return False

        if delta_time is None:
            # 未显式传入增量时，用单调时钟自行计算经过时间
            now = time.monotonic()
            delta_time = now - research.start_time
            research.start_time = now

        # 单调时钟保证不会回退；即便外部传入负值也钳制，进度绝不倒退/变负
        if delta_time < 0:
            delta_time = 0

        research.progress = max(0.0, research.progress + delta_time)
        if research.progress >= 100:
            research.progress = 100
            research.status = "completed"
            if self.active_research == rid:
                self.active_research = None
        return True

    # ------------------------------------------------------------------
    # 科技效果
    # ------------------------------------------------------------------
    def apply_effect(self, rid: str, base_value: float) -> float:
        """只对已完成的科技生效；加法与乘法分别处理。"""
        research = self.researches.get(rid)
        if not research or research.status != "completed":
            return base_value
        if research.effect_type == "multiplicative":
            return base_value * (1 + research.effect_value)
        return base_value + research.effect_value

    def apply_all_effects(self, rids: list, base_value: float) -> float:
        """多个已完成科技叠加：加法效果求和，乘法效果连乘。

        结果 = (基础值 + 加法效果之和) * Π(1 + 乘法效果)
        研究中/不存在的科技一律不参与计算。
        """
        additive_sum = 0.0
        multiplier_product = 1.0
        for rid in rids:
            research = self.researches.get(rid)
            if not research or research.status != "completed":
                continue
            if research.effect_type == "multiplicative":
                multiplier_product *= (1 + research.effect_value)
            else:
                additive_sum += research.effect_value
        return (base_value + additive_sum) * multiplier_product

    # ------------------------------------------------------------------
    # 前置依赖（传递闭包）
    # ------------------------------------------------------------------
    def check_prerequisite(self, rid: str, completed: list) -> bool:
        """检查前置依赖闭包：直接/间接前置都必须完成。"""
        research = self.researches.get(rid)
        if not research:
            return False

        completed_set = set(completed)
        visited: set[str] = set()
        stack = list(research.prerequisites)
        while stack:
            pre = stack.pop()
            if pre in visited:
                # 依赖环保护
                continue
            visited.add(pre)
            if pre not in completed_set:
                return False
            pre_research = self.researches.get(pre)
            if pre_research is not None:
                stack.extend(pre_research.prerequisites)
        return True

    # ------------------------------------------------------------------
    # 取消研究（按比例返还资源）
    # ------------------------------------------------------------------
    def cancel_research(self, rid: str) -> bool:
        """取消进行中的研究，按剩余进度比例返还资源。"""
        research = self.researches.get(rid)
        if not research or research.status != "researching":
            return False

        # 已完成进度 progress/100，剩余比例返还
        ratio = max(0.0, min(1.0, 1 - research.progress / 100))
        refund = research.cost * ratio
        self.resources += refund
        self.last_refund = refund

        research.status = "idle"
        research.progress = 0
        research.start_time = 0
        if self.active_research == rid:
            self.active_research = None
        return True

    # ------------------------------------------------------------------
    # 研究院等级
    # ------------------------------------------------------------------
    def get_research_slot_count(self, academy_level: int) -> int:
        """研究院每升一级增加一个研究槽（等级至少为 1）。"""
        return max(1, academy_level)
