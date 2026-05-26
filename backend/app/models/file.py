"""
文件模型
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, BigInteger, DECIMAL, JSON, Index, UniqueConstraint
from app.models.base import BaseModel


class File(BaseModel):
    """文件元数据表"""
    
    __tablename__ = "files"
    
    # 文件信息
    original_filename = Column(String(500), nullable=False, comment="原始文件名")
    stored_filename = Column(String(500), nullable=False, comment="存储文件名")
    file_path = Column(String(500), nullable=False, comment="相对路径")
    file_size = Column(BigInteger, nullable=False, comment="文件大小（字节）")
    mime_type = Column(String(100), comment="MIME类型")
    file_hash = Column(String(64), nullable=False, index=True, comment="SHA256哈希")
    
    # 关联业务
    related_type = Column(String(20), nullable=False, index=True, comment="关联类型: contract/receipt/screenshot")
    related_id = Column(Integer, nullable=False, index=True, comment="关联ID")
    
    # OCR结果
    ocr_text = Column(Text, comment="OCR提取的文本")
    ocr_confidence = Column(DECIMAL(5, 4), comment="OCR置信度")
    
    # AI识别结果（微信截图专用）
    ai_extracted_data = Column(JSON, server_default="'{}'", comment="AI提取的数据")
    
    # 上传者
    uploaded_by = Column(Integer, ForeignKey("users.id"), index=True, comment="上传者ID")
    
    # 索引和约束
    __table_args__ = (
        Index("idx_files_related", "related_type", "related_id"),
        Index("idx_files_uploaded_by", "uploaded_by"),
        UniqueConstraint("file_hash", "related_type", "related_id", name="uq_file_hash_related"),
    )
