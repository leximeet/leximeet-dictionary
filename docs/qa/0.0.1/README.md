# 0.0.1 候选抽样证据

这些小文件从本地 `build/v0.0.1-final/qa/` 原样复制，便于源码推送后审阅；对应 `dist/final/release-candidate.json` 的词典正文与 436 条音频固定清单。完整归档、1.22 GB SQLite、194 MB 详情 Markdown 和原 OGG 不进入 Git。本轮各文件的用途和剩余判断见 [复核记录](../../QA_REVIEW_0.0.1.md)。

| 文件 | 内容 | 注意 |
| --- | --- | --- |
| `agent-meaning-review.csv` | 210 条词卡预览、源字段检查和 9 处编辑疑点 | `human_semantic_decision=pending` 仍需独立语义判断 |
| `agent-audio-review.csv` | 40 条录音的哈希、容器、文件名与署名/许可字段检查 | `content_listening=pending`，未将 ASR 当真人试听 |
| `agent-review-summary.json` | 可机读的 210/40 统计 | 仅程序一致性计数 |
| `asr-review.json` | base.en 对 40 条 OGG 的原始转写及时长 | 短录音与同音词易误识别 |
| `asr-crosscheck.json` | small.en 对 9 条歧义录音的原始转写 | `life` 与 `wall` 的首次误识别得到交叉检查，不是最终听辨结论 |

复制后这些文件与 `build/v0.0.1-final/qa/` 同名文件的 SHA-256 一致。若今后调整词条、录音或抽样算法，应重新生成两份工作表，再更新本目录与 [总览](../../DICTIONARY_OVERVIEW.md)；不能沿用旧样本声称新包已审查。
