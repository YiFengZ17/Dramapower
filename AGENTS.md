# 给 Codex 的说明

这个仓库是短片项目。导演是云端的 Claude，你（Codex）是画师兼执行者，GitHub 是双方的中转站。

- 按 `film-crew` skill 工作（skill 原文在 `codex-skill/film-crew/SKILL.md`）。
- 项目文件夹：`film01/`。工单在 `film01/jobs/`，报告写到 `film01/reports/`。

即使没有加载 skill，下面这几条也必须遵守：
1. 不修改 `film01/jobs/`、`film01/prompts/`、`film01/shots/`、`film01/tools/`、`film01/story/`、`film01/refs/`。
2. 不碰 `film01/approvals/`，不运行 `approve.py`，不删除 `film01/STOP_BILLING`。
3. 不提交视频文件和密钥，不打印 `ARK_API_KEY`。
4. 不覆盖、不删除已有产出；新版本存新文件。
5. 花钱的提交失败了不重试。
