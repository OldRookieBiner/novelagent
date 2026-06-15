from enum import Enum
"""Agent 共享常量"""

# 禁用词汇列表（AI 味检测用）
FORBIDDEN_WORDS = [
    "不禁", "竟然", "居然", "蓦然", "恍然", "心中涌起", "一股暖流",
    "下意识", "不由自主地", "心头一震", "悄然", "缓缓", "注视",
    "似乎", "仿佛", "嘴角上扬", "眼神复杂", "欲言又止", "眸光微动",
    "眼中闪过一丝", "深吸一口气", "定了定神", "迟疑了片刻",
    "心里五味杂陈", "莫名的", "本能地", "条件反射", "脑海里浮现",
    "心中一动", "暗暗", "不动声色", "目光一凝", "瞳孔微缩", "浑身一震",
    "作为 AI",
]

# 禁用句式列表
FORBIDDEN_PATTERNS = [
    "他的眼神里有复杂的情绪",
    "她的嘴角微微上扬，露出一个意味深长的笑容",
    "两人对视了一眼，仿佛有千言万语",
]

# 禁用规则列表
FORBIDDEN_RULES = [
    '每段结尾的总结性句子（如"这一夜，注定不平静"）',
    "超过 3 行的纯心理活动描写",
    '用 "……" 省略号表达沉默或情绪（最多每章出现 1 次，且不超过 3 个连续点）',
    "以风光描写开头的环境铺陈（除非这个环境本身就是角色心理的投射）",
]

# 大纲生成精简禁用词列表（约10个最常见的大纲AI味词）
OUTLINE_FORBIDDEN_WORDS_BRIEF = [
    "错综复杂",
    "扑朔迷离",
    "暗流涌动",
    "波澜壮阔",
    "命运交织",
    "跌宕起伏",
    "扣人心弦",
    "引人入胜",
    "令人唏嘘",
    "发人深省",
]

# 节点级温度配置
# 创意任务（大纲、初稿）用较高温度增加多样性，分析/审核任务用较低温度提高确定性
NODE_TEMPERATURES = {
    "outline_generation": 0.8,
    "character_generation": 0.7,
    "relation_generation": 0.5,
    "chapter_outline_generation": 0.6,
    "chapter_content_draft": 0.8,
    "chapter_writing": 0.55,  # 写作温度降低，提升指令遵循度
    "chapter_planning": 0.7,  # 规划保持较高温度
    "chapter_content_self_check": 0.3,
    "chapter_content_refine": 0.5,
    "review": 0.2,
    "rewrite": 0.5,
    "volume_arc_generation": 0.6,
    "arc_outline_generation": 0.6,
}

# Agent 自由操作温度按阶段映射
# 孵化阶段高温度保证创意发散，写作/修订阶段低温度保证果断执行工具调用
AGENT_TEMPERATURES = {
    "incubation": 0.7,
    "structure": 0.6,
    "writing": 0.5,
    "revision": 0.4,
}

# 正面风格示例库（按场景类型分类）
STYLE_EXEMPLARS = {
    "action": [
        "他侧身躲过那一拳，右肩撞上墙角，石膏碎了一块。疼是真疼，但他没出声，反而笑了一下——对手出拳的角度露了破绽。",
        "三步。她数着距离。两步。手指摸到桌沿的碎片。一步。她把碎片攥进掌心，血从指缝渗出来的时候她反而平静了。",
    ],
    "dialogue": [
        "「你来的不是时候。」他没抬头。\n「什么时候算时候？」\n「我死了以后。」",
        "「这件事你知道多少？」\n「知道不该知道那么多。」她说完就站起来走了，杯子里的茶一口没动。",
    ],
    "emotion": [
        "她把信折好放回信封，在桌上摆正，又歪了，再摆正。最后她把信封翻过来扣着，好像这样就不会看到那行字。",
        "他蹲在路边看蚂蚁搬东西，看了很久。旁边的人以为他在休息，其实他只是不想站起来面对那扇门。",
    ],
    "environment": [
        "雨下到第三天，巷口的青苔爬上了台阶。隔壁面馆的蒸气从早上六点就开始冒，混着酱油和碱水的味道。",
        "楼道的声控灯坏了三个月，没人报修。他摸黑上到五楼，钥匙插进锁孔的时候，隔壁的门开了一条缝，又关上了。",
    ],
    "opening": [
        "老陈死那天，他养的猫比他老婆先知道。",
        "电话响的时候，她正在切一颗不太新鲜的橙子。刀刃卡在果核里，她拔了两下才拔出来。第三声响的时候，她接了。",
    ],
}

# 示例动态选择规则
STYLE_EXEMPLAR_RULES = [
    ("conflict", ["打斗", "追杀", "对决", "战斗", "搏斗"], ["action", "emotion"]),
    ("hook", ["悬念", "秘密", "真相", "谜团"], ["dialogue", "emotion"]),
]

# 默认选择
STYLE_EXEMPLAR_DEFAULT = ["opening", "emotion"]




# ========== Phase Enum ==========

class Phase(str, Enum):
    """创作阶段"""
    INCUBATION = "incubation"
    STRUCTURE = "structure"
    WRITING = "writing"
    REVISION = "revision"

    @classmethod
    def values(cls):
        return [cls.INCUBATION, cls.STRUCTURE, cls.WRITING, cls.REVISION]

# 默认章节数（大纲未指定时使用）
DEFAULT_CHAPTER_COUNT = 20


# ========== 预算分配比例 ==========
# 按 Phase 分配 context_window 剩余预算（扣除 output/safety/system 固定项后）
# 格式: (history_ratio, previous_text_ratio, project_data_ratio)
PHASE_BUDGET_RATIOS = {
    Phase.INCUBATION.value: (0.60, 0.00, 0.40),
    Phase.STRUCTURE.value:  (0.40, 0.00, 0.60),
    Phase.WRITING.value:    (0.10, 0.70, 0.20),
    Phase.REVISION.value:   (0.20, 0.40, 0.40),
}
