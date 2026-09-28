# 数据、音频与署名说明（0.0.1 候选）

本仓库的 `LICENSE` 是构建代码的 GPL-3.0 许可；不能把它当成整个混合词包的统一数据许可。0.0.1 词包是多来源汇编，使用方须按具体字段及素材履行相应条款。当前本地候选清单标记为 **candidate-needs-human-review**，表示自动构建与校验通过，但人工词义、录音署名及真实客户端验收尚未完成。

项目维护者决定：首版 ECDICT 数据保留原仓库、MIT 文本和贡献者署名，不把逐字段追溯历史资料设为单独发布门禁。[ECDICT README](https://github.com/skywind3000/ECDICT#简介)提到 EDictAZ、其他词表和收集的音标，因此这项决定是项目的使用与响应策略，**不表示已证实所有第三方字段都可由 ECDICT 再授权**。README 致谢本身也不取代其他来源明确要求的许可文本、相同方式共享或逐文件媒体署名。

若权利人认为某个词条、字段或录音不应在词遇词包中使用，请发邮件至 [13622993145@163.com](mailto:13622993145@163.com)，提供内容定位、权利说明与联系方法。维护者会核查来源并移除或替换相应使用，重建后续词包；若涉及可控的已发布资产，按实际情况撤回或更正。已被第三方下载的历史副本无法由一次更新自动收回。

| 内容 | 来源和署名 | 条款与依据 |
| --- | --- | --- |
| 英语义项、中文学习解释、双语例句、标签、IPA 等策展内容 | English Wiktionary 贡献者；Wiktextract/Kaikki；ahpxex/open-dictionary v2.0 | open-dictionary 将其发布数据按 [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) 授权；保留 [原项目数据声明](notices/OPEN-DICTIONARY-DATA-LICENSE.md)。此处英语原义和审计字段来自同谱系，不能当独立证据。 |
| 高频功能词独立英文义项 | English Wiktionary 贡献者；Tatu Ylonen 的 [Kaikki/Wiktextract](https://kaikki.org/dictionary/rawdata.html) | 从 2026-09-02 Wiktionary dump 的 2026-09-25 提取结果中，仅抽取 34 个词的 article/conj 定义与义项标签，保留每词原始 JSONL URL、字节哈希和位置；按 [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) 署名及相同方式共享。未复制历史引文/例句，也未与 v2.0 的义项跨快照自动对齐。 |
| ECDICT 词条级中文/英文回退、考试声称、历史频率字段 | skywind3000/ECDICT、Linwei 与历史贡献者 | 保留仓库的 [MIT 文本](notices/ECDICT-LICENSE.txt)、来源和上述权利通知入口；历史资料来源存在未逐字段追溯之处，收到具体主张时核查并移除或替换。 |
| 词遇 0.0.1 审校层 | LexiMeet 维护者；逐条列出外部核对页面 | `editorial/corrections.json` 与词条内 `editorial` 记录审校文字、旧值、目标 ID 和依据；这层中文由词遇独立撰写，按 [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) 提供。外部页面是事实核对依据，不把其受版权保护的释义原文复制进词包。 |
| Open English WordNet 2025 概念数据 | Open English WordNet team 与 Princeton WordNet | [CC BY 4.0 与 Princeton WordNet 原条款](notices/OPEN-ENGLISH-WORDNET-LICENSE.md)、[Princeton 原文](notices/PRINCETON-WORDNET-LICENSE.txt)；两方都要署名。 |
| CMUdict ARPAbet | Carnegie Mellon University 与贡献者 | [CMUdict 许可证及完整免责声明](notices/CMUDICT-LICENSE.txt)；二进制再分发需在文档或随附材料保留。 |
| 离线 Commons 录音 | 每个 `audio/manifest.json` 记录的作者和文件页 | 逐文件的 CC0/CC BY/CC BY-SA 许可及作者署名，不受词典主包的统一数据许可覆盖。0.0.1 固定清单只保留 436 条作者字段明确的录音，18 条“推定作者”线索从离线包排除；自动元数据审查不代替人工抽查和权利判断。 |

构建器不导入 qwerty-learner 第三方词表、有道录音或 DictionaryByGPT4 长文。WordNet `wordnet_lemmas` 是独立候选概念，尚未与 open-dictionary 某条义项确证对齐。Wiktionary 历史引文不进入当前规范词包。按需查询 Commons 文件时，也必须显示该文件元数据中的作者、许可、文件页与来源；缓存不会改变其授权义务。

若后续确认某些 ECDICT 字段不能使用，应从构建输入或发布配置剔除，并重建/复核词包。0.0.1 正式发布仍须完成分层词义样本与音频听辨/署名抽查；桌面端和插件端的原生集成验收由各消费项目接入时进行。维护者将自行推送代码和决定 Release 发布时间。
