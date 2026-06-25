"""凭证不匹配手动放行审计模型

对应表 payment_override_audit（DDL 见 public.sql / 提交切片 1）。
每次对话流中用户在 soft_mismatch 状态下手动放行落库，落一条；
无凭证支出（manual 模式）也可记一条以备审计；
hard_conflict 永远进不到这里（工具入口硬挡）。

与 audit_logs（中间件/Service 显式调用写入）互补：
  - audit_logs：通用 CRUD 审计，关注"谁改了什么字段"
  - payment_override_audit：业务级放行事件，关注"识别 vs 输入 的差异 + 放行理由"
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, DateTime, Index, JSON, func, CheckConstraint
from app.db.session import Base


class PaymentOverrideAudit(Base):
    """凭证不匹配手动放行审计表。

    使用裸 Base（非 BaseModel）——本表不需要 updated_at / is_deleted / soft_delete：
    审计记录一旦写入永不修改、永不删除。
    """

    __tablename__ = "payment_override_audit"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    payment_id = Column(Integer, ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False, index=True, comment="关联付款 ID")
    operator_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True, comment="放行人 user_id；用户删后置 NULL")
    operator_name = Column(String(100), nullable=False, comment="冗余存放行人姓名/用户名，保证审计可读")
    operator_role = Column(String(20), comment="放行时的角色快照（admin/income/expense）")
    session_id = Column(String(64), comment="Agent 会话 ID，可回溯到具体对话")
    match_status = Column(String(20), nullable=False, comment="放行时的匹配状态：soft_mismatch/manual/hard_conflict")
    override_reason = Column(Text, nullable=False, comment="用户填写的放行理由")
    extracted_snapshot = Column(JSON, comment="凭证 OCR/VL 识别结果快照 JSON")
    user_input_snapshot = Column(JSON, comment="用户对话中提供的信息快照 JSON")
    expected_snapshot = Column(JSON, comment="合同/付款计划中应当匹配的字段快照 JSON")
    diff_fields = Column(JSON, comment="差异字段清单 JSON 数组")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="放行时间")

    __table_args__ = (
        Index("idx_payment_override_audit_payment_id", "payment_id"),
        Index("idx_payment_override_audit_operator_id", "operator_id"),
        Index("idx_payment_override_audit_created_at", "created_at"),
        CheckConstraint(
            "match_status IN ('soft_mismatch','hard_conflict','manual')",
            name="payment_override_audit_match_status_chk",
        ),
    )
