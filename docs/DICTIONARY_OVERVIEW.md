# LexiMeet 词典 0.0.1：来源、产物与全量词条总览

本页只统计本地 `build/v0.0.1-final/` 与 `dist/final/` 中已生成的候选；计数来自 `manifest.json`、`qa/quality-report.json` 和只读 SQLite，不把设计中尚未导入的数据算作贡献。这里的“词条”是有独立 `entry_id` 的记录，**不是** 81 万个已人工审校的不同英语单词；忽略大小写的查找键共 805,827 个。当前归档可用于词遇客户端的集成开发和隔离安装验证，正式自动下载仍受包内 `release_status=candidate-needs-human-review` 限制。

## 当前实际使用了哪些项目

| 项目与固定数据 | 实际写入 0.0.1 的内容 | 可核对的产物数量 | 边界 |
| --- | --- | ---: | --- |
| [open-dictionary](https://github.com/ahpxex/open-dictionary) v2.0 `distribution` | 主词卡的词性、策展义项、中文学习解释、例句、展示优先级、词形及部分 IPA | 84,212 策展词条；241,427 策展义项 | 仍保留上游写法与罕见义，不能把所有词义称为词遇独立审校；固定发行文件 SHA-256 |
| 同版 open-dictionary `audit`，源谱系是 Wiktionary/Wiktextract | 在词性组、词源组和义项数对齐后，补英文原义、义项标签/领域、IPA 及待核权的音频线索 | 84,173 / 84,212 词条结构对齐；53,121 条音频线索 | 与主词卡同源，**不是独立第二票**；39 条未对齐不猜配英文原义；线索不等于可再分发录音 |
| [Wiktextract](https://github.com/tatuylonen/wiktextract) / [Kaikki](https://kaikki.org/dictionary/) 固定逐词提取 | 对主来源缺失的冠词、连词词性补短英文原义及其原标签 | 34 个高频功能词；161 条独立义项 | 是 2026-09-02 Wiktionary dump 的另一快照，只补缺词性，不跨快照按词头强行对齐 |
| [ECDICT](https://github.com/skywind3000/ECDICT) `bc015ed2` | 宽覆盖的词条级中文/英文回退、原始考试标签、历史词频和旧式音标字段 | 原 CSV 770,611 行；新增 726,880 回退词条；768,739 词条有中文；14,942 词条有显式考试声称 | 中文回退**不自动对应某一个英文义项**；旧音标不称 IPA；原始译文可能过时或不准 |
| [CMUdict](https://github.com/cmusphinx/cmudict) `74790861` | 美式 ARPABET 音素和重音，独立于 IPA | 87,412 词条含 ARPABET | 不是英式读音、IPA 原文或真人录音 |
| [Open English WordNet](https://github.com/globalwordnet/english-wordnet) 2025 core | 独立 synset 和 lemma-sense 关系，供概念候选查询 | 107,519 synset；185,129 lemma-sense | 词头命中还没有证实与具体词卡义项同义，不将概念自动并入词义 |
| [Wikimedia Commons](https://commons.wikimedia.org/) 固定逐文件清单 | 可选带发音包的高频 OGG；逐文件保存作者、许可、来源页、字节数及 SHA-256 | 436 条离线录音 | 录音按需播放；其余词按用户点击查询和缓存；40 条样本听辨仍需独立完成 |
| [qwerty-learner](https://github.com/RealKai42/qwerty-learner)、[DictionaryByGPT4](https://github.com/Ceelog/DictionaryByGPT4)、[Aictionary](https://github.com/ahpxex/Aictionary) | 只用于词表组织、助记和客户端/音频架构参考 | **0 条内容导入** | 0.0.1 没有 qwerty 词表成员或 GPT4 助记长文，不能在功能介绍中写成已上线 |

数据文件和 Git 修订的完整哈希见 [SOURCE_LOCK.md](SOURCE_LOCK.md) 与仓库根目录 `sources.lock.json`；每层内容及音频署名见 [DATA-LICENSE.md](../DATA-LICENSE.md)。

## 与两个主要上游的实测对比

| 维度 | open-dictionary v2.0 | 当前 ECDICT CSV | LexiMeet 0.0.1 候选 | LexiMeet 的实际增量或限制 |
| --- | ---: | ---: | ---: | --- |
| 词条记录 | 84,212 | 770,611 行 | 811,092 | 合并后比任一单源覆盖更多；交集按构建清单为 43,731 个源词条匹配，不能把数量当质量评分 |
| 策展、可逐义项展示的词义 | 241,427 | CSV 没有同等义项树 | 241,427 主来源义项 + 161 条独立功能词义项 | 主词卡不降为单行翻译，并补主源筛掉的高频冠词/连词；绝大多数 ECDICT-only 词仍无逐义项拆分 |
| 中文覆盖 | 学习者解释集中在策展词卡 | 768,739 行有中文 `translation` | 768,739 词条有 ECDICT 词条级中文，策展词卡另有逐义中文 | 常见词可先展示策展释义，缺词回退；**不能**把 ECDICT 中文自动挂到英文义项下 |
| 考试、领域和用法 | 有义项标签、领域，无中国考试词表体系 | 14,942 行有显式考试 `tag` | 考试为词条级；领域/用法为义项级 | 来源与作用域分开；qwerty 词表成员目前尚未导入 |
| 读音 | 有部分 IPA、音频候选线索 | 218,065 行有旧式 `phonetic`，CSV 无录音 | 26,483 词条含 IPA；87,412 含 ARPABET；可选 436 条离线 OGG | 记法、来源及地区显式区分；离线音频目前只覆盖少量高频词 |
| 语义关系 | 主词卡没有本项目的独立 WordNet 表 | 无相应 synset 网络 | 107,519 个 WordNet synset 独立查询 | 供未来语义功能使用；未完成逐义项人工映射 |
| 面向词遇多端的交付 | 上游自己的 JSONL/SQLite | 原始 CSV | 5,000 词核心包、完整无音频包、完整带音频包；同一稳定 `entry_id` | 固定 SHA-256、只读安装和来源清单；桌面/插件原生接入尚未测试 |

这张表比较的是**当前锁定文件与本地构建结果**，不代表对上游项目最新版、词义准确率或查询速度做了同条件评测。LexiMeet 的优势是为词遇多端建立一个有统一字段、来源、作用域和可验证分发格式的组合词典；它没有宣称每一个源词条都优于上游。

## 词条详情表与安装文件

| 本地文件 | 内容 | 当前大小或校验 |
| --- | --- | --- |
| [全量词条与释义 Markdown](../dist/final/leximeet-dictionary-0.0.1-details.md) | 811,092 行词条，逐义项英文原义/中文短释/学习解释，以及独立的 ECDICT 词条级中英文回退；一行一个 `entry_id` | 193,973,684 bytes；SHA-256 `97d5451ae5622b9ac2545d86bf2869f81fbfc98925fc38c967dabc308e51abb9` |
| `dist/final/leximeet-dictionary-0.0.1-core.tar.gz` | 插件可导入的 5,000 词离线核心 | 17,963,726 bytes；外层哈希见 `release-candidate.json` |
| `dist/final/leximeet-dictionary-0.0.1-no-audio.tar.gz` | 完整 SQLite/JSONL，不附 OGG | 433,452,931 bytes |
| `dist/final/leximeet-dictionary-0.0.1-with-audio.tar.gz` | 相同完整词典，加 436 条录音 | 437,918,827 bytes |

Markdown 是供维护者浏览和检索的**附加导出件**，不是客户端运行时数据库；它约 194 MB，不提交到 Git 或塞入上述三个压缩包。可以从已验证的 SQLite 重建：

~~~sh
python3 tools/export_markdown.py \
  --db build/v0.0.1-final/dictionary.sqlite \
  --out dist/final/leximeet-dictionary-0.0.1-details.md
~~~

导出器逐行写入，不一次加载全部词条，生成 `.stats.json` 并核对导出行数。真正安装时按 [CLIENT_CONTRACT.md](CLIENT_CONTRACT.md) 验证包清单、所有文件哈希和 schema 后原子切换。当前字节哈希仅适用这份本地候选；若数据修正或发布状态改变，必须重建此表与三归档。
