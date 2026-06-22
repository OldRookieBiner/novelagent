"""Character and relation models

人物设定模块的数据库模型，包含：
- Character: 人物设定
- Relation: 人物关系
- EvolutionPlan: 关系演变规划
- EvolutionRecord: 关系演变追溯记录
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Character(Base):
    """人物设定模型

    存储小说中的人物基本信息，包括：
    - 基本信息：姓名、角色定位
    - 性格特征：性格、口头禅、习惯动作
    - 内在驱动：深层恐惧、核心动机、成长弧线
    - 外在表现：外貌、背景故事、标志性物品
    """

    __tablename__ = "characters"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(100), nullable=False)
    role = Column(String(50), nullable=False)  # 主角/核心反派/重要配角/配角
    personality = Column(Text, nullable=True)  # 性格特征
    catchphrase = Column(String(200), nullable=True)  # 口头禅
    habit_action = Column(String(200), nullable=True)  # 习惯动作
    deep_fear = Column(Text, nullable=True)  # 深层恐惧
    core_motivation = Column(Text, nullable=True)  # 核心动机
    growth_arc = Column(Text, nullable=True)  # 成长弧线
    appearance = Column(Text, nullable=True)  # 外貌描写
    backstory = Column(Text, nullable=True)  # 背景故事
    signature_item = Column(Text, nullable=True)  # 标志性物品
    knowledge_boundary = Column(Text, nullable=True)  # 知识边界（防 OOC 核心约束）
    speech_style = Column(Text, nullable=True)  # 语言风格特征
    speech_samples = Column(Text, nullable=True)  # 代表性对话样本（分隔符分隔）
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="characters")
    # 作为关系中的 A 角色
    relations_a = relationship(
        "Relation",
        foreign_keys="Relation.character_a_id",
        back_populates="character_a",
        cascade="all, delete-orphan",
    )
    # 作为关系中的 B 角色
    relations_b = relationship(
        "Relation",
        foreign_keys="Relation.character_b_id",
        back_populates="character_b",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Character {self.name}>"


class Relation(Base):
    """人物关系模型

    存储人物之间的关系，包括：
    - 关系类型：信任/敌对/感情/合作/利用/陌生
    - 方向性：双向/单向A→B/单向B→A
    - 当前状态：关系的详细描述
    - 信任度：0-100 的数值
    """

    __tablename__ = "relations"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    character_a_id = Column(
        Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    character_b_id = Column(
        Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    relation_type = Column(String(50), nullable=False)  # 信任/敌对/感情/合作/利用/陌生
    direction = Column(
        String(20), nullable=False, default="双向"
    )  # 双向/单向A→B/单向B→A
    current_status = Column(Text, nullable=True)  # 当前状态描述
    trust_level = Column(Integer, default=50)  # 信任度 0-100
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="relations")
    character_a = relationship(
        "Character", foreign_keys=[character_a_id], back_populates="relations_a"
    )
    character_b = relationship(
        "Character", foreign_keys=[character_b_id], back_populates="relations_b"
    )
    evolution_plans = relationship(
        "EvolutionPlan", back_populates="relation", cascade="all, delete-orphan"
    )
    evolution_records = relationship(
        "EvolutionRecord", back_populates="relation", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Relation {self.character_a_id} <-> {self.character_b_id}>"


class EvolutionPlan(Base):
    """关系演变规划模型

    预先规划人物关系的变化，包括：
    - 触发章节：计划在哪个章节触发变化
    - 事件描述：引发变化的事件
    - 变化前后：关系状态和信任度的变化
    - 是否已触发：标记计划是否已执行
    """

    __tablename__ = "evolution_plans"

    id = Column(Integer, primary_key=True, index=True)
    relation_id = Column(
        Integer, ForeignKey("relations.id", ondelete="CASCADE"), nullable=False
    )
    trigger_chapter = Column(Integer, nullable=False)  # 触发章节
    event_description = Column(Text, nullable=False)  # 事件描述
    status_before = Column(Text, nullable=True)  # 变化前状态
    status_after = Column(Text, nullable=False)  # 变化后状态
    trust_before = Column(Integer, nullable=True)  # 变化前信任度
    trust_after = Column(Integer, nullable=True)  # 变化后信任度
    is_triggered = Column(Boolean, default=False)  # 是否已触发
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    relation = relationship("Relation", back_populates="evolution_plans")
    triggered_records = relationship("EvolutionRecord", back_populates="triggered_plan")

    def __repr__(self):
        return f"<EvolutionPlan relation={self.relation_id} chapter={self.trigger_chapter}>"


class EvolutionRecord(Base):
    """关系演变追溯记录模型

    记录实际发生的人物关系变化，包括：
    - 章节号：变化发生的章节
    - 内容：具体的变化内容
    - 状态变化：关系状态的变化
    - 信任度变化：信任度的增减
    - 关联规划：如果是预先规划的，关联到 EvolutionPlan
    """

    __tablename__ = "evolution_records"

    id = Column(Integer, primary_key=True, index=True)
    relation_id = Column(
        Integer, ForeignKey("relations.id", ondelete="CASCADE"), nullable=False
    )
    chapter_number = Column(Integer, nullable=False)  # 章节号
    content = Column(Text, nullable=False)  # 变化内容
    status_change = Column(Text, nullable=True)  # 状态变化
    trust_change = Column(Integer, nullable=True)  # 信任度变化（正负值）
    triggered_plan_id = Column(
        Integer, ForeignKey("evolution_plans.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    relation = relationship("Relation", back_populates="evolution_records")
    triggered_plan = relationship("EvolutionPlan", back_populates="triggered_records")

    def __repr__(self):
        return f"<EvolutionRecord relation={self.relation_id} chapter={self.chapter_number}>"
