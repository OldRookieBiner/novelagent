"""BudgetAllocator 单元测试"""
import pytest
from app.agents.budget_allocator import BudgetAllocator, BudgetAllocation
from app.agents.constants import Phase


class TestBudgetAllocator:
    def test_writing_1m_window(self):
        """1M 窗口 WRITING 阶段预算分配"""
        alloc = BudgetAllocator.allocate(1_000_000, Phase.WRITING.value)
        # 固定项
        assert alloc.output_budget == 50_000
        assert alloc.safety_margin == 100_000
        assert alloc.system_prompt_budget == 20_000
        # 剩余 830_000
        assert alloc.history_budget == int(830_000 * 0.10)
        assert alloc.previous_text_budget == int(830_000 * 0.70)
        assert alloc.project_data_budget == int(830_000 * 0.20)
        # 总和不超 context_window
        total = (alloc.output_budget + alloc.safety_margin +
                 alloc.system_prompt_budget + alloc.history_budget +
                 alloc.previous_text_budget + alloc.project_data_budget)
        assert total <= 1_000_000

    def test_incubation_previous_text_is_zero(self):
        """孵化阶段前文预算为 0"""
        alloc = BudgetAllocator.allocate(128_000, Phase.INCUBATION.value)
        assert alloc.previous_text_budget == 0

    def test_small_window_no_negative(self):
        """极小窗口不产生负值"""
        alloc = BudgetAllocator.allocate(8192, Phase.WRITING.value)
        assert alloc.history_budget >= 0
        assert alloc.previous_text_budget >= 0
        assert alloc.project_data_budget >= 0

    def test_output_budget_capped_at_50k(self):
        """输出预算上限 50K"""
        alloc = BudgetAllocator.allocate(2_000_000, Phase.WRITING.value)
        assert alloc.output_budget == 50_000

    def test_output_budget_5_percent_for_small_window(self):
        """小窗口输出预算为 5%"""
        alloc = BudgetAllocator.allocate(100_000, Phase.WRITING.value)
        assert alloc.output_budget == 5_000

    def test_invalid_phase_raises(self):
        """无效阶段抛异常"""
        with pytest.raises(ValueError):
            BudgetAllocator.allocate(128_000, "unknown_phase")

    def test_allocation_dataclass_fields(self):
        """BudgetAllocation 包含所有预期字段"""
        alloc = BudgetAllocator.allocate(128_000, Phase.STRUCTURE.value)
        assert hasattr(alloc, "output_budget")
        assert hasattr(alloc, "safety_margin")
        assert hasattr(alloc, "system_prompt_budget")
        assert hasattr(alloc, "history_budget")
        assert hasattr(alloc, "previous_text_budget")
        assert hasattr(alloc, "project_data_budget")
        assert hasattr(alloc, "context_window")
        assert hasattr(alloc, "phase")
