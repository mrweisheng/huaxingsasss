"""
对话历史模型
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, DECIMAL, JSON, Index
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from app.models.base import BaseModel


class ChatHistory(BaseModel):
    """对话历史表"""
    
    __tablename__ = "chat_history"
    
    user_id = Column(Integer, ForeignKey("users.id"), index=True, comment="用户ID")
    session_id = Column(String(100), index=True, comment="会话ID")
    question = Column(Text, nullable=False, comment="用户问题")
    answer = Column(Text, comment="AI回答")
    context_contracts = Column(ARRAY(Integer), comment="参考的合同ID列表")
    intent_type = Column(String(50), comment="意图类型")
    extracted_entities = Column(JSONB, comment="提取的实体")
    sql_query = Column(Text, comment="生成的SQL查询")
    llm_model = Column(String(50), comment="使用的模型")
    tokens_used = Column(Integer, comment="消耗的token数")
    confidence = Column(DECIMAL(5, 4), comment="回答置信度")
    
    # 索引
    __table_args__ = (
        Index("idx_chat_user", "user_id"),
        Index("idx_chat_session", "session_id"),
        Index("idx_chat_created", "created_at"),
    )
