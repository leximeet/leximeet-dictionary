# 0.0.1 本地抽样证据

`agent-meaning-review.csv` 对应最终候选的 210 条词卡，`agent-audio-review.csv` 对应 40 条录音；`agent-review-summary.json` 汇总机器检查。两份 ASR JSON 是短音频辅助转写，不能代替真人听辨。原始上游字段、词遇审校显示与待审状态均分列保存。

本目录的小文件可随源码审阅；完整 SQLite、归档和全量 Markdown 在被 Git 忽略的 `build/v0.0.1-final/`、`dist/final/`。准确资产哈希以 `dist/final/release-candidate.json` 为准。
