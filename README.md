<div align="center">

# LexiMeet Dictionary · 词遇开放词典

**一份可核验、可离线发音、供桌面端与浏览器插件共用的英汉词典。**

[词包接入](docs/CLIENT_CONTRACT.md) · [从源码构建](docs/BUILD.md) · [数据来源](DATA-LICENSE.md) · [更新记录](CHANGELOG.md)

</div>

词遇以 [open-dictionary v2.0](https://github.com/ahpxex/open-dictionary) 的完整学习词卡为主体，补入 ECDICT 的中文与缺词、Wiktionary 的少量功能词义项、CMUdict 音素和独立的 WordNet 概念索引。`0.0.1` 提供两个版本：核心词都有离线音频；完整版增加全部词条，分片下载并复用核心音频。

| 版本 | 词条范围 | 使用场景 |
| --- | ---: | --- |
| **核心版 `core`** | 117,902 条：全部 84,212 条 open-dictionary 词卡 + 33,690 条有频率或考试依据的补充词；117,902 条离线音频 | 桌面端、插件端内置 |
| **完整版 `full`** | 811,092 条词条；共享核心词的 117,902 条离线音频 | 用户主动下载，校验后替换 |

数字来自当前固定输入，最终以同版 `release.json` 为准。两版词卡都保留完整内容；**非核心词在 0.0.1 没有随包音频**，端侧可按需使用在线朗读。核心音频包含 436 条逐文件署名的 Commons 真人录音和标明来源的本地合成录音；合成音色与真人录音不同。尚未发布的本地构建不能冒充 GitHub Release。

## 为什么做这份词典

| 能力 | open-dictionary v2.0 | ECDICT | LexiMeet 0.0.1 |
| --- | --- | --- | --- |
| 词条 | 84,212 条策展词卡 | 770,611 行原始 CSV | 合并后 811,092 条；核心版完整收录主词库 |
| 释义 | 学习者向逐义词卡 | 词条级中文/英文回退 | 主词卡保留逐义结构，缺词明确标记为词条级回退 |
| 标签 | 义项领域与用法 | 词条考试标签与历史频率 | 保留各自作用域，避免把考试标签误贴到某个义项 |
| 发音 | IPA 与部分在线音频线索 | 旧式音标字段 | IPA/ARPABET 分开记录；核心词随包离线音频 |
| 交付 | 上游数据格式 | CSV | JSONL、分片 SQLite、共享音频分片与逐文件 SHA-256 |

优势是**完整词卡、广覆盖与可校验交付的组合**。ECDICT 缺词多数没有人工整理的逐义解释，WordNet 概念也尚未与具体义项自动对齐；词遇不把这些内容伪装成已审校词义。详细来源和数量见 [词典总览](docs/DICTIONARY_OVERVIEW.md)。

## 接入与使用

消费端从固定版本的 `release.json` 读取 `core.assets` 或 `full.assets`。下载文件先按字节数和 SHA-256 校验，再按 `sqlite.parts` 拼接完整版 SQLite；`.pack` 内每段 Ogg 按索引的 `offset`、`bytes` 读取。完整版引用核心音频分片，下载中断时继续使用已安装的核心版。用户笔记、单词本与自定义标签存于词包之外。

```bash
# 校验发布目录中的核心版和完整版；--deep 会逐词检查索引、音频字节和 SQLite。
python3 -m leximeet_dictionary release-verify dist/v0.0.1 --edition core --deep
python3 -m leximeet_dictionary release-verify dist/v0.0.1 --edition full --deep

# 校验分片并拼接查询库；发音按音频索引读取。
python3 -m leximeet_dictionary release-assemble dist/v0.0.1 --out /tmp/leximeet-dictionary.sqlite
python3 -m leximeet_dictionary lookup --db /tmp/leximeet-dictionary.sqlite bank
```

从零生成固定数据、续跑音频和分片发包见 [构建说明](docs/BUILD.md)；应用的下载与原子替换步骤见 [客户端协议](docs/CLIENT_CONTRACT.md)。当前仓库提供可消费的数据协议和参考校验器，桌面端与插件端的原生接入由各自项目完成。

## 来源与致谢

| 项目 | 对词遇的贡献 |
| --- | --- |
| [open-dictionary](https://github.com/ahpxex/open-dictionary) 与 English Wiktionary 贡献者 | 主词卡、例句、词义与同版审计信息 |
| [Wiktextract / Kaikki](https://kaikki.org/dictionary/) | 主词库缺少的高频功能词义项 |
| [ECDICT](https://github.com/skywind3000/ECDICT) | 中文回退、缺词、考试标签与历史词频 |
| [CMUdict](https://github.com/cmusphinx/cmudict) · [Open English WordNet](https://github.com/globalwordnet/english-wordnet) | 美式音素与独立概念网络 |
| [Wikimedia Commons](https://commons.wikimedia.org/) · [eSpeak NG](https://github.com/espeak-ng/espeak-ng) · [Opus](https://opus-codec.org/) | 有署名的真人录音、合成发音与音频编码 |

感谢这些项目、词典编纂者、录音作者和维护者。具体版本、逐层许可、真人录音署名及权利处理方式见 [DATA-LICENSE.md](DATA-LICENSE.md) 和随包 `notice-*` 文件。仓库代码使用 [GPL-3.0](LICENSE)；不同数据和音频保留各自的来源与许可。若发现内容侵权或需要修订，请联系作者并说明具体词条或文件，维护者核查后移除或替换。

**0.0.2 计划**：提供全部词条的离线音频版本，并评估 [DictionaryByGPT4](https://github.com/Ceelog/DictionaryByGPT4) 的部分助记内容与 [qwerty-learner](https://github.com/RealKai42/qwerty-learner) 的词表归属。二者未进入 0.0.1；补充层不会覆盖基础词义。参与修订见 [CONTRIBUTING.md](CONTRIBUTING.md)。
