# 买前问问 · 微信小程序

让朋友在你付款前给出明确意见。项目使用原生微信小程序、Python 3.12 / FastAPI 和 PostgreSQL 16；页面调用真实后端接口，演示数据保存在数据库中。

## 已有功能

- 打开即通过微信登录，无注册表单；生产环境由后端使用 code2Session 换取微信用户标识。
- 邀请码添加好友、处理申请和解除好友。
- 个人购物车：商品、价格、购买理由、分类、链接、可见范围和最多三张图片。
- 好友购物圈：评论、点赞、下踩和取消反应。
- 指定 1～10 位好友审批，意见必填；支持一票否决、多数决定、全员一致。
- 审批详情可转发为微信小程序卡片；参与者点击后自动登录并直达该审批。
- 审批分为待我审批、已处理、我发起，待办按截止时间排序并显示数量；结果以决定小票呈现。
- 清单一键“问问朋友”，商品图片可点开预览，商品链接可复制；分享封面独立绘制商品和价格。
- 审批快照、72 小时截止、撤回、并发投票保护和好友关系复核。
- PostgreSQL outbox 短信记录；新审批提醒审批人，终态提醒发起人。
- 腾讯云短信适配器已留好；无短信资质时使用 mock，在短信中心查看记录。

## 本地启动

需要 Python 3.12、Node.js 18+（用于小程序检查）和 Docker Desktop。

```powershell
cd D:\Codex\buy-review-mini
docker compose up -d postgres
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 3210
```

也可以在 PostgreSQL 启动后双击 [启动后端.cmd](D:/Codex/buy-review-mini/启动后端.cmd)。默认连接参数与 `compose.yaml` 一致。打开 [健康检查](http://127.0.0.1:3210/api/health) 应看到 `{"ok":true,"mode":"demo","smsProvider":"mock"}`。

自定义配置时复制 `.env.example` 为 `.env`，服务会自动读取。数据库由 Docker 数据卷保存，图片保存在 `data/`。

## 导入微信开发者工具

1. 导入 `D:\Codex\buy-review-mini`。根目录直接包含 `app.json` 和 `project.config.json`，不要选择上一级 `D:\Codex` 或里面的 `miniprogram` 文件夹。
2. 没有真实 AppID 时使用游客/测试方式。
3. 本地开发在「详情 → 本地设置」勾选不校验合法域名、TLS 和 HTTPS 证书。
4. 开发模式没有微信 AppSecret 时，`wx.login` 会自动进入“小满”虚构身份，数据库会同时准备好友和样例商品。

真机无法通过手机自身的 `127.0.0.1` 连接电脑。真机联调需 HTTPS 测试域名，把 [api.js](D:/Codex/buy-review-mini/miniprogram/utils/api.js) 中的 `BASE_URL` 改为该地址，并在微信公众平台配置服务器域名。

## 推荐演示流程

1. 打开小程序后自动以微信身份登录，在想买清单添加商品。
2. 发起审批，选择好友和决定规则。
3. 使用另一个已加入体验名单的微信账号处理审批并留下意见。
4. 回到发起账号查看结果和通知记录。
5. 在购物圈评论、点赞或下踩好友商品。

| 规则 | 判定 |
| --- | --- |
| 一票否决 | 一人拒绝立即结束；全部接受才通过 |
| 多数决定 | 接受数严格超过总人数一半即通过；无法达到多数时拒绝，平票拒绝 |
| 全员一致 | 等所有人提交，必须全部接受才通过 |

审批人和商品内容在发起时形成快照。解除好友后不能继续投票，但仍能查看自己参与过的历史审批。商品之后修改或删除不影响已有审批；购物圈赞踩不计入审批。

## 短信与验证

开发环境保留 `APP_MODE=demo` 和 `SMS_PROVIDER=mock`。生产环境还需配置 `WECHAT_APP_ID`、`WECHAT_APP_SECRET`；AppSecret 只能保存在后端。真实短信配置见 [短信说明](D:/Codex/buy-review-mini/docs/sms.md)。真实上线还需小程序账号、类目、备案 HTTPS 域名、隐私说明及短信签名/模板资质。

```powershell
python -m pytest backend/tests
node --test tests/client.test.mjs
node scripts/check-mini.mjs
```

PostgreSQL 集成测试需将 `TEST_DATABASE_URL` 指向名称含 `test` 的独立测试库；测试会清空其中的应用表。未配置时自动跳过。接口见 [API 约定](D:/Codex/buy-review-mini/docs/api.md)，产品范围见 [规格说明](D:/Codex/buy-review-mini/docs/spec.md)。
