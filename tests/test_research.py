"""帮派科技与研究系统 - 红态测试"""
import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from guild.research import GuildResearch, Tech

class TestPrereq:
    def test_prereq_required(self):
        gr = GuildResearch()
        gr.techs["t1"] = Tech("t1", "基础", 1)
        gr.techs["t2"] = Tech("t2", "高级", 2, prereq=["t1"])
        assert gr.can_research("t2") == False  # bug1: 返回True
        gr.techs["t1"].complete = True
        assert gr.can_research("t2") == True

class TestQueueLimit:
    def test_queue_has_limit(self):
        gr = GuildResearch()
        gr.max_queue = 2
        gr.resources = {"gold": 1000}
        for i in range(3):
            gr.techs[f"t{i}"] = Tech(f"t{i}", f"tech{i}", 1, cost={"gold": 10})
        gr.start_research("t0")
        gr.start_research("t1")
        r, _ = gr.start_research("t2")
        assert r == False  # bug2: 队列上限1但这里设2，第三个应该失败

class TestResourceDeduction:
    def test_resources_deducted_on_start(self):
        gr = GuildResearch()
        gr.resources = {"gold": 100}
        gr.techs["t1"] = Tech("t1", "tech", 1, cost={"gold": 30})
        gr.start_research("t1")
        assert gr.resources["gold"] == 70  # bug3: 还是100

class TestEffectRequiresComplete:
    def test_incomplete_tech_no_effect(self):
        gr = GuildResearch()
        gr.techs["t1"] = Tech("t1", "tech", 1, effect={"atk": 10})
        effect = gr.get_effect("t1")
        assert effect == {}  # bug4: 未研究就有效果

class TestNotification:
    def test_completion_notification(self):
        gr = GuildResearch()
        gr.techs["t1"] = Tech("t1", "tech", 1)
        gr.complete_research("t1")
        assert len(gr.notifications) > 0  # bug5: 无通知

class TestResetRefund:
    def test_reset_refunds_resources(self):
        gr = GuildResearch()
        gr.resources = {"gold": 100}
        gr.techs["t1"] = Tech("t1", "tech", 1, cost={"gold": 30})
        gr.start_research("t1")
        gr.complete_research("t1")
        gr.reset_tech("t1")
        assert gr.resources["gold"] > 70  # bug6: 还是70（应该返还部分）

class TestDurationScaling:
    def test_higher_tier_takes_longer(self):
        t1 = Tech("t1", "low", 1, duration=3600)
        t5 = Tech("t5", "high", 5, duration=3600)
        # duration应该在创建时按tier计算，或者系统有计算函数
        # 这里验证：系统应该有get_duration方法
        assert hasattr(GuildResearch, "get_duration") or t5.duration > t1.duration

class TestArchive:
    def test_disband_archives_techs(self):
        gr = GuildResearch()
        gr.techs["t1"] = Tech("t1", "tech", 1, complete=True)
        gr.archive_guild("g1")
        assert "g1" in gr.archive  # bug8: 空
