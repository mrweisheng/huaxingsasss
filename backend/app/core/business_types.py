"""
业务类型常量与判定工具

作为业务类型枚举的单一事实来源，供以下位置使用：
- Contract.business_type 字段（DB comment）
- GroupChat 识别的 business_type 输出（VL prompt）
- get_customer_contracts 工具的 business_type 过滤参数
- 前端业务类型下拉选项

设计原则：
- 用字符串而非 Python Enum：DB 存储与序列化更灵活
- 提供 LEGACY 映射：兼容历史数据中的「车辆业务/中港牌业务」两位枚举
"""

from typing import Optional


class BusinessType:
    """业务类型常量集合。"""

    VEHICLE_PURCHASE = "车辆买卖"
    LICENSE_TRANSFER = "两地牌过户"
    INSPECTION_INSURANCE = "年检保险"
    OTHER = "其他"

    @classmethod
    def all_values(cls) -> list[str]:
        """返回全部合法业务类型，供前端下拉与 IN 校验使用。"""
        return [
            cls.VEHICLE_PURCHASE,
            cls.LICENSE_TRANSFER,
            cls.INSPECTION_INSURANCE,
            cls.OTHER,
        ]

    @classmethod
    def is_valid(cls, value: Optional[str]) -> bool:
        """判定 value 是否为合法业务类型（含 legacy 兼容）。"""
        if not value:
            return False
        return value in cls.all_values() or value in LEGACY_VALUES

    @classmethod
    def normalize(cls, value: Optional[str]) -> Optional[str]:
        """将业务类型规整为标准值。

        - 已是标准值 → 原样返回
        - 是 legacy 值 → 映射到标准值
        - None/空 → 返回 None
        - 非法值 → 返回 None（调用方应兜底到全量）
        """
        if not value:
            return None
        v = value.strip()
        if not v:
            return None
        if v in cls.all_values():
            return v
        return LEGACY_TO_STANDARD.get(v)


# Legacy 兼容：历史数据中使用的两位枚举
LEGACY_VALUES = ("车辆业务", "中港牌业务")
LEGACY_TO_STANDARD = {
    "车辆业务": BusinessType.VEHICLE_PURCHASE,
    "中港牌业务": BusinessType.LICENSE_TRANSFER,
}
