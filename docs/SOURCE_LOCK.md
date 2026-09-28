# 固定输入

构建时以仓库根目录 [sources.lock.json](../sources.lock.json) 的文件大小和 SHA-256 为准，而不是跟随上游默认分支。Git 子模块固定 ECDICT、CMUdict 等源码版本；open-dictionary v2.0 的 `distribution` 与 `audit`、Open English WordNet 2025 ZIP 是另外锁定的实际数据文件。

| 来源 | 0.0.1 固定范围 |
| --- | --- |
| open-dictionary | v2.0 `distribution.jsonl.gz` 与同版 `audit.jsonl.gz` |
| Wiktionary / Kaikki | `sources/function-words.jsonl`，34 词、161 条英文义项 |
| ECDICT | Git 子模块 `bc015ed2` 的 `ecdict.csv` |
| CMUdict | Git 子模块 `74790861` 的 `cmudict.dict` |
| Open English WordNet | 2025 JSON ZIP |
| 词遇审校 | `editorial/corrections.json`，SHA-256 记在产物 `manifest.json` |
| 离线录音 | `audio.lock.json`，每个 Commons 文件另有作者、许可和内容哈希 |

构建器在读入前拒绝哈希不匹配；最终产物的所有输入、输出哈希和生成 commit 见 `build/v0.0.1-final/manifest.json`。DictionaryByGPT4 和 qwerty-learner 是 0.0.2 的待评估来源，目前不是 0.0.1 输入。
