"""
付款管理模块测试
"""
from decimal import Decimal
from datetime import date
from unittest.mock import patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.contract import Contract
from app.models.customer import Customer
from app.models.exchange_rate import ExchangeRate
from app.services.payment_service import PaymentService
from app.services.exchange_rate_service import ExchangeRateService

PAYMENTS_URL = "/api/v1/payments"


class TestCreatePayment:
    """付款创建测试"""

    def test_create_payment_cny(self, db_session: Session, test_contract: Contract, admin_user):
        """CNY 付款创建成功"""
        payment = PaymentService.create_payment_with_exchange_rate(
            db=db_session,
            contract_id=test_contract.id,
            installment_number=1,
            currency="CNY",
            amount=Decimal("50000.00"),
            paid_date=date(2026, 5, 26),
            payment_method="bank_transfer",
            created_by=admin_user.id,
        )

        assert payment.id is not None
        assert payment.currency == "CNY"
        assert Decimal(str(payment.paid_amount)) == Decimal("50000.00")
        assert payment.status == "paid"
        assert payment.payment_method == "bank_transfer"

    def test_create_payment_hkd_with_exchange_rate(self, db_session: Session,
                                                    test_contract: Contract, admin_user,
                                                    test_exchange_rate: ExchangeRate):
        """HKD 付款使用汇率折算 CNY"""
        payment = PaymentService.create_payment_with_exchange_rate(
            db=db_session,
            contract_id=test_contract.id,
            installment_number=2,
            currency="HKD",
            amount=Decimal("10000.00"),
            paid_date=date(2026, 5, 26),
            payment_method="bank_transfer",
            created_by=admin_user.id,
        )

        assert payment.currency == "HKD"
        assert Decimal(str(payment.exchange_rate)) == Decimal("0.920000")
        # HKD 10000 * 0.92 = CNY 9200
        assert Decimal(str(payment.amount_in_cny)) == Decimal("9200.00")
        assert Decimal(str(payment.paid_amount_in_cny)) == Decimal("9200.00")

    def test_create_payment_without_exchange_rate(self, db_session: Session,
                                                   test_contract: Contract, admin_user):
        """无汇率数据的币种应抛出异常"""
        from app.services.exchange_rate_service import ExchangeRateService

        with pytest.raises(ValueError, match="无法获取 USD 兑 CNY 的汇率"):
            PaymentService.create_payment_with_exchange_rate(
                db=db_session,
                contract_id=test_contract.id,
                installment_number=3,
                currency="USD",
                amount=Decimal("1000.00"),
                paid_date=date(2026, 5, 26),
                payment_method="bank_transfer",
                created_by=admin_user.id,
            )

    def test_duplicate_installment_raises(self, db_session: Session, test_contract: Contract, admin_user):
        """同一合同相同期数不能重复创建"""
        PaymentService.create_payment_with_exchange_rate(
            db=db_session,
            contract_id=test_contract.id,
            installment_number=1,
            currency="CNY",
            amount=Decimal("10000.00"),
            paid_date=date(2026, 5, 26),
            payment_method="bank_transfer",
            created_by=admin_user.id,
        )

        # SQLite 下 UniqueConstraint 冲突
        with pytest.raises(Exception):
            PaymentService.create_payment_with_exchange_rate(
                db=db_session,
                contract_id=test_contract.id,
                installment_number=1,
                currency="CNY",
                amount=Decimal("20000.00"),
                paid_date=date(2026, 5, 27),
                payment_method="cash",
                created_by=admin_user.id,
            )

    def test_payment_updates_contract_paid_amount(self, db_session: Session,
                                                   test_contract: Contract, admin_user):
        """付款后合同已付金额更新"""
        initial_paid = Decimal(str(test_contract.paid_amount))

        PaymentService.create_payment_with_exchange_rate(
            db=db_session,
            contract_id=test_contract.id,
            installment_number=10,
            currency="CNY",
            amount=Decimal("30000.00"),
            paid_date=date(2026, 5, 26),
            payment_method="bank_transfer",
            created_by=admin_user.id,
        )

        db_session.refresh(test_contract)
        assert Decimal(str(test_contract.paid_amount)) == initial_paid + Decimal("30000.00")

    def test_payment_completes_contract(self, db_session: Session, admin_user,
                                         test_customer: Customer):
        """全额付款后合同状态变为 completed"""
        contract = Contract(
            contract_number="HT2026FULL001",
            title="全额付款测试",
            customer_id=test_customer.id,
            sales_person_id=admin_user.id,
            currency="CNY",
            total_amount=Decimal("50000.00"),
            paid_amount=Decimal("0"),
            total_amount_in_cny=Decimal("50000.00"),
            paid_amount_in_cny=Decimal("0"),
            status="active",
            signed_date=date(2026, 5, 1),
            created_by=admin_user.id,
        )
        db_session.add(contract)
        db_session.commit()

        PaymentService.create_payment_with_exchange_rate(
            db=db_session,
            contract_id=contract.id,
            installment_number=1,
            currency="CNY",
            amount=Decimal("50000.00"),
            paid_date=date(2026, 5, 26),
            payment_method="bank_transfer",
            created_by=admin_user.id,
        )

        db_session.refresh(contract)
        assert contract.status == "completed"


class TestListPayments:
    """付款列表测试"""

    def test_list_empty(self, client: TestClient, auth_headers: dict):
        """空列表"""
        response = client.get(PAYMENTS_URL, headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["items"] == []
        assert data["pagination"]["total"] == 0

    def test_list_with_payments(self, client: TestClient, auth_headers: dict,
                                 db_session: Session, test_contract: Contract, admin_user):
        """列表包含付款记录"""
        payment = Payment(
            contract_id=test_contract.id,
            installment_number=1,
            currency="CNY",
            amount=Decimal("10000.00"),
            paid_amount=Decimal("10000.00"),
            paid_date=date(2026, 5, 26),
            payment_method="bank_transfer",
            status="paid",
            created_by=admin_user.id,
        )
        db_session.add(payment)
        db_session.commit()

        response = client.get(PAYMENTS_URL, headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["currency"] == "CNY"
        assert Decimal(data["items"][0]["paid_amount"]) == Decimal("10000.00")

    def test_list_filter_by_contract(self, client: TestClient, auth_headers: dict,
                                      db_session: Session, test_contract: Contract,
                                      admin_user):
        """按合同 ID 过滤"""
        # 创建第二个合同
        other = Contract(
            contract_number="HT2026OTHER",
            title="其他合同",
            sales_person_id=admin_user.id,
            currency="CNY",
            total_amount=Decimal("10000.00"),
            paid_amount=Decimal("0"),
            status="active",
            created_by=admin_user.id,
        )
        db_session.add(other)
        db_session.commit()

        # 为 test_contract 添加付款
        db_session.add(Payment(
            contract_id=test_contract.id, installment_number=1,
            currency="CNY", amount=Decimal("5000.00"), paid_amount=Decimal("5000.00"),
            paid_date=date(2026, 5, 26), payment_method="bank_transfer",
            status="paid", created_by=admin_user.id,
        ))
        # 为 other 合同添加付款
        db_session.add(Payment(
            contract_id=other.id, installment_number=1,
            currency="CNY", amount=Decimal("3000.00"), paid_amount=Decimal("3000.00"),
            paid_date=date(2026, 5, 26), payment_method="cash",
            status="paid", created_by=admin_user.id,
        ))
        db_session.commit()

        response = client.get(PAYMENTS_URL, headers=auth_headers, params={"contract_id": test_contract.id})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["contract_id"] == test_contract.id

    def test_list_requires_auth(self, client: TestClient):
        """未认证用户不能获取付款列表"""
        response = client.get(PAYMENTS_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestContractPayments:
    """合同付款汇总测试"""

    CONTRACT_PAYMENTS_URL = f"{PAYMENTS_URL}/contract"

    def test_get_contract_payments(self, db_session: Session, test_contract: Contract, admin_user):
        """获取合同付款汇总"""
        # 创建两笔付款
        PaymentService.create_payment_with_exchange_rate(
            db=db_session, contract_id=test_contract.id,
            installment_number=1, currency="CNY",
            amount=Decimal("30000.00"), paid_date=date(2026, 5, 26),
            payment_method="bank_transfer", created_by=admin_user.id,
        )
        PaymentService.create_payment_with_exchange_rate(
            db=db_session, contract_id=test_contract.id,
            installment_number=2, currency="CNY",
            amount=Decimal("20000.00"), paid_date=date(2026, 5, 27),
            payment_method="bank_transfer", created_by=admin_user.id,
        )

        result = PaymentService.get_contract_payments(db_session, test_contract.id)
        assert result["contract_id"] == test_contract.id
        assert len(result["payments"]) == 2
        assert Decimal(str(result["paid_amount"])) == Decimal("50000.00")
        assert Decimal(str(result["remaining_amount"])) == Decimal("50000.00")

    def test_get_payments_nonexistent_contract(self, db_session: Session):
        """不存在的合同抛出异常"""
        with pytest.raises(ValueError, match="合同不存在"):
            PaymentService.get_contract_payments(db_session, 99999)


class TestExchangeRateService:
    """汇率服务测试"""

    def test_same_currency_rate_is_one(self, db_session: Session):
        """同币种汇率为 1.0"""
        rate = ExchangeRateService.get_exchange_rate(
            db=db_session,
            from_currency="CNY",
            to_currency="CNY",
            rate_date=date(2026, 5, 26),
        )
        assert rate == Decimal("1.0")

    def test_get_exchange_rate_record_same_currency(self, db_session: Session):
        """同币种返回虚拟汇率记录"""
        record = ExchangeRateService.get_exchange_rate_record(
            db=db_session,
            from_currency="HKD",
            to_currency="HKD",
            rate_date=date(2026, 5, 26),
        )
        assert record.rate == Decimal("1.0")
        assert record.source == "system"

    def test_exchange_rate_lookup_priority(self, db_session: Session):
        """最新汇率的查找优先级"""
        # 创建较旧汇率
        old = ExchangeRate(
            from_currency="USD", to_currency="CNY",
            rate=Decimal("7.200000"),
            rate_date=date(2026, 4, 1),
            source="manual", is_active=True,
        )
        db_session.add(old)
        # 创建较新汇率
        newer = ExchangeRate(
            from_currency="USD", to_currency="CNY",
            rate=Decimal("7.250000"),
            rate_date=date(2026, 5, 20),
            source="manual", is_active=True,
        )
        db_session.add(newer)
        db_session.commit()

        rate = ExchangeRateService.get_exchange_rate(
            db=db_session,
            from_currency="USD",
            to_currency="CNY",
            rate_date=date(2026, 5, 25),
        )
        # 应返回 5月20日 的汇率（30天内最近）
        assert rate == Decimal("7.250000")

    def test_exchange_rate_not_found(self, db_session: Session):
        """未找到汇率返回 None"""
        rate = ExchangeRateService.get_exchange_rate(
            db=db_session,
            from_currency="EUR",
            to_currency="CNY",
            rate_date=date(2026, 5, 26),
        )
        assert rate is None


class TestUploadReceipt:
    """付款凭证上传测试"""

    @patch("app.utils.file_utils.save_uploaded_file",
           return_value=("receipts/2026/05/receipt.jpg", "receipthash", 2048))
    def test_upload_receipt_success(self, mock_save, client: TestClient, auth_headers: dict,
                                     db_session: Session, test_contract: Contract,
                                     test_exchange_rate: ExchangeRate):
        """上传付款凭证成功"""
        response = client.post(
            f"{PAYMENTS_URL}/upload-receipt",
            headers=auth_headers,
            data={
                "contract_id": str(test_contract.id),
                "installment_number": 5,
                "currency": "HKD",
                "paid_amount": "5000.00",
                "paid_date": "2026-05-26",
                "payment_method": "bank_transfer",
            },
            files={"file": ("receipt.jpg", b"fake-image-content", "image/jpeg")},
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["currency"] == "HKD"
        assert Decimal(data["paid_amount"]) == Decimal("5000.00")
        # HKD 5000 * 0.92 = CNY 4600
        assert Decimal(data["amount_in_cny"]) == Decimal("4600.00")

    def test_upload_receipt_no_file(self, client: TestClient, auth_headers: dict,
                                     db_session: Session, test_contract: Contract,
                                     test_exchange_rate: ExchangeRate):
        """不上传凭证文件也可创建付款"""
        response = client.post(
            f"{PAYMENTS_URL}/upload-receipt",
            headers=auth_headers,
            data={
                "contract_id": str(test_contract.id),
                "installment_number": 6,
                "currency": "CNY",
                "paid_amount": "10000.00",
                "paid_date": "2026-05-26",
                "payment_method": "cash",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["payment_method"] == "cash"
        assert Decimal(data["paid_amount"]) == Decimal("10000.00")

    def test_upload_receipt_requires_auth(self, client: TestClient):
        """未认证用户不能上传付款凭证"""
        response = client.post(
            f"{PAYMENTS_URL}/upload-receipt",
            data={
                "contract_id": "1",
                "installment_number": 1,
                "currency": "CNY",
                "paid_amount": "1000.00",
                "paid_date": "2026-05-26",
                "payment_method": "bank_transfer",
            },
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
