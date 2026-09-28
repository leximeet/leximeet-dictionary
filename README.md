# LexiMeet Dictionary｜词遇开放词典

LexiMeet Dictionary 是独立的开源英汉词典项目，以 [open-dictionary](https://github.com/ahpxex/open-dictionary) 的学习词卡为基础，合并其他开放数据，向桌面端和浏览器插件提供同一套可验证的离线词包。

**0.0.1 状态：本地候选已可用于接入开发，尚未发布正式 Release。** 当前包有 811,092 条词条和 241,588 条义项。三个安装包已在本地构建并验证；发布状态仍是 `candidate-needs-human-review`。桌面端与插件端的原生接入由各自项目完成，本仓库不把它们的测试当作词典构建结果。

## 0.0.1 基于哪些项目

| 来源 | 在当前词包中的作用 |
| --- | --- |
| [open-dictionary v2.0](https://github.com/ahpxex/open-dictionary) | 84,212 条策展词卡：词性、义项、中文学习解释、例句和展示顺序；同版 audit 补英文原义、标签与 IPA。 |
| [Wiktionary / Wiktextract / Kaikki](https://kaikki.org/dictionary/) | 对主词源缺少的 34 个高频功能词，补 161 条独立英文义项。 |
| [ECDICT](https://github.com/skywind3000/ECDICT) | 中文和缺词回退、考试标签及历史词频；新增 726,880 条回退词条。 |
| [CMUdict](https://github.com/cmusphinx/cmudict) | 美式 ARPABET 音素；不冒充 IPA 或真人录音。 |
| [Open English WordNet](https://github.com/globalwordnet/english-wordnet) | 独立的概念和语义关系索引；目前不把同词头概念强贴到具体义项。 |
| [Wikimedia Commons](https://commons.wikimedia.org/) | 可选带发音包中的 436 条有文件哈希、来源和署名的高频 OGG。 |

词遇另为八个抽样词头提供可追溯的中文审校显示；原上游字段保留。来源版本、文件哈希和数据条款见 [来源与对比](docs/DICTIONARY_OVERVIEW.md)、[输入锁](sources.lock.json)及[数据许可](DATA-LICENSE.md)。

## 相比单一上游增加了什么

| 能力 | open-dictionary v2.0 | ECDICT | LexiMeet 0.0.1 |
| --- | --- | --- | --- |
| 词条范围 | 84,212 条策展词卡 | 770,611 行原始 CSV | 合并后 811,092 条词条 |
| 中文与义项 | 细分的学习者词义 | 词条级翻译 | 主词卡保留逐义结构；缺词另用 ECDICT 回退，避免假装翻译已逐义对齐 |
| 发音 | 部分 IPA 与音频线索 | 旧式音标字段 | 区分 IPA、ARPABET 与录音；可选高频离线音频，其余按需获取 |
| 扩展数据 | 策展词卡 | 考试标签、频率 | 义项标签与词条考试标签分层，WordNet 概念独立，三种可校验安装包 |

优势在于**覆盖范围、来源边界和多端交付**，不代表 81 万词都经过人工审校，也不宣称每条释义都优于上游。详细计数、包大小及全量词条 Markdown 入口见 [来源与对比](docs/DICTIONARY_OVERVIEW.md)。

## 获取与后续计划

0.0.1 提供 5,000 词核心包、完整无音频包、完整带发音包。开发时按 [构建说明](docs/BUILD.md)生成；未来客户端应下载固定版本的 Release 资产并校验 SHA-256，不将本仓库作为运行时子模块。[消费契约](docs/CLIENT_CONTRACT.md)说明查询和安装规则。

**计划中的 0.0.2** 将评估 [DictionaryByGPT4](https://github.com/Ceelog/DictionaryByGPT4) 的部分助记内容，以及 [qwerty-learner](https://github.com/RealKai42/qwerty-learner) 的词表归属信息。二者目前**没有导入 0.0.1**；先核对具体数据来源、可分发范围与事实质量，再做可选学习层，不覆盖基础词义。具体交接见 [任务清单](docs/TASKS.md)。

本仓库代码采用 [GPL-3.0](LICENSE)；词典数据与录音按各来源许可和署名分层处理，见 [DATA-LICENSE.md](DATA-LICENSE.md)。
