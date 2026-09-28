# 0.0.1 质量记录

0.0.1 的程序验收针对两个词包：核心版 117,902 条词卡均有离线音频；完整版 811,092 条词卡共享这批核心音频。固定数据底座的 JSONL/SQLite 已深度核对；最终 `dist/v0.0.1` 通过两版逐文件哈希、音频索引覆盖、核心词卡一致性、SQLite 分片重组和 `PRAGMA integrity_check`。数据底座记录 `generator.dirty=false`，对应本地内容提交 `9cbfe53`。验证命令见 [构建说明](BUILD.md)。

| 抽样 | 已验证 | 人工判断的边界 |
| --- | --- | --- |
| 210 条词义 | 抽样字段与词包一致；9 个疑点中的 8 个已在词遇审校层处理，保留原字段和核对页面。 | `Nussbaum's braceiets` 的规范拼写缺少充分一手依据，未擅自改写；抽样不能代表 81 万词全部人工审定。 |
| 40 条 Commons 录音 | 字节哈希、OGG 容器、文件名及署名/许可字段一致；全部 436 条固定录音可解码。 | ASR 仅辅助筛查；真人是否读准、音色是否自然，仍需维护者试听。 |
| 核心词音频 | 117,902 个核心 `entry_id` 均有缓存文件；最终分片的完整索引与音频字节哈希通过。 | 程序校验与可解码不等于逐词真人听辨；合成声线和字符拼读在索引中明确标记。 |
| 分片抽样解码 | 从真实分片抽取 40 条，含 5 条真人录音、3 条字符拼读，40/40 可解码；记录在本地 `dist/reports/audio-decode-sample.csv`。 | 解码成功只证明文件可播放，不能证明发音正确。 |

原始工作表和 ASR 辅助记录在 [qa/0.0.1](qa/0.0.1/README.md)；本地可直接打开 `dist/reports/qa-0.0.1/review-sample.csv` 与 `dist/reports/qa-0.0.1/audio-review-sample.csv`。有证据的词义修订见 [editorial/corrections.json](../editorial/corrections.json)。210／40 是项目抽样规模，不是发布协议强制的词数。数据清单中的 `release_status=data-verified` 仅表示程序检查通过，不表示全部词义与录音已人工审校。
