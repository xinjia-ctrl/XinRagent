# 数据库脚本资源

本目录是数据库迁移体系的版本化输入资料，必须随仓库提交。

## 工程化迁移入口

Python 后端的正式迁移入口在 `python-backend/alembic`：

- `python-backend/alembic/versions/0001_initial_schema.py` 会读取 `resources/database/schema_pg.sql` 创建 PostgreSQL 初始表结构。
- 新增或调整表结构时，优先新增 Alembic revision；确需同步 SQL 基线时，再更新本目录中的 SQL 文件。

## 文件说明

- `schema_pg.sql`：PostgreSQL 初始结构基线，当前 Alembic 初始迁移依赖该文件。
- `init_data_pg.sql`：初始化数据脚本，供本地或部署初始化时显式执行；不要在业务代码中隐式执行。
- `upgrade_v1.0_to_v1.1.sql`、`upgrade_v1.1_to_v1.2.sql`：历史升级 SQL，作为从旧数据库手工升级到当前结构的参考资料；当前 `schema_pg.sql` 已包含这些升级后的字段。
- `backups/`：本地数据库备份或临时 dump，已在 `.gitignore` 中忽略，不属于工程必需资料。

提交前请确认 `resources/database/*.sql` 仍被 Git 跟踪，避免出现本机有表结构、其他环境缺少迁移输入文件的问题。
