# 小程序与后端接口约定

Base URL http://127.0.0.1:3210。除登录和health外：Authorization: Bearer <token>。JSON成功返回直接对象（不套data），错误 {error:中文消息} 和4xx/5xx。时间均epoch毫秒。金额price整数分，输入API也是price分。列表默认最近100条。

User={id,name,initial,code,phoneMasked,color}。token存在wx本地存储仅用于会话凭证。SMS验证码不进入日志。

- GET /api/health -> {ok:true,mode:'demo'|'production',smsProvider:'mock'|'tencent'}
- POST /api/auth/code {phone} -> {challengeId,expiresIn:300,retryAfter:60,demoCode?}
- POST /api/auth/login {phone,challengeId,code,name?} -> {token,user}
- POST /api/auth/demo {account:'a'|'b'|'c'} -> {token,user}；仅demo可用，幂等播种虚构账号及样例商品与好友
- POST /api/auth/logout {} -> {ok:true}
- GET /api/me -> {user,stats:{cartCount,pendingCount,friendCount},mode,smsProvider}
- PATCH /api/me {name} -> {user}
- GET /api/friends -> {friends:User[],incoming:[{id,user,createdAt}],outgoing:[{id,user,createdAt}]}
- POST /api/friends/request {code} -> {ok:true}
- POST /api/friends/:id/respond {accept:boolean} -> {ok:true}
- DELETE /api/friends/:userId -> {ok:true}
- GET /api/items?scope=feed|mine -> {items:Item[]}
- POST /api/items {title,price,reason,category,link,visibility:'friends'|'private',images:string[]} -> {item:Item}
- GET /api/items/:id -> {item:Item,comments:Comment[]}
- PATCH /api/items/:id 同POST字段 -> {item:Item}
- DELETE /api/items/:id -> {ok:true} (软删除，不影响审批快照)
- POST /api/items/:id/comments {text} -> {comment:Comment}
- DELETE /api/comments/:id -> {ok:true} 本人评论或商品所有者
- POST /api/items/:id/reaction {value:1|-1|0} -> {ok:true}

Item={id,ownerId,owner:User,title,price,reason,category,link,visibility,images:string[],imageUrls:string[],createdAt,updatedAt,likes,dislikes,myReaction,commentCount}; images为媒体ID，imageUrls为临时可读绝对URL。Comment={id,itemId,text,createdAt,user:User}。

- POST /api/media {base64,mime:'image/png'|'image/jpeg'|'image/webp'} -> {id,url}，单图3MB，最多3张，wx文件系统readFile base64后wx.request发送JSON；签名URL由后端产生，不能接受任意外部URL当图片。
- GET /api/approvals?scope=sent|inbox -> {approvals:Approval[]}
- POST /api/approvals {itemId,reviewerIds:string[],rule:'veto'|'majority'|'unanimous'} -> {approval:Approval}
- GET /api/approvals/:id -> {approval:Approval}
- POST /api/approvals/:id/vote {decision:'accept'|'reject',comment} -> {approval:Approval}
- POST /api/approvals/:id/cancel {} -> {approval:Approval}
- GET /api/messages -> {messages:[{id,kind:'review'|'result',body,status,createdAt,approvalId,direction:'sent'|'received',recipientName}],mode,smsProvider}

Approval={id,ownerId,owner:User,itemId,title,price,reason,category,link,images:string[],imageUrls:string[],rule,status:'pending'|'approved'|'rejected'|'expired'|'cancelled',createdAt,expiresAt,reviewers:[{user:User,decision:null|'accept'|'reject',comment:null|string,votedAt:null|number}]}

前端四tab：feed购物圈/cart我的购物车/approvals审批/profile我的。另login,compose,item-detail,approval-create,approval-detail,friends,messages。待审好友才能投票；页面下拉刷新；错误可见；按钮提交期间禁用；分享只包含好友邀请码或审批ID，接收者仍须登录并通过授权校验。小程序缺真实AppID时touristappid，仅本地工具演示，不宣称已发布。
