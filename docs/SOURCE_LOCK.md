# 固定输入

0.0.3 按 [package-sources.lock.json](../package-sources.lock.json) 锁定官方 0.0.2 Release 清单、官方 0.0.1 全量 JSONL、功能词和压缩实现。构建时核对输入文件的大小与 SHA-256，不重新访问浮动上游，也不重新合成核心录音。lite 名单由固定规则和完整下载预算产生；最终选词报告和逐文件摘要见新词包的 `selection.json`、`release.json`。构建与自动发布见[构建说明](BUILD.md)。

## 早期版本的数据底座

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

构建器在读入前拒绝哈希不匹配；数据底座的输入、输出哈希和生成 commit 见 `build/base/manifest.json`，0.0.1 正式发布资产哈希以 [GitHub Release](https://github.com/leximeet/leximeet-dictionary/releases/tag/v0.0.1) 的 `release.json` 为准。DictionaryByGPT4 和 qwerty-learner 不是 0.0.1 输入；0.0.2 的固定输入和官方 0.0.1 Release 清单哈希见 [learning-sources.lock.json](../learning-sources.lock.json)，字段映射见[设计文档](DESIGN_0.0.2.md)。
