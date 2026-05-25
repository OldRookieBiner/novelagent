'''AI 搭档会话与消息数据模型'''

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime,
    ForeignKey, CheckConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class AgentConversation(Base):
    '''AI 搭档会话 — 每个项目仅一个会话'''

    __tablename__ = 'agent_conversations'

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer,
        ForeignKey('projects.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
    )
    title = Column(String(200), default='')
    message_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship(
        'AgentMessage',
        back_populates='conversation',
        cascade='all, delete-orphan',
        order_by='AgentMessage.created_at',
    )
    project = relationship('Project', backref='agent_conversation', uselist=False)


class AgentMessage(Base):
    '''AI 搭档消息'''

    __tablename__ = 'agent_messages'
    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant')",
            name='ck_agent_messages_role',
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(
        Integer,
        ForeignKey('agent_conversations.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    role = Column(String(10), nullable=False)
    content = Column(Text, nullable=False, default='')
    segments = Column(JSONB, default=list)
    actions = Column(JSONB, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship('AgentConversation', back_populates='messages')
