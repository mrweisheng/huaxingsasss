"""
Agent 附件文件模型。

与 chat_history.attachments JSON 列配合：
  - JSON 列是「会话内附件清单」用于前端历史回看时还原"哪条消息带了哪些附件"
  - 本表是「附件实体」存物理存储路径 + 鉴权所需的 user_id，提供 /agent/files/{file_id} 下载
"""
from sqlalchemy import Column, String, Integer, Text, Index

from app.models.base import BaseModel


class AgentFile(BaseModel):
    """Agent 上传的持久化文件元数据"""

    __tablename__ = "agent_file"

    # file_id 由后端 upload 接口生成 UUID，全表唯一，供前端引用
    file_id = Column(String(64), unique=True, nullable=False, index=True, comment="UUID 标识")
    user_id = Column(Integer, nullable=False, index=True, comment="上传者用户 ID（鉴权用）")
    session_id = Column(String(100), nullable=True, index=True, comment="所属会话 ID，上传时为空，finalize 时回填")
    original_name = Column(Text, comment="原始文件名")
    mime_type = Column(String(120), comment="MIME 类型")
    file_size = Column(Integer, comment="字节大小")
    storage_path = Column(Text, nullable=False, comment="相对 AGENT_FILE_DIR 的路径")
    file_type = Column(String(20), comment="image / pdf / word / excel / text")

    __table_args__ = (
        Index("idx_agent_file_session", "session_id"),
        Index("idx_agent_file_user", "user_id"),
    )
