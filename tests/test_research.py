"""帮派科技与研究院 - 红态测试"""
import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from guild.research import ResearchSystem, Research

class TestResearchMutex:
    def test_cannot_start_two_researches(self):
        rs = ResearchSystem()
        rs.researches["r1"] = Research("r1", "tech1")
        rs.researches["r2"] = Research("r2", "tech2")
        rs.start_research("r1")
        result = rs.start_research("r2")
        assert result == False

class TestMonotonicProgress:
    def test_progress_does_not_go_negative(self):
        rs = ResearchSystem()
        rs.researches["r1"] = Research("r1", "tech1", status="researching", progress=50)
        rs.update_progress("r1", -10)  # 时间回退
        assert rs.researches["r1"].progress >= 0

class TestEffectType:
    def test_multiplicative_effect_applied_correctly(self):
        rs = ResearchSystem()
        rs.researches["r1"] = Research("r1", "tech1", status="completed", effect_type="multiplicative", effect_value=0.5)
        result = rs.apply_effect("r1", 100)
        assert result == 150  # 100 * 1.5

class TestTransitivePrerequisite:
    def test_transitive_prerequisite_checked(self):
        rs = ResearchSystem()
        rs.researches["a"] = Research("a", "A")
        rs.researches["b"] = Research("b", "B", prerequisites=["a"])
        rs.researches["c"] = Research("c", "C", prerequisites=["b"])
        # 只完成了a，没完成b，c应该不能研究
        assert rs.check_prerequisite("c", ["a"]) == False

class TestCancelRefund:
    def test_cancel_returns_resources(self):
        rs = ResearchSystem()
        rs.researches["r1"] = Research("r1", "tech1", status="researching", progress=50)
        # 取消应该按比例返还
        result = rs.cancel_research("r1")
        assert result == True

class TestAcademySlots:
    def test_higher_academy_more_slots(self):
        rs = ResearchSystem()
        assert rs.get_research_slot_count(10) > rs.get_research_slot_count(1)
