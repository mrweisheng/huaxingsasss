"""
用户管理服务

处理用户 CRUD、启用/禁用、密码重置/修改等业务逻辑
"""
from typing import Optional
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import AdminUserCreate, UserUpdateByAdmin
from app.core.security import get_password_hash, verify_password
from app.services.audit_service import AuditService


# 默认密码
DEFAULT_PASSWORD = "123456"


class UserService:
    """用户管理服务"""

    @staticmethod
    def get_users(
        db: Session,
        page: int = 1,
        per_page: int = 20,
        keyword: Optional[str] = None,
    ) -> tuple[list[User], int]:
        """
        分页获取用户列表

        Args:
            db: 数据库会话
            page: 页码
            per_page: 每页数量
            keyword: 搜索关键词（匹配 username/full_name/email/department）

        Returns:
            (items, total) 元组
        """
        query = db.query(User)

        if keyword:
            keyword = keyword.strip()
            if keyword:
                search_pattern = f"%{keyword}%"
                query = query.filter(
                    or_(
                        User.username.ilike(search_pattern),
                        User.full_name.ilike(search_pattern),
                        User.email.ilike(search_pattern),
                        User.department.ilike(search_pattern),
                    )
                )

        total = query.count()
        items = (
            query.order_by(User.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return items, total

    @staticmethod
    def create_user(db: Session, data: AdminUserCreate, created_by: int) -> User:
        """
        创建用户（默认密码 123456）

        Args:
            db: 数据库会话
            data: 创建数据
            created_by: 操作者用户ID

        Raises:
            ValueError: 用户名或邮箱已存在
        """
        # 用户名唯一性检查
        existing = db.query(User).filter(User.username == data.username).first()
        if existing:
            raise ValueError("用户名已存在")

        # 邮箱唯一性检查
        if data.email:
            existing_email = db.query(User).filter(User.email == data.email).first()
            if existing_email:
                raise ValueError("邮箱已被使用")

        user = User(
            username=data.username,
            full_name=data.full_name,
            email=data.email,
            role=data.role,
            department=data.department,
            password_hash=get_password_hash(DEFAULT_PASSWORD),
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        AuditService.log(
            db,
            user_id=created_by,
            action="create",
            entity_type="user",
            entity_id=user.id,
            new_values={
                "username": user.username,
                "full_name": user.full_name,
                "role": user.role,
            },
        )

        return user

    @staticmethod
    def update_user(
        db: Session,
        user_id: int,
        data: UserUpdateByAdmin,
        updated_by: int,
    ) -> User:
        """
        更新用户信息

        Args:
            db: 数据库会话
            user_id: 目标用户ID
            data: 更新数据
            updated_by: 操作者用户ID

        Raises:
            ValueError: 用户不存在或邮箱已被使用
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("用户不存在")

        # 邮箱唯一性检查
        if data.email and data.email != user.email:
            existing = db.query(User).filter(User.email == data.email, User.id != user_id).first()
            if existing:
                raise ValueError("邮箱已被其他用户使用")

        # 记录旧值
        old_values = {
            "full_name": user.full_name,
            "email": user.email,
            "department": user.department,
            "role": user.role,
        }

        # 更新字段
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)

        db.commit()
        db.refresh(user)

        new_values = {
            "full_name": user.full_name,
            "email": user.email,
            "department": user.department,
            "role": user.role,
        }

        AuditService.log(
            db,
            user_id=updated_by,
            action="update",
            entity_type="user",
            entity_id=user.id,
            old_values=old_values,
            new_values=new_values,
        )

        return user

    @staticmethod
    def toggle_active(db: Session, user_id: int, operator_id: int) -> User:
        """
        启用/禁用用户

        Args:
            db: 数据库会话
            user_id: 目标用户ID
            operator_id: 操作者用户ID

        Raises:
            ValueError: 用户不存在或不能禁用自己
        """
        if user_id == operator_id:
            raise ValueError("不能禁用自己的账户")

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("用户不存在")

        old_active = user.is_active
        user.is_active = not user.is_active
        db.commit()
        db.refresh(user)

        AuditService.log(
            db,
            user_id=operator_id,
            action="toggle_active",
            entity_type="user",
            entity_id=user.id,
            old_values={"is_active": old_active},
            new_values={"is_active": user.is_active},
        )

        return user

    @staticmethod
    def reset_password(db: Session, user_id: int, operator_id: int) -> User:
        """
        重置用户密码为默认密码

        Args:
            db: 数据库会话
            user_id: 目标用户ID
            operator_id: 操作者用户ID

        Raises:
            ValueError: 用户不存在
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("用户不存在")

        user.password_hash = get_password_hash(DEFAULT_PASSWORD)
        db.commit()
        db.refresh(user)

        AuditService.log(
            db,
            user_id=operator_id,
            action="reset_password",
            entity_type="user",
            entity_id=user.id,
            new_values={"username": user.username},
        )

        return user

    @staticmethod
    def change_password(db: Session, user_id: int, old_password: str, new_password: str) -> bool:
        """
        修改用户密码（需验证旧密码）

        Args:
            db: 数据库会话
            user_id: 用户ID
            old_password: 旧密码
            new_password: 新密码

        Raises:
            ValueError: 用户不存在或旧密码不正确
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("用户不存在")

        if not verify_password(old_password, user.password_hash):
            raise ValueError("旧密码不正确")

        user.password_hash = get_password_hash(new_password)
        db.commit()

        AuditService.log(
            db,
            user_id=user_id,
            action="change_password",
            entity_type="user",
            entity_id=user.id,
        )

        return True

    @staticmethod
    def change_password_by_username(
        db: Session,
        username: str,
        old_password: str,
        new_password: str,
    ) -> bool:
        """
        通过用户名修改密码（用于未认证场景）

        Args:
            db: 数据库会话
            username: 用户名
            old_password: 旧密码
            new_password: 新密码

        Raises:
            ValueError: 用户不存在或密码不正确（统一提示）
        """
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise ValueError("用户名或密码错误")

        if not verify_password(old_password, user.password_hash):
            raise ValueError("用户名或密码错误")

        user.password_hash = get_password_hash(new_password)
        db.commit()

        AuditService.log(
            db,
            user_id=user.id,
            action="change_password",
            entity_type="user",
            entity_id=user.id,
        )

        return True
