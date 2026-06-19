# 工程资源目录

`resources/` 用于保存需要随仓库版本化的工程资源，不是本地临时目录。

当前内容：

- `database/`：数据库结构、初始化数据和历史升级 SQL 资料。Python 后端的正式迁移入口仍以 `python-backend/alembic` 为准，具体说明见 `resources/database/README.md`。

本地导出的备份、dump、临时文件不要直接放入可跟踪路径；数据库备份统一放入已忽略的 `resources/database/backups/`。
