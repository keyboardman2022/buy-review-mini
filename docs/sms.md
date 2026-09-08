# 短信适配器

实现位于 `backend/app/sms.py`。业务层先把审批通知写入 PostgreSQL outbox，后台任务再提交短信；本地短信中心展示任务状态。`sent` 表示腾讯云已受理，不等于手机最终收到。

## 本地模拟

```env
APP_MODE=demo
SMS_PROVIDER=mock
```

mock 不联网、不收费。验证码返回登录页，审批提醒和结果通知记录为 `mock`。

## 腾讯云配置

生产环境必须显式配置腾讯云，缺项时服务拒绝启动，不会回退到 mock。

```env
APP_MODE=production
SMS_PROVIDER=tencent
AUTH_SECRET=至少32字符的随机值
TENCENT_SECRET_ID=
TENCENT_SECRET_KEY=
TENCENT_SMS_APP_ID=
TENCENT_SMS_SIGN_NAME=
TENCENT_SMS_TEMPLATE_OTP=
TENCENT_SMS_TEMPLATE_REVIEW=
TENCENT_SMS_TEMPLATE_RESULT=
TENCENT_SMS_REGION=ap-guangzhou
```

| 类型 | 模板正文示例 | 参数顺序 |
| --- | --- | --- |
| `otp` | `您的验证码为{1}，{2}分钟内有效。` | `[验证码, 5]` |
| `review` | `{1}邀请您审批“{2}”，请打开买前问问查看。` | `[发起人昵称, 商品名称]` |
| `result` | `“{1}”审批结果：{2}。` | `[商品名称, 中文状态]` |

模板和变量顺序必须与控制台审核通过的内容一致。适配器把 11 位大陆手机号转换为 `+86` E.164 格式，使用 TC3-HMAC-SHA256 调用 SendSms 2021-01-11。

发送状态：`queued` 等待后台任务，`sending` 正在提交，`mock` 本地模拟完成，`sent` 供应商受理，`failed` 明确未受理，`unknown` 表示结果无法确认。服务启动时把遗留的 `sending` 改为 `unknown`，避免超时场景重复收费。当前 MVP 不接收运营商送达回执，也不自动催办。
