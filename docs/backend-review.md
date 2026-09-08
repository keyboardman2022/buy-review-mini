# 后端审查记录

审查范围为当前 Python/FastAPI/PostgreSQL 实现，对照 `docs/spec.md` 和 `docs/api.md`。本地未发送真实短信。

迁移前审查发现的两个高优先级问题已在 `backend/app/service.py` 修复：

- 投票事务会再次检查发起人与审批人的当前好友关系。解除好友后，历史审批仍可查看，但不能继续投票。
- 投票和撤回先使用 `SELECT ... FOR UPDATE` 锁定审批，再用同一时间点检查截止时间。到期状态与结果通知在同一事务提交，过期投票不会写入。

额外实现了 PostgreSQL outbox 唯一事件键、进程中断后的 `unknown` 状态、签名媒体 URL、图片所有权校验、验证码频率限制和会话哈希。`backend/tests/test_api_postgres.py` 提供数据库级回归测试，需要独立测试库。
