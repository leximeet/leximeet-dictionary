# 数据、音频与署名说明（0.0.1 候选）

本仓库的 `LICENSE` 是构建代码的 GPL-3.0 许可；不能把它当成整个混合词包的统一数据许可。0.0.1 词包是多来源汇编，使用方须按具体字段及素材履行相应条款。当前构建清单标记为 **candidate-needs-license-and-human-review**，尚不表示已通过公开发行审核。

“仓库开源、README 致谢”解决的是来源披露，不自动取得第三方文本、录音的再分发权。ECDICT 自身附 MIT 文本；但其 [README](https://github.com/skywind3000/ECDICT#简介) 说明早期释义来自 EDictAZ 和词表，音标也曾从其他资料收集。现有证据无法逐字段说明这些原始材料是否由权利人允许 ECDICT 再授权。此处只是权利链未核实，不是认定 ECDICT 侵权。若能找到各原始材料的适用许可与来源记录，并满足条款，就无须逐一联系作者；若仍不清楚，可向维护者核实来源与授权，或将相应字段改为用户本地导入。完整候选可在本地研究，但公开数据 Release 继续等待核权。

| 内容 | 来源和署名 | 条款与依据 |
| --- | --- | --- |
| 英语义项、中文学习解释、双语例句、标签、IPA 等策展内容 | English Wiktionary 贡献者；Wiktextract/Kaikki；ahpxex/open-dictionary v2.0 | open-dictionary 将其发布数据按 [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) 授权；保留 [原项目数据声明](notices/OPEN-DICTIONARY-DATA-LICENSE.md)。此处英语原义和审计字段来自同谱系，不能当独立证据。 |
| ECDICT 词条级中文/英文回退、考试声称、历史频率字段 | skywind3000/ECDICT、Linwei 与历史贡献者 | 仓库附 [MIT 文本](notices/ECDICT-LICENSE.txt)。README 说明词义及音标曾来自 EDictAZ、其他词表和抓取资料；各字段的原始权利尚未充分核验。因此公开数据包的 ECDICT 层仍需明确授权结论。 |
| Open English WordNet 2025 概念数据 | Open English WordNet team 与 Princeton WordNet | [CC BY 4.0 与 Princeton WordNet 原条款](notices/OPEN-ENGLISH-WORDNET-LICENSE.md)、[Princeton 原文](notices/PRINCETON-WORDNET-LICENSE.txt)；两方都要署名。 |
| CMUdict ARPAbet | Carnegie Mellon University 与贡献者 | [CMUdict 许可证及完整免责声明](notices/CMUDICT-LICENSE.txt)；二进制再分发需在文档或随附材料保留。 |
| 离线 Commons 录音 | 每个 `audio/manifest.json` 记录的作者和文件页 | 逐文件的 CC0/CC BY/CC BY-SA 许可及作者署名，不受词典主包的统一数据许可覆盖。自动元数据审查不代替人工抽查和权利判断。 |

构建器不导入 qwerty-learner 第三方词表、有道录音或 DictionaryByGPT4 长文。WordNet `wordnet_lemmas` 是独立候选概念，尚未与 open-dictionary 某条义项确证对齐。Wiktionary 历史引文不进入当前规范词包。按需查询 Commons 文件时，也必须显示该文件元数据中的作者、许可、文件页与来源；缓存不会改变其授权义务。

若后续确认 ECDICT 的某些字段不能公开再分发，应在发布配置中剔除这些字段或改为用户本地导入，并重建/复核词包。数据工件的公开下载和 GitHub Release 应在此项与分层词义样本验收完成后进行。
