# film01 项目

> 总规划见仓库根目录的 `规划书.md`。所有内容只推送到 `main`。

## 分工
- 导演（云端 Claude）：故事（`story/`）、分镜、提示词、脚本、审片
- Codex（用户本地 WSL）：画图、运行脚本、推送结果。规则见 `codex-skill/film-crew/SKILL.md`
- 用户：选方向、确认画风、批准花钱（`approve.py`）、看动态、听声音

## 一轮交接
1. 导演推送工单 `jobs/JOB-xxxx.md`（以及要用的提示词、镜头参数）
2. 用户在 WSL 里对 Codex 说“执行工单”
3. Codex 拉取 → 执行 → 写 `reports/JOB-xxxx.md` → 推送
4. 用户告诉导演“推了”，导演拉取后检查

## 花钱这一步（每一镜视频）
`video_plan` 工单生成报价 → 导演另开 agent 审核提示词和首尾帧 → 导演在对话里报价
→ 用户本地运行 `python film01/tools/approve.py <clip>` 签批准单并推送
→ `video_submit` 工单提交 → `video_fetch` 工单下载并抽帧 → 导演看抽帧，用户看动态

批准单绑定请求指纹：提示词、图片、参数改了任何一处，旧批准都会失效。
接口返回疑似欠费时，脚本会写 `STOP_BILLING`，全项目停止提交。

## 命名
- 图：`images/<名字>_v<N>.png`，例如 `S03_first_v2.png`、`CHAR_lin_v1.png`、`STYLE_a_v1.png`
- 视频镜头：`<镜头>_v<N>`，例如 `S03_v1`。重拍用 `S03_v2`，不覆盖旧文件
- mp4 只在本地 `video/`；检查包 `video_check/<clip>/` 要提交
