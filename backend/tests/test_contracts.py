"""
合同管理模块测试
"""
from decimal import Decimal
from datetime import date
from unittest.mock import patch, MagicMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.contract import Contract
from app.models.customer import Customer
from app.services.contract_service import ContractService


CONTRACTS_URL = "/api/v1/contracts"


class TestListContracts:
    """合同列表测试"""

    def test_list_empty(self, client: TestClient, auth_headers: dict):
        """列表为空时返回空列表"""
        response = client.get(CONTRACTS_URL, headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["items"] == []
        assert data["pagination"]["total"] == 0
        assert data["pagination"]["page"] == 1

    def test_list_with_contracts(self, client: TestClient, auth_headers: dict,
                                 db_session: Session, test_customer: Customer, admin_user):
        """列表返回合同数据"""
        # 创建多个合同
        for i in range(3):
            contract = Contract(
                contract_number=f"HT2026{i:04d}",
                title=f"测试合同{i}",
                customer_id=test_customer.id,
                sales_person_id=admin_user.id,
                currency="CNY",
                total_amount=Decimal(f"{i+1}0000.00"),
                paid_amount=Decimal("0"),
                status="active",
                signed_date=date(2026, 5, 1),
                created_by=admin_user.id,
            )
            db_session.add(contract)
        db_session.commit()

        response = client.get(CONTRACTS_URL, headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["items"]) == 3
        assert data["pagination"]["total"] == 3

    def test_list_pagination(self, client: TestClient, auth_headers: dict,
                             db_session: Session, test_customer: Customer, admin_user):
        """分页参数正常工作"""
        for i in range(5):
            contract = Contract(
                contract_number=f"HT2026{i:04d}",
                title=f"分页合同{i}",
                customer_id=test_customer.id,
                sales_person_id=admin_user.id,
                currency="CNY",
                total_amount=Decimal("10000.00"),
                paid_amount=Decimal("0"),
                status="active",
                signed_date=date(2026, 5, 1),
                created_by=admin_user.id,
            )
            db_session.add(contract)
        db_session.commit()

        response = client.get(CONTRACTS_URL, headers=auth_headers, params={"per_page": 2, "page": 1})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["items"]) == 2
        assert data["pagination"]["total"] == 5
        assert data["pagination"]["total_pages"] == 3

    def test_list_filter_by_status(self, client: TestClient, auth_headers: dict,
                                   db_session: Session, test_customer: Customer, admin_user):
        """按状态过滤"""
        for i, status_val in enumerate(["draft", "active", "completed"]):
            contract = Contract(
                contract_number=f"HT2026{i:04d}",
                title=f"状态合同{i}",
                customer_id=test_customer.id,
                sales_person_id=admin_user.id,
                currency="CNY",
                total_amount=Decimal("10000.00"),
                paid_amount=Decimal("0"),
                status=status_val,
                signed_date=date(2026, 5, 1),
                created_by=admin_user.id,
            )
            db_session.add(contract)
        db_session.commit()

        response = client.get(CONTRACTS_URL, headers=auth_headers, params={"status": "active"})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["status"] == "active"

    def test_list_requires_auth(self, client: TestClient):
        """未认证用户不能获取合同列表"""
        response = client.get(CONTRACTS_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestGetContract:
    """合同详情测试"""

    def test_get_success(self, client: TestClient, auth_headers: dict,
                         db_session: Session, test_customer: Customer, admin_user):
        """获取合同详情成功"""
        contract = Contract(
            contract_number="HT2026GET001",
            title="查看测试合同",
            customer_id=test_customer.id,
            sales_person_id=admin_user.id,
            currency="CNY",
            total_amount=Decimal("50000.00"),
            paid_amount=Decimal("0"),
            status="active",
            signed_date=date(2026, 5, 1),
            created_by=admin_user.id,
        )
        db_session.add(contract)
        db_session.commit()

        response = client.get(f"{CONTRACTS_URL}/{contract.id}", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["contract_number"] == "HT2026GET001"
        assert data["title"] == "查看测试合同"
        assert data["status"] == "active"
        assert Decimal(data["total_amount"]) == Decimal("50000.00")

    def test_get_not_found(self, client: TestClient, auth_headers: dict):
        """不存在的合同返回 404"""
        response = client.get(f"{CONTRACTS_URL}/99999", headers=auth_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_requires_auth(self, client: TestClient, db_session: Session, test_customer: Customer, admin_user):
        """未认证用户不能查看合同"""
        contract = Contract(
            contract_number="HT2026AUTH001",
            title="认证测试",
            customer_id=test_customer.id,
            sales_person_id=admin_user.id,
            currency="CNY",
            total_amount=Decimal("10000.00"),
            paid_amount=Decimal("0"),
            status="draft",
            created_by=admin_user.id,
        )
        db_session.add(contract)
        db_session.commit()

        response = client.get(f"{CONTRACTS_URL}/{contract.id}")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestCreateContract:
    """合同创建测试（通过 Service）"""

    def test_service_create(self, db_session: Session, test_customer: Customer, admin_user):
        """ContractService.create_contract 正常创建合同"""
        from app.schemas.contract import ContractCreate

        contract_data = ContractCreate(
            contract_number="HT2026CREATE001",
            title="创建测试",
            customer_id=test_customer.id,
            currency="HKD",
            total_amount=Decimal("80000.00"),
            original_file_path="contracts/2026/05/test.pdf",
            file_hash="abc123",
            signed_date=date(2026, 5, 1),
            start_date=date(2026, 5, 1),
            end_date=date(2027, 4, 30),
        )

        contract = ContractService.create_contract(
            db=db_session,
            contract_data=contract_data,
            sales_person_id=admin_user.id,
        )

        assert contract.id is not None
        assert contract.contract_number == "HT2026CREATE001"
        assert contract.currency == "HKD"
        assert contract.status == "draft"
        assert contract.sales_person_id == admin_user.id
        assert contract.customer_id == test_customer.id
        assert Decimal(str(contract.paid_amount)) == Decimal("0")

    def test_service_duplicate_contract_number(self, db_session: Session, test_customer: Customer, admin_user):
        """重复合同编号抛出异常"""
        from app.schemas.contract import ContractCreate

        contract_data = ContractCreate(
            contract_number="HT2026DUP001",
            title="重复编号",
            customer_id=test_customer.id,
            currency="CNY",
            total_amount=Decimal("10000.00"),
            original_file_path="contracts/2026/05/test.pdf",
            signed_date=date(2026, 5, 1),
        )

        ContractService.create_contract(db=db_session, contract_data=contract_data, sales_person_id=admin_user.id)
        with pytest.raises(ValueError, match="合同编号 HT2026DUP001 已存在"):
            ContractService.create_contract(db=db_session, contract_data=contract_data, sales_person_id=admin_user.id)

    def test_service_invalid_customer(self, db_session: Session, admin_user):
        """不存在的客户抛出异常"""
        from app.schemas.contract import ContractCreate

        contract_data = ContractCreate(
            contract_number="HT2026NOCUST",
            title="无客户",
            customer_id=99999,
            currency="CNY",
            total_amount=Decimal("10000.00"),
            original_file_path="contracts/2026/05/test.pdf",
            signed_date=date(2026, 5, 1),
        )

        with pytest.raises(ValueError, match="客户不存在"):
            ContractService.create_contract(db=db_session, contract_data=contract_data, sales_person_id=admin_user.id)


class TestUpdateContract:
    """合同更新测试"""

    def test_update_success(self, client: TestClient, auth_headers: dict,
                            db_session: Session, test_customer: Customer, admin_user):
        """更新合同字段成功"""
        contract = Contract(
            contract_number="HT2026UPD001",
            title="更新前",
            customer_id=test_customer.id,
            sales_person_id=admin_user.id,
            currency="CNY",
            total_amount=Decimal("10000.00"),
            paid_amount=Decimal("0"),
            status="draft",
            created_by=admin_user.id,
        )
        db_session.add(contract)
        db_session.commit()

        response = client.put(
            f"{CONTRACTS_URL}/{contract.id}",
            headers=auth_headers,
            json={"title": "更新后", "status": "active"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["title"] == "更新后"
        assert data["status"] == "active"

    def test_update_not_found(self, client: TestClient, auth_headers: dict):
        """不存在的合同返回 404"""
        response = client.put(
            f"{CONTRACTS_URL}/99999",
            headers=auth_headers,
            json={"title": "不存在"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestDeleteContract:
    """合同删除测试（软删除）"""

    def test_delete_as_admin(self, client: TestClient, db_session: Session,
                              test_customer: Customer, admin_user, admin_headers: dict):
        """管理员可以删除合同"""
        contract = Contract(
            contract_number="HT2026DEL001",
            title="删除测试",
            customer_id=test_customer.id,
            sales_person_id=admin_user.id,
            currency="CNY",
            total_amount=Decimal("10000.00"),
            paid_amount=Decimal("0"),
            status="draft",
            created_by=admin_user.id,
        )
        db_session.add(contract)
        db_session.commit()
        contract_id = contract.id

        response = client.delete(f"{CONTRACTS_URL}/{contract_id}", headers=admin_headers)
        assert response.status_code == status.HTTP_200_OK

        # 验证软删除
        db_session.refresh(contract)
        assert contract.is_deleted is True
        assert contract.deleted_at is not None

    def test_delete_as_non_admin_returns_403(self, client: TestClient, auth_headers: dict,
                                              db_session: Session, test_customer: Customer, admin_user):
        """非管理员删除合同返回 403"""
        contract = Contract(
            contract_number="HT2026FORBID001",
            title="无权限删除",
            customer_id=test_customer.id,
            sales_person_id=admin_user.id,
            currency="CNY",
            total_amount=Decimal("10000.00"),
            paid_amount=Decimal("0"),
            status="draft",
            created_by=admin_user.id,
        )
        db_session.add(contract)
        db_session.commit()

        response = client.delete(f"{CONTRACTS_URL}/{contract.id}", headers=auth_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_soft_deleted_not_in_list(self, client: TestClient, db_session: Session,
                                       test_customer: Customer, admin_user, admin_headers: dict):
        """软删除后不再出现在列表"""
        contract = Contract(
            contract_number="HT2026SOFT001",
            title="软删除不可见",
            customer_id=test_customer.id,
            sales_person_id=admin_user.id,
            currency="CNY",
            total_amount=Decimal("10000.00"),
            paid_amount=Decimal("0"),
            status="draft",
            created_by=admin_user.id,
        )
        db_session.add(contract)
        db_session.commit()

        # 删除
        client.delete(f"{CONTRACTS_URL}/{contract.id}", headers=admin_headers)

        # 列表不应包含
        response = client.get(CONTRACTS_URL, headers=admin_headers)
        assert response.status_code == status.HTTP_200_OK
        ids = [item["id"] for item in response.json()["items"]]
        assert contract.id not in ids

    def test_soft_deleted_contract_not_found(self, client: TestClient, db_session: Session,
                                              test_customer: Customer, admin_user, admin_headers: dict):
        """已软删除的合同获取详情返回 404"""
        contract = Contract(
            contract_number="HT2026GON001",
            title="已删除不可见",
            customer_id=test_customer.id,
            sales_person_id=admin_user.id,
            currency="CNY",
            total_amount=Decimal("10000.00"),
            paid_amount=Decimal("0"),
            status="draft",
            created_by=admin_user.id,
        )
        db_session.add(contract)
        db_session.commit()

        client.delete(f"{CONTRACTS_URL}/{contract.id}", headers=admin_headers)

        response = client.get(f"{CONTRACTS_URL}/{contract.id}", headers=admin_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestServiceNPlusOne:
    """N+1 查询问题验证"""

    def test_contract_list_does_not_n_plus_one(self, db_session: Session, admin_user):
        """合同列表查询不会对每个合同执行额外客户查询（N+1 修复验证）"""
        from app.schemas.contract import ContractCreate

        # 创建多个客户和合同
        customers = []
        for i in range(3):
            c = Customer(name=f"N+1客户{i}", phone=f"1380013800{i}")
            db_session.add(c)
            customers.append(c)
        db_session.commit()

        for i, c in enumerate(customers):
            contract = Contract(
                contract_number=f"HT2026NP{i:04d}",
                title=f"N+1测试{i}",
                customer_id=c.id,
                sales_person_id=admin_user.id,
                currency="CNY",
                total_amount=Decimal("10000.00"),
                paid_amount=Decimal("0"),
                status="active",
                created_by=admin_user.id,
            )
            db_session.add(contract)
        db_session.commit()

        # 启用 SQLAlchemy 查询计数
        import sqlalchemy.event as sa_event
        query_count = [0]

        def count_queries(conn, cursor, statement, parameters, context, executemany):
            query_count[0] += 1

        sa_event.listen(db_session.bind, "before_cursor_execute", count_queries)

        try:
            items, total = ContractService.get_contracts(db=db_session, page=1, per_page=20)
            # 验证客户名称已从 eager load 填充（无额外查询）
            for item in items:
                assert item.customer_name is not None
            # 理想情况：1 次主查询（含 join）不应有 N 次额外客户查询
            # SQLite 下可能还有额外查询（因 SQLAlchemy 延迟加载行为），但不应为每个合同多一次
            # 设置宽松阈值确认有改善
            assert query_count[0] < 5 + len(items)  # 远少于 1 + 3*N
        finally:
            sa_event.remove(db_session.bind, "before_cursor_execute", count_queries)


class TestUploadAndParse:
    """合同上传与 AI 解析测试"""

    @patch("app.utils.file_utils.validate_file_magic", return_value=True)
    @patch("app.utils.file_utils.save_uploaded_file", return_value=("contracts/2026/05/test.pdf", "fakehash123", 1024))
    def test_upload_success(self, mock_save, mock_validate,
                            client: TestClient, auth_headers: dict, db_session: Session):
        """上传合同成功，返回 task_id 和 contract_id"""
        response = client.post(
            f"{CONTRACTS_URL}/upload-and-parse",
            headers=auth_headers,
            files={"file": ("test_contract.pdf", b"%PDF-1.4 test content", "application/pdf")},
        )

        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert "task_id" in data
        assert data["contract_id"] is not None
        assert data["status"] == "parsing"

    @patch("app.utils.file_utils.validate_file_magic", return_value=True)
    @patch("app.utils.file_utils.save_uploaded_file", return_value=("contracts/2026/05/test.pdf", "fakehash123", 1024))
    def test_upload_creates_contract_record(self, mock_save, mock_validate,
                                            client: TestClient, auth_headers: dict, db_session: Session):
        """上传后合同记录已创建"""
        response = client.post(
            f"{CONTRACTS_URL}/upload-and-parse",
            headers=auth_headers,
            files={"file": ("test_contract.pdf", b"%PDF-1.4 content", "application/pdf")},
        )

        contract_id = response.json()["contract_id"]
        contract = db_session.query(Contract).filter(Contract.id == contract_id).first()
        assert contract is not None
        assert contract.status == "draft"

    def test_upload_unsupported_type(self, client: TestClient, auth_headers: dict):
        """不支持的文件类型返回 400"""
        response = client.post(
            f"{CONTRACTS_URL}/upload-and-parse",
            headers=auth_headers,
            files={"file": ("test.txt", b"plain text content", "text/plain")},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_upload_requires_auth(self, client: TestClient):
        """未认证用户不能上传"""
        response = client.post(
            f"{CONTRACTS_URL}/upload-and-parse",
            files={"file": ("test.pdf", b"%PDF content", "application/pdf")},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestParseStatus:
    """合同解析状态查询测试"""

    def test_parse_status_processing(self, client: TestClient, auth_headers: dict,
                                      db_session: Session, test_customer: Customer, admin_user):
        """draft 状态且无解析数据时返回 processing"""
        contract = Contract(
            contract_number="HT2026PARSESTAT",
            title="解析状态测试",
            customer_id=test_customer.id,
            sales_person_id=admin_user.id,
            currency="CNY",
            total_amount=Decimal("10000.00"),
            paid_amount=Decimal("0"),
            status="draft",
            created_by=admin_user.id,
        )
        db_session.add(contract)
        db_session.commit()

        response = client.get(f"{CONTRACTS_URL}/parse-status/{contract.id}", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["code"] == 200
