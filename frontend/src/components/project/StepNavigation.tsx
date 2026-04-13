export interface StepConfig {
  index: number
  name: string
  stages: string[]  // 对应的后端 stage 列表
}

export const STEPS: StepConfig[] = [
  { index: 0, name: '信息收集', stages: ['collecting_info'] },
  { index: 1, name: '大纲生成', stages: ['outline_generating', 'outline_confirming'] },
  { index: 2, name: '章节数', stages: ['chapter_count_suggesting', 'chapter_count_confirming'] },
  { index: 3, name: '章节纲', stages: ['chapter_outlines_generating', 'chapter_outlines_confirming'] },
  { index: 4, name: '写作', stages: ['chapter_writing'] },
  { index: 5, name: '审核', stages: ['chapter_reviewing', 'completed'] },
]

export type StepStatus = 'completed' | 'current' | 'pending'

// 获取步骤状态
export function getStepStatus(stepIndex: number, currentStage: string): StepStatus {
  const step = STEPS[stepIndex]

  // 当前步骤
  if (step.stages.includes(currentStage)) {
    return 'current'
  }

  // 判断是否已完成
  const stageOrder = [
    'collecting_info',
    'outline_generating', 'outline_confirming',
    'chapter_count_suggesting', 'chapter_count_confirming',
    'chapter_outlines_generating', 'chapter_outlines_confirming',
    'chapter_writing',
    'chapter_reviewing', 'completed'
  ]

  const currentIndex = stageOrder.indexOf(currentStage)
  const lastStageOfStep = step.stages[step.stages.length - 1]
  const stepEndIndex = stageOrder.indexOf(lastStageOfStep)

  if (currentIndex > stepEndIndex) {
    return 'completed'
  }

  return 'pending'
}

// 获取当前步骤索引
export function getCurrentStepIndex(currentStage: string): number {
  for (let i = 0; i < STEPS.length; i++) {
    if (STEPS[i].stages.includes(currentStage)) {
      return i
    }
  }
  return 0
}
