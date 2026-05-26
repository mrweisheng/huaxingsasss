"""
认证模块测试
"""
from datetime import datetime, timezone
from unittest.mock import ANY, patch

import pytest
from fastapi import status

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)
from app.models.user import User


class TestRegister:
    """用户注册测试"""

    REGISTER_URL = "/api/v1/auth/register"

    def test_register_success(self, client, db_session):
        """注册新用户成功，默认角色为 sales"""
        response = client.post(self.REGISTER_URL, json={
            "username": "newuser",
            "password": "password123",
            "email": "new@example.com",
            "full_name": "新用户",
        })
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["username"] == "newuser"
        assert data["role"] == "sales"
        assert data["is_active"] is True
        assert "password" not in data

        # 确认已写入数据库
        user = db_session.query(User).filter(User.username == "newuser").first()
        assert user is not None
        assert user.email == "new@example.com"

    def test_register_duplicate_username(self, client, db_session):
        """重复用户名返回 409"""
        create_test_user = lambda: (
            db_session.add(User(username="dupuser", password_hash="hash", email="first@example.com", role="sales")),
            db_session.commit(),
        )
        db_session.add(User(username="dupuser", password_hash="hash", email="first@example.com", role="sales"))
        db_session.commit()

        response = client.post(self.REGISTER_URL, json={
            "username": "dupuser",
            "password": "password123",
            "email": "second@example.com",
        })
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "用户名已存在" in response.text

    def test_register_duplicate_email(self, client, db_session):
        """重复邮箱返回 409"""
        db_session.add(User(username="user1", password_hash="hash", email="dup@example.com", role="sales"))
        db_session.commit()

        response = client.post(self.REGISTER_URL, json={
            "username": "user2",
            "password": "password123",
            "email": "dup@example.com",
        })
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "邮箱已被使用" in response.text

    def test_register_with_admin_token(self, client, db_session, admin_user):
        """管理员 token 可创建指定角色的用户"""
        admin_token = create_access_token(subject=admin_user.id)
        response = client.post(
            self.REGISTER_URL,
            json={
                "username": "finance_user",
                "password": "password123",
                "email": "finance@example.com",
                "role": "finance",
            },
            params={"admin_token": admin_token},
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["role"] == "finance"


class TestLogin:
    """用户登录测试"""

    LOGIN_URL = "/api/v1/auth/login"

    def test_login_success(self, client, db_session):
        """正确凭证登录成功，返回 token 和用户信息"""
        from app.core.security import get_password_hash
        db_session.add(User(
            username="logintest",
            password_hash=get_password_hash("correctpass"),
            email="login@example.com",
            role="sales",
            is_active=True,
        ))
        db_session.commit()

        response = client.post(self.LOGIN_URL, json={
            "username": "logintest",
            "password": "correctpass",
        })
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["expires_in"] == 3600
        assert data["user"]["username"] == "logintest"

        # 验证 token 有效
        payload = decode_access_token(data["access_token"])
        assert payload is not None

    def test_login_wrong_password(self, client, db_session):
        """错误密码返回 401"""
        from app.core.security import get_password_hash
        db_session.add(User(
            username="wrongpass",
            password_hash=get_password_hash("realpass"),
            email="wrong@example.com",
            role="sales",
            is_active=True,
        ))
        db_session.commit()

        response = client.post(self.LOGIN_URL, json={
            "username": "wrongpass",
            "password": "wrongpass",
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_nonexistent_user(self, client):
        """不存在的用户返回 401"""
        response = client.post(self.LOGIN_URL, json={
            "username": "nobody",
            "password": "anything",
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_inactive_user(self, client, db_session):
        """已禁用的用户返回 403"""
        from app.core.security import get_password_hash
        db_session.add(User(
            username="inactiveuser",
            password_hash=get_password_hash("testpass"),
            email="inactive@example.com",
            role="sales",
            is_active=False,
        ))
        db_session.commit()

        response = client.post(self.LOGIN_URL, json={
            "username": "inactiveuser",
            "password": "testpass",
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_login_updates_last_login(self, client, db_session):
        """登录成功后更新 last_login_at"""
        from app.core.security import get_password_hash
        user = User(
            username="lastlogintest",
            password_hash=get_password_hash("testpass"),
            email="lastlogin@example.com",
            role="sales",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        user_id = user.id

        client.post(self.LOGIN_URL, json={
            "username": "lastlogintest",
            "password": "testpass",
        })

        db_session.refresh(user)
        assert user.last_login_at is not None
        assert user.last_login_at.tzinfo is not None


class TestRefreshToken:
    """Token 刷新测试"""

    REFRESH_URL = "/api/v1/auth/refresh"

    def test_refresh_success(self, client, db_session):
        """有效的 refresh token 返回新的 access token"""
        from app.core.security import get_password_hash
        user = User(
            username="refreshtest",
            password_hash=get_password_hash("testpass"),
            email="refresh@example.com",
            role="sales",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        refresh_token = create_refresh_token(subject=user.id)

        response = client.post(self.REFRESH_URL, json={"refresh_token": refresh_token})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        # 新 token 应可解码
        assert decode_access_token(data["access_token"]) is not None

    def test_refresh_invalid_token(self, client):
        """无效的 refresh token 返回 401"""
        response = client.post(self.REFRESH_URL, json={"refresh_token": "invalidtoken123"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_with_access_token(self, client, db_session):
        """access token 不能用于刷新端点"""
        user = User(username="accesstokenuser", password_hash="hash", email="access@example.com", role="sales")
        db_session.add(user)
        db_session.commit()

        access_token = create_access_token(subject=user.id)
        response = client.post(self.REFRESH_URL, json={"refresh_token": access_token})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestCurrentUser:
    """当前用户信息测试"""

    ME_URL = "/api/v1/auth/me"

    def test_get_current_user(self, client, db_session):
        """有效 token 返回当前用户信息"""
        user = User(
            username="meuser",
            password_hash="hash",
            email="me@example.com",
            full_name="测试本人",
            role="sales",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        token = create_access_token(subject=user.id)
        response = client.get(self.ME_URL, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["username"] == "meuser"
        assert data["email"] == "me@example.com"
        assert data["full_name"] == "测试本人"
        assert data["role"] == "sales"

    def test_get_current_user_no_token(self, client):
        """无 token 返回 401"""
        response = client.get(self.ME_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_current_user_invalid_token(self, client):
        """无效 token 返回 401"""
        response = client.get(self.ME_URL, headers={"Authorization": "Bearer invalidtoken"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_current_user_refresh_token_rejected(self, client, db_session):
        """refresh token 不能用于获取用户信息"""
        user = User(username="reftokenuser", password_hash="hash", email="ref@example.com", role="sales")
        db_session.add(user)
        db_session.commit()

        refresh_token = create_refresh_token(subject=user.id)
        response = client.get(self.ME_URL, headers={"Authorization": f"Bearer {refresh_token}"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_current_user_disabled(self, client, db_session):
        """已禁用的用户不能获取信息"""
        user = User(
            username="disabledme",
            password_hash="hash",
            email="disabled@example.com",
            role="sales",
            is_active=False,
        )
        db_session.add(user)
        db_session.commit()

        token = create_access_token(subject=user.id)
        response = client.get(self.ME_URL, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
