# 0.0.1 本地抽样证据

`agent-meaning-review.csv` 对应 210 条抽样词卡，`agent-audio-review.csv` 对应 40 条 Commons 录音；`agent-review-summary.json` 汇总机器检查。两份 ASR JSON 是短音频辅助转写，不能代替真人听辨。原始上游字段、词遇审校显示与待审状态均分列保存。

本目录的小文件可随源码审阅；完整 SQLite、音频缓存和全量 Markdown 在被 Git 忽略的 `build/`、`dist/`。两版发布资产的准确哈希以 `dist/v0.0.1/release.json` 为准。
