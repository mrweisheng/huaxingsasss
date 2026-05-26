"""
pytest 配置和夹具
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 必须在任何应用模块导入前配置环境变量
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only-32chars!")
os.environ.setdefault("SILICONFLOW_API_KEY", "test-api-key")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LOG_LEVEL", "ERROR")

from typing import Generator, Any
from decimal import Decimal
from datetime import date, datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from app.db.session import Base, get_db
from app.main import app
from app.api.dependencies import get_current_user
from app.models.user import User
from app.models.contract import Contract
from app.models.customer import Customer
from app.models.payment import Payment
from app.models.exchange_rate import ExchangeRate
from app.core.security import get_password_hash, create_access_token

# 使用 SQLite 内存数据库（测试用）
TEST_DATABASE_URL = "sqlite://"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})

# 启用 SQLite 外键支持
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """创建所有表（每个 session 一次）"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """每个测试一个独立事务"""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    # 覆盖依赖中的 get_db 使用测试 session
    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    yield session

    # 清理依赖覆盖
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI 测试客户端"""
    with TestClient(app) as c:
        yield c


def create_test_user(db: Session, **kwargs) -> User:
    """创建测试用户"""
    user = User(
        username=kwargs.get("username", "testuser"),
        password_hash=get_password_hash(kwargs.get("password", "testpass123")),
        email=kwargs.get("email", "test@example.com"),
        full_name=kwargs.get("full_name", "测试用户"),
        role=kwargs.get("role", "sales"),
        is_active=kwargs.get("is_active", True),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_auth_header(db: Session, user: User = None) -> dict:
    """获取认证请求头"""
    if user is None:
        user = create_test_user(db)
    token = create_access_token(subject=user.id)
    return {"Authorization": f"Bearer {token}"}


# --- 测试用 fixture 覆盖依赖 ---

@pytest.fixture
def auth_headers(db_session: Session) -> dict:
    """创建一个用户并返回认证头"""
    user = create_test_user(db_session)

    async def override_user():
        return user

    app.dependency_overrides[get_current_user] = override_user
    return get_auth_header(db_session, user)


@pytest.fixture
def admin_user(db_session: Session) -> User:
    """创建管理员用户"""
    return create_test_user(
        db_session,
        username="admin",
        password="admin123",
        email="admin@example.com",
        role="admin",
    )


@pytest.fixture
def admin_headers(db_session: Session, admin_user: User) -> dict:
    """管理员认证头"""
    async def override_user():
        return admin_user
    app.dependency_overrides[get_current_user] = override_user
    token = create_access_token(subject=admin_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_customer(db_session: Session) -> Customer:
    """创建测试客户"""
    customer = Customer(
        name="测试客户有限公司",
        contact_person="张三",
        phone="13800138000",
        email="contact@testcompany.com",
        address="深圳市南山区科技园",
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    return customer


@pytest.fixture
def test_contract(db_session: Session, test_customer: Customer, admin_user: User) -> Contract:
    """创建测试合同"""
    contract = Contract(
        contract_number="HT202605260001",
        title="测试合同",
        customer_id=test_customer.id,
        sales_person_id=admin_user.id,
        currency="CNY",
        total_amount=Decimal("100000.00"),
        paid_amount=Decimal("0"),
        total_amount_in_cny=Decimal("100000.00"),
        paid_amount_in_cny=Decimal("0"),
        status="active",
        signed_date=date(2026, 5, 1),
        created_by=admin_user.id,
    )
    db_session.add(contract)
    db_session.commit()
    db_session.refresh(contract)
    return contract


@pytest.fixture
def test_exchange_rate(db_session: Session) -> ExchangeRate:
    """创建测试汇率（HKD→CNY）"""
    rate = ExchangeRate(
        from_currency="HKD",
        to_currency="CNY",
        rate=Decimal("0.920000"),
        rate_date=date(2026, 5, 26),
        source="manual",
        is_active=True,
    )
    db_session.add(rate)
    db_session.commit()
    db_session.refresh(rate)
    return rate
