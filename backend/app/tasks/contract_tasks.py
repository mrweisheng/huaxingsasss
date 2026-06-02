"""
合同解析异步任务
"""
import asyncio
import logging
from celery import current_task
from app.tasks.celery_app import celery_app
from app.ai.llm_client import SiliconFlowClient
from app.db.session import SessionLocal
from app.models.contract import Contract
from decimal import Decimal
from datetime import date

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def parse_contract_task(self, contract_id: int, file_path: str):
    """
    异步解析合同图片/PDF

    Args:
        contract_id: 合同 ID
        file_path: 合同文件本地路径
    """
    db = SessionLocal()
    try:
        logger.info("合同解析开始: contract_id=%d, file=%s", contract_id, file_path)
        current_task.update_state(state="PROCESSING", meta={"progress": 30})

        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            logger.warning("合同不存在: contract_id=%d", contract_id)
            return {"error": "Contract not found"}

        current_task.update_state(state="PROCESSING", meta={"progress": 60})

        client = SiliconFlowClient()
        result = asyncio.run(client.parse_contract_image(file_path))

        parsed_data = result["data"]
        confidence = result["confidence"]
        logger.info("AI解析完成: contract_id=%d, confidence=%.2f", contract_id, confidence)

        # 更新结构化数据
        contract.contract_data = parsed_data

        # 保存合同全文（用于知识库问答）
        if parsed_data.get("full_text"):
            contract.contract_text = parsed_data["full_text"]

        # 提取关键字段
        if "total_amount" in parsed_data:
            try:
                contract.total_amount = Decimal(str(parsed_data["total_amount"]))
            except Exception:
                pass

        if "signed_date" in parsed_data:
            try:
                contract.signed_date = date.fromisoformat(parsed_data["signed_date"])
            except (ValueError, TypeError):
                pass

        if "business_type" in parsed_data:
            contract.business_type = parsed_data["business_type"]

        if "business_description" in parsed_data:
            contract.business_description = parsed_data["business_description"]

        validity = parsed_data.get("validity_period")
        if isinstance(validity, dict):
            if validity.get("start_date"):
                try:
                    contract.start_date = date.fromisoformat(validity["start_date"])
                except (ValueError, TypeError):
                    pass
            if validity.get("end_date"):
                try:
                    contract.end_date = date.fromisoformat(validity["end_date"])
                except (ValueError, TypeError):
                    pass

        # 同步重算 remaining_amount
        if contract.total_amount and contract.paid_amount is not None:
            contract.remaining_amount = contract.total_amount - contract.paid_amount

        # 根据置信度设置状态和元数据
        contract.confidence = round(confidence, 4) if confidence is not None else None
        contract.needs_review = confidence < 0.85 if confidence is not None else False
        if confidence >= 0.85:
            contract.status = "active"
        else:
            contract.status = "pending_review"

        db.commit()

        current_task.update_state(state="PROCESSING", meta={"progress": 100})
        logger.info("合同解析成功: contract_id=%d, status=%s", contract_id, contract.status)

        return {
            "contract_id": contract_id,
            "status": "completed",
            "confidence": confidence,
            "needs_review": confidence < 0.85,
        }

    except Exception as exc:
        logger.error("合同解析失败: contract_id=%d, error=%s", contract_id, exc, exc_info=True)
        try:
            contract = db.query(Contract).filter(Contract.id == contract_id).first()
            if contract:
                contract.status = "parse_failed"
                db.commit()
        except Exception:
            pass
        raise self.retry(exc=exc)

    finally:
        db.close()
