# Migrations（历史审计保留）

此目录仅作**历史审计**保留，记录项目早期的数据库迁移历史。

**不被 `main.py` 自动调用。** 业务表变更通过 `scripts/dump_init_sql.py` 导出 DDL SQL，由用户手动执行。
