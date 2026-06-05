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
