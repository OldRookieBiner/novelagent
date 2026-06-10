"""小说结构模型

包含情节块（PlotBlock）、问题链（PlotQuestion）和支线（Subplot）。
支撑 novelskills 的逆向规划方法论。
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.database import Base


class PlotBlock(Base):
    """情节块

    逆向规划的核心单元。每个情节块的存在理由是：
    1. 回答一个旧问题（因果链）
    2. 提出一个新问题（钩子）
    """

    __tablename__ = "plot_blocks"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    title = Column(String(200), nullable=False)
    # 要回答的旧问题列表
    questions_to_answer = Column(JSON, default=list)
    # 要提出的新问题（钩子）列表
    questions_to_raise = Column(JSON, default=list)
    # 必须发生的事件列表
    must_happen = Column(JSON, default=list)
    # 预期情绪基调
    expected_mood = Column(String(100), nullable=True)
    # 章节范围
    chapter_start = Column(Integer, nullable=True)
    chapter_end = Column(Integer, nullable=True)
    # 情节块完成摘要（写完后自动生成）
    completion_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="plot_blocks")
    plot_questions = relationship(
        "PlotQuestion", back_populates="plot_block",
        # 不使用 ORM cascade：数据库 ondelete='SET NULL' 会将 plot_block_id 置空
        # 删除情节块时问题链保留，只是脱离情节块关联
    )

    def __repr__(self):
        return f"<PlotBlock '{self.title}'>"


class PlotQuestion(Base):
    """问题链条目

    逆向规划的核心追踪单元。每个问题有三种状态：
    pending -> answered -> closed
    """

    __tablename__ = "plot_questions"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    plot_block_id = Column(
        Integer,
        ForeignKey("plot_blocks.id", ondelete="SET NULL"),
        nullable=True,
    )
    question_text = Column(Text, nullable=False)
    # pending = 待回答, answered = 已回答, closed = 已闭环
    status = Column(String(20), default="pending")
    # 提出章节
    raised_in_chapter = Column(Integer, nullable=True)
    # 回答章节
    answered_in_chapter = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="plot_questions")
    plot_block = relationship("PlotBlock", back_populates="plot_questions")

    def __repr__(self):
        return f"<PlotQuestion '{self.question_text[:30]}...'>"


class Subplot(Base):
    """支线

    多线叙事的支线登记和交汇规划。
    """

    __tablename__ = "subplots"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(200), nullable=False)
    # 涉及角色列表
    characters = Column(JSON, default=list)
    # 暗示 -> 发展中 -> 待交汇 -> 已解决
    current_status = Column(String(50), default="hint")
    raised_in_chapter = Column(Integer, nullable=True)
    planned_intersection_chapter = Column(Integer, nullable=True)
    expected_resolution_chapter = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="subplots")

    def __repr__(self):
        return f"<Subplot '{self.name}'>"
