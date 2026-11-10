# JOB-0011 执行补充报告 v1
状态: 部分完成（S01_v5 成功，成片已渲染，接缝检查包生成失败）
执行时间: 2026-11-10 16:14 → 16:20（Asia/Shanghai，约）
Codex 会话 id: 01a1bae7-f90e-7f60-bdcd-46b5a60aacb0
执行基线: main / 6decaec
前次等待报告 reports/JOB-0011.md 保留不动。

## 执行范围与前置检查

- git checkout main 与 git pull --ff-only origin main 均退出 0，Already up to date。
- 开工未跟踪文件只有用户的批准单，保持不动。找到用户新签的 approvals/S01_v5.json，上限 ¥10，批准时间 2026-11-10T16:13:42+08:00；STOP_BILLING 不存在。
- selfcheck.py 退出 0。Python 3.14.3、Pillow 12.1.1、FFmpeg/ffprobe 9.0.2、API 网络检测通过。自检 codex 一行标 [OK]，正文实际仍为 FileNotFoundError；本工单没有使用 codex exec。
- S01_v5 提交前没有 API 日志、视频或检查包；其他五个素材视频都存在。T01_cut_v2 视频和检查包原先均不存在。
- 只提交了 S01_v5 一次，未重试、未改参数、未提交其他镜头，未运行 approve.py，未创建或修改批准单、导演文件和旧报告。

## S01_v5 结果

- task_id: cgt-20261110161434-dy8n1
- 最终 status: succeeded
- usage: completion_tokens=40594，total_tokens=40594
- 预估 ¥0.94，实际以平台账单为准。
- 本地 video/S01_v5.mp4：1632590 字节，sha256 945e20b71fdad96d2243bfbf83cf882b21267d3f56a69ca4baf01965516fdf42
- 下载时间 2026-11-10T16:16:02+08:00
- 提交脚本已核验请求、报价和批准单指纹一致：72337f564f8b99c6315f7c67ddf025e43cbbbe6329f33c9fe3f1bf729f3fe07c
- logs/api/S01_v5.json 与完整 video_check/S01_v5/ 已生成。

执行命令及原文输出：

```text
python film01/tools/seedance.py submit shots/S01_v5.json
已提交 S01_v5，task_id=cgt-20261110161434-dy8n1
退出码 0

python film01/tools/seedance.py poll S01_v5 --wait 15
2026-11-10T16:14:46+08:00  S01_v5  running
2026-11-10T16:15:01+08:00  S01_v5  running
2026-11-10T16:15:16+08:00  S01_v5  running
2026-11-10T16:15:31+08:00  S01_v5  running
2026-11-10T16:15:47+08:00  S01_v5  running
2026-11-10T16:16:02+08:00  S01_v5  succeeded
已下载 video/S01_v5.mp4（1.6 MB）
退出码 0
```

## 抽帧、拼接的完整输出与报错

inspect_video.py S01_v5 退出 0；随后 assemble.py story/T01_edl_v6.json 退出 1。脚本已输出成片，但在抽取最后一个 OUT 帧后尝试读取不存在的 _5_OUT.png 时失败。未重新运行 assemble，未手工补写缺失检查包，也未覆盖现有视频。

```text
python film01/tools/inspect_video.py S01_v5
python film01/tools/assemble.py story/T01_edl_v6.json
# S01_v5 检查包

- 时长 4.04s，864x496，24.0 fps，共 97 帧，h264
- 音轨：无
- 抽帧亮度：[25.4, 45.7, 52.9, 58.8, 64.7, 72.4, 78.5, 83.9]
- 相邻抽帧差异：[23.2, 15.1, 17.0, 19.4, 22.5, 24.5, 28.2]
- 与 first_frame 原图差异：3.6（images/K0_door_gap_v1_16x9.png）
- 与 last_frame 原图差异：7.3（images/K1_typing_v2_16x9.png）

![sheet](sheet.jpg)


已写入 video_check/S01_v5/
| # | 镜头 | 素材 | 素材入/出点 | 时长 | 成片时间 |
|---|---|---|---|---|---|
| 1 | S01 | video/S01_v5.mp4 | 2.00–4.04 | 2.04s | 0.00–2.04 |
| 2 | S02 | video/S02_v6.mp4 | 0.04–2.58 | 2.54s | 2.04–4.58 |
| 3 | S03 | video/S03_insert_v1.mp4 | 0.50–2.50 | 2.00s | 4.58–6.58 |
| 4 | S04 | video/S04_v3.mp4 | 1.29–4.04 | 2.75s | 6.58–9.33 |
| 5 | S05 | video/S05_v5.mp4 | 0.04–5.04 | 5.00s | 9.33–14.33 |
| 6 | S06 | video/S06_v3.mp4 | 0.04–4.04 | 4.00s | 14.33–18.33 |
总时长 18.33s
已生成 video/T01_cut_v2.mp4（18.33s，只在本地，不提交）
Traceback (most recent call last):
  File "D:\Dramapower\film01\tools\assemble.py", line 141, in <module>
    main()
    ~~~~^^
  File "D:\Dramapower\film01\tools\assemble.py", line 122, in main
    tiles.append((f"{i + 1} {s['shot']} {label} {ts:.2f}s", Image.open(f).convert("RGB")))
                                                            ~~~~~~~~~~^^^
  File "C:\Users\24494\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\PIL\Image.py", line 3512, in open
    fp = builtins.open(filename, "rb")
FileNotFoundError: [Errno 2] No such file or directory: 'D:\\Dramapower\\film01\\video_check\\T01_cut_v2\\_5_OUT.png'
```

## 成片和检查包的实际状态

- video/T01_cut_v2.mp4 存在。只读 ffprobe -count_frames 检查结果为 H.264、864×496、24fps、440 帧、18.333333 秒、4867456 字节；视频只留本机，不提交。
- video_check/T01_cut_v2/ 只生成了 11 张原始 PNG：_0_IN/OUT、_1_IN/OUT、_2_IN/OUT、_3_IN/OUT、_4_IN/OUT、_5_IN。
- 缺少 _5_OUT.png、cuts.jpg、timeline.md。因此没有 timeline.md 原文可贴；上面的 assemble 标准输出包含脚本打印的完整时间线。
- 保留并提交这些已有接缝帧，未删除脚本产出。
- 最后 OUT 的目标时间约为 18.292 秒，接近最后一帧的边界；这仅是源码时间计算的观察，尚未证明具体报错根因，交由导演修脚本。

## 实际观看的客观情况

**S01_v5 和 T01_cut_v2 均只看了抽帧，没有连续播放。** S01 看了 8 帧接触表；成片看了三组接缝前后 PNG。无法据此确认动态没有跳动、闪烁或两帧之间的形变。

- S01_v5：从暗走廊门外推近，门口开口逐渐扩大，右门框在后段移出，左门板和把手退到左缘。少女始终坐在电脑前、双手接近键盘，尾巴在椅边摆动。碗仍在右边、勺子仍插在米饭里；未从抽帧看到新增开门的手。门缝、人物、碗和桌面随推近明显放大，局部线条随帧变化，最后一帧接近 K1 构图。无文字字幕。
- S01→S02（成片约 2.04 秒）：_0_OUT 与 _1_IN 的房间大布局接近；S02 入点人物已开始转脸、手开始离开键盘，头脸、手腕和尾部轮廓位置变化可见；未在这两张图里看到整幅黑/白闪帧。
- S04→S05（约 9.33 秒）：_3_OUT 为瞪眼、嘴含勺子，_4_IN 已转为眯眼、嘴形变化，头饰和发丝轮廓略有变化；碗、桌子和屏幕大致对齐。两张图不能判定播放时的跳变程度。
- S05→S06（约 14.33 秒）：_4_OUT 和 _5_IN 均为地上坐姿、碗盖头顶，碗的位置和房间大布局接近，嘴形、手部、发丝与饭团边缘有变化；两张图没有明显全画面亮度翻转。连续动态仍需用户播放确认。

## 需要导演或用户决定的事

- 用户可直接播放本机 video/T01_cut_v2.mp4；本轮视频生成及成片渲染已完成。
- 导演修复 assemble.py 最后 OUT 抽帧缺失导致整个检查包未完成的问题，并下发后续工单。现有脚本拒绝覆盖已存在的 T01_cut_v2，后续应按导演新工单执行，不能自行删除视频重跑。
- 本轮未产生 cuts.jpg 和 timeline.md，因此不能标为全部完成。

