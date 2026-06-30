# 【安全·高优先·今日办】U9C client_secret 轮换请求

**背景**：U9C webApi 的 OAuth2 `client_secret`（明文）此前被写进脚本并推到 GitHub，归档仓 history 里仍残留。该 secret 能换取 JWT、读取真实 ERP 数据，属**暴露中的活凭据**。删代码无法清除 history 残留，唯一有效处置是**在 U9C 侧重置 secret，使旧值立即失效**。

**请 IT 今日执行**：
1. 登录 U9C webApi / OAuth2 应用管理后台，定位我司对应应用（`client_id`：__＿＿＿＿＿＿，请填本仓库 .env 中的值__）。
2. **regenerate / 重置 client_secret** —— 重置即旧值作废，风险解除。
3. 把新 `client_secret` 用**企微私聊**发给 Paul。**切勿**走邮件、切勿写进任何文件或提交到 git。

**重置后我方会做**：用新值跑 `OAuth2/AuthLogin` + `BOM/Query` 冒烟验证（确认新值通），并用旧值试登确认返回 401（确认旧值已死）。

**烦请今天内完成第 1–3 步并回告。** 谢谢。
