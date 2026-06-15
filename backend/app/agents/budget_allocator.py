"""预算分配器 — 根据模型上下文窗口和阶段分配 token 预算"""

from dataclasses import dataclass

from app.agents.constants import PHASE_BUDGET_RATIOS


@dataclass(frozen=True)
class BudgetAllocation:
    """预算分配结果"""
    output_budget: int
    safety_margin: int
    system_prompt_budget: int
    history_budget: int
    previous_text_budget: int
    project_data_budget: int
    context_window: int
    phase: str


class BudgetAllocator:
    """根据 context_window + phase 分配 token 预算

    第一步：扣除固定项（output 5% 上限 50K, safety 10%, system 2%）
    第二步：按 PHASE_BUDGET_RATIOS 分配剩余预算
    """

    # 固定项比例
    OUTPUT_RATIO = 0.05
    OUTPUT_CAP = 50_000
    SAFETY_RATIO = 0.10
    SYSTEM_RATIO = 0.02

    @classmethod
    def allocate(cls, context_window: int, phase: str) -> BudgetAllocation:
        """分配 token 预算

        Args:
            context_window: 模型上下文窗口大小
            phase: 当前阶段（Phase.value）

        Returns:
            BudgetAllocation 各项预算

        Raises:
            ValueError: phase 不在 PHASE_BUDGET_RATIOS 中
        """
        if phase not in PHASE_BUDGET_RATIOS:
            raise ValueError(f"未知阶段: {phase}，有效值: {list(PHASE_BUDGET_RATIOS.keys())}")

        # 第一步：扣除固定项
        output_budget = min(int(context_window * cls.OUTPUT_RATIO), cls.OUTPUT_CAP)
        safety_margin = int(context_window * cls.SAFETY_RATIO)
        system_prompt_budget = int(context_window * cls.SYSTEM_RATIO)

        remaining = context_window - output_budget - safety_margin - system_prompt_budget
        remaining = max(remaining, 0)

        # 第二步：按阶段比例分配
        history_ratio, previous_ratio, project_data_ratio = PHASE_BUDGET_RATIOS[phase]

        return BudgetAllocation(
            output_budget=output_budget,
            safety_margin=safety_margin,
            system_prompt_budget=system_prompt_budget,
            history_budget=int(remaining * history_ratio),
            previous_text_budget=int(remaining * previous_ratio),
            project_data_budget=int(remaining * project_data_ratio),
            context_window=context_window,
            phase=phase,
        )
