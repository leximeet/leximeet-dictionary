# LexiMeet Dictionary｜词遇开放词典

LexiMeet Dictionary 是独立的开源英汉词典项目，以 [open-dictionary](https://github.com/ahpxex/open-dictionary) 的学习词卡为基础，合并其他开放数据，向桌面端和浏览器插件提供同一套可验证的离线词包。

**0.0.1 正在改为核心版和完整版，尚未发布。** 现有构建包含 811,092 条词条、241,588 条义项，但本地三包候选属于旧方案：只有 436 条离线录音，**不符合新版逐词离线发音要求，不能作为正式 0.0.1 使用**。桌面端与插件端的原生接入由各自项目完成。

## 0.0.1 基于哪些项目

| 来源 | 在当前词包中的作用 |
| --- | --- |
| [open-dictionary v2.0](https://github.com/ahpxex/open-dictionary) | 84,212 条策展词卡：词性、义项、中文学习解释、例句和展示顺序；同版 audit 补英文原义、标签与 IPA。 |
| [Wiktionary / Wiktextract / Kaikki](https://kaikki.org/dictionary/) | 对主词源缺少的 34 个高频功能词，补 161 条独立英文义项。 |
| [ECDICT](https://github.com/skywind3000/ECDICT) | 中文和缺词回退、考试标签及历史词频；新增 726,880 条回退词条。 |
| [CMUdict](https://github.com/cmusphinx/cmudict) | 美式 ARPABET 音素；不冒充 IPA 或真人录音。 |
| [Open English WordNet](https://github.com/globalwordnet/english-wordnet) | 独立的概念和语义关系索引；目前不把同词头概念强贴到具体义项。 |
| [Wikimedia Commons](https://commons.wikimedia.org/) | 已取得 436 条有文件哈希、来源和署名的 OGG；新版所需的其余逐词录音尚待补齐。 |

词遇另为八个抽样词头提供可追溯的中文审校显示；原上游字段保留。来源版本、文件哈希和数据条款见 [来源与对比](docs/DICTIONARY_OVERVIEW.md)、[输入锁](sources.lock.json)及[数据许可](DATA-LICENSE.md)。

## 相比单一上游增加了什么

| 能力 | open-dictionary v2.0 | ECDICT | LexiMeet 0.0.1 |
| --- | --- | --- | --- |
| 词条范围 | 84,212 条策展词卡 | 770,611 行原始 CSV | 合并后 811,092 条词条 |
| 中文与义项 | 细分的学习者词义 | 词条级翻译 | 主词卡保留逐义结构；缺词另用 ECDICT 回退，避免假装翻译已逐义对齐 |
| 发音 | 部分 IPA 与音频线索 | 旧式音标字段 | 区分 IPA、ARPABET 与录音；目标是两个版本都逐词附可离线播放的音频，当前尚未达标 |
| 扩展数据 | 策展词卡 | 考试标签、频率 | 义项标签与词条考试标签分层，WordNet 概念独立；目标为核心版和完整版 |

优势在于**覆盖范围、来源边界和多端交付**，不代表 81 万词都经过人工审校，也不宣称每条释义都优于上游。详细计数、包大小及全量词条 Markdown 入口见 [来源与对比](docs/DICTIONARY_OVERVIEW.md)。

## 获取与后续计划

0.0.1 的目标是**核心版**（open-dictionary 全部 84,212 条完整词卡，再加有词频或考试标签依据的 33,690 条 ECDICT 缺词，共 117,902 条）和**完整版**（全部 811,092 条词条）。两个版本都须覆盖各自的逐词离线音频；不再给核心版设 50 MB 上限。插件和桌面端可内置核心版，安装后由用户手动下载完整版并验证、替换。完整包可以拆成多个下载文件，但仍是一个版本。音频来源、打包器和验收尚在建设，详见 [任务清单](docs/TASKS.md)及[消费契约](docs/CLIENT_CONTRACT.md)。

**计划中的 0.0.2** 将评估 [DictionaryByGPT4](https://github.com/Ceelog/DictionaryByGPT4) 的部分助记内容，以及 [qwerty-learner](https://github.com/RealKai42/qwerty-learner) 的词表归属信息。二者目前**没有导入 0.0.1**；先核对具体数据来源、可分发范围与事实质量，再做可选学习层，不覆盖基础词义。具体交接见 [任务清单](docs/TASKS.md)。

本仓库代码采用 [GPL-3.0](LICENSE)；词典数据与录音按各来源许可和署名分层处理，见 [DATA-LICENSE.md](DATA-LICENSE.md)。
