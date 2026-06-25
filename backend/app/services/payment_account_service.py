"""
收款账户服务层
"""
import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.payment_account import PaymentAccount
from app.schemas.payment_account import PaymentAccountCreate

logger = logging.getLogger(__name__)


class PaymentAccountService:
    """收款账户服务"""
    
    @staticmethod
    def list_accounts(db: Session) -> List[PaymentAccount]:
        """列出所有有效收款账户"""
        return (
            db.query(PaymentAccount)
            .filter(PaymentAccount.is_deleted == False)
            .order_by(PaymentAccount.sort_order.asc(), PaymentAccount.id.asc())
            .all()
        )
    
    @staticmethod
    def create_account(db: Session, data: PaymentAccountCreate, user_id: int) -> PaymentAccount:
        """创建收款账户"""
        if data.is_default:
            db.query(PaymentAccount).filter(
                PaymentAccount.is_default == True,
                PaymentAccount.is_deleted == False,
            ).update({"is_default": False})
        
        account = PaymentAccount(
            account_type=data.account_type,
            title=data.title,
            account_name=data.account_name,
            account_number=data.account_number,
            qr_code_url=data.qr_code_url,
            fps_id=data.fps_id,
            bank_name=data.bank_name,
            branch=data.branch,
            address=data.address,
            phone=data.phone,
            swift_code=data.swift_code,
            extra_info=data.extra_info or {},
            is_default=data.is_default,
            sort_order=data.sort_order,
            created_by=user_id,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        return account
    
    @staticmethod
    def delete_account(db: Session, account_id: int) -> bool:
        """软删收款账户"""
        account = (
            db.query(PaymentAccount)
            .filter(PaymentAccount.id == account_id, PaymentAccount.is_deleted == False)
            .first()
        )
        if not account:
            return False
        account.soft_delete()
        db.commit()
        return True

    @staticmethod
    def find_by_hint(db: Session, hint: str) -> Optional[PaymentAccount]:
        """根据简称模糊匹配收款账户（供凭证识别后自动关联 payment_account_id）。

        匹配策略按优先级降级：
        0. extra_info.aliases 精确等值：管理员显式登记的别名（如"高山香港账户"），
           最高优先级，零拆词零误判
        1. 全包含：title 包含 hint 或 hint 包含 title（如 hint="高山香港账户"，title="高山-HSBC"）
        2. 副字段全包含：account_name + bank_name 拼接串包含 hint
        3. 2-gram 拆词命中数：hint 拆 2 字 token，统计 token 在 title/account_name/bank_name
           的命中数，要求至少命中 2 个 token 才算匹配，按命中数降序取最高分

        Returns:
            匹配到的 PaymentAccount；无匹配返回 None。
        """
        hint = (hint or "").strip()
        if not hint:
            return None

        accounts = (
            db.query(PaymentAccount)
            .filter(PaymentAccount.is_deleted == False)
            .all()
        )
        if not accounts:
            return None

        # 优先级 0：extra_info.aliases 精确等值（管理员显式登记的别名，最高优先级）
        for acc in accounts:
            aliases = (acc.extra_info or {}).get("aliases") or []
            if not isinstance(aliases, list):
                continue
            for alias in aliases:
                if isinstance(alias, str) and alias.strip() == hint:
                    return acc

        # 优先级 1：title 全包含
        for acc in accounts:
            if acc.title and (hint in acc.title or acc.title in hint):
                return acc

        # 优先级 2：account_name + bank_name 任一字段包含 hint
        for acc in accounts:
            haystack = " ".join(filter(None, [acc.account_name, acc.bank_name]))
            if haystack and hint in haystack:
                return acc

        # 优先级 3：2-gram 拆词命中数排序
        tokens = {hint[i : i + 2] for i in range(len(hint) - 1)}
        tokens = {t for t in tokens if len(t.strip()) == 2}
        if not tokens:
            return None

        scored: List[tuple] = []
        for acc in accounts:
            searchable = " ".join(filter(None, [acc.title, acc.account_name, acc.bank_name]))
            if not searchable:
                continue
            score = sum(1 for t in tokens if t in searchable)
            if score >= 2:  # 至少 2 个 token 命中才算匹配，防误匹配
                scored.append((score, acc))

        if not scored:
            return None
        scored.sort(key=lambda x: (-x[0], x[1].id))
        return scored[0][1]
