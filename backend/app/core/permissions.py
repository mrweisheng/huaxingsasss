"""
权限模块：角色常量和权限判断函数

集中管理所有角色相关的逻辑，消除散落在各路由文件中的魔法字符串。
"""


class Role:
    ADMIN = "admin"
    INCOME = "income"
    EXPENSE = "expense"


def is_admin(user) -> bool:
    return user.role == Role.ADMIN


def can_view_income(user) -> bool:
    """admin 或 income 可查看收入数据"""
    return user.role in (Role.ADMIN, Role.INCOME)


def can_view_expense(user) -> bool:
    """admin 或 expense 可查看支出数据"""
    return user.role in (Role.ADMIN, Role.EXPENSE)


def can_create_contract(user) -> bool:
    """admin 或 income 可创建合同"""
    return user.role in (Role.ADMIN, Role.INCOME)


def can_delete_contract(user, contract=None) -> bool:
    """admin 可删除所有合同；income 可删除自己录入的合同"""
    if user.role == Role.ADMIN:
        return True
    if user.role == Role.INCOME and contract is not None:
        return contract.sales_person_id == user.id
    return False
