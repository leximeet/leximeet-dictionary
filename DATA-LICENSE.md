# 数据来源、许可与权利通知

仓库代码采用 [GPL-3.0](LICENSE)。词包汇集不同来源，使用方应保留随包的 `DATA-LICENSE.md`、`notices/` 和音频清单中的逐文件署名。

| 数据 | 来源与适用说明 |
| --- | --- |
| 主词卡、同版 audit 与词遇中文审校 | [open-dictionary v2.0](https://github.com/ahpxex/open-dictionary)、English Wiktionary 贡献者、词遇维护者；按 [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) 提供，并保留 [原项目声明](notices/OPEN-DICTIONARY-DATA-LICENSE.md)。词遇审校文件逐条保存旧值与核对页面。 |
| 高频功能词补充 | [Wiktionary / Kaikki / Wiktextract](https://kaikki.org/dictionary/rawdata.html)；按 CC BY-SA 4.0 署名。固定的 34 个逐词文件哈希和定位见 `sources/function-words.jsonl`。 |
| 中文及缺词回退 | [ECDICT](https://github.com/skywind3000/ECDICT) 与贡献者；保留 [MIT 文本](notices/ECDICT-LICENSE.txt)和来源说明。 |
| 概念与音素 | [Open English WordNet / Princeton WordNet](notices/OPEN-ENGLISH-WORDNET-LICENSE.md)、[CMUdict](notices/CMUDICT-LICENSE.txt)；保留相应许可与声明。 |
| 离线录音 | Wikimedia Commons；每个文件的作者、许可链接、来源页和 SHA-256 均在 `audio/manifest.json`，按该文件的实际许可署名。 |

感谢以上项目与贡献者。ECDICT 历史资料的逐字段权利链并非全部可独立核实；本项目按仓库许可保留署名并提供处理入口。如认为某个词条、字段或录音侵犯权利，请将内容位置与依据发至 [13622993145@163.com](mailto:13622993145@163.com)。维护者核查后会移除或替换相应使用，并重建后续词包。

DictionaryByGPT4 与 qwerty-learner 目前仅列入 0.0.2 计划，**没有内容进入 0.0.1 词包**。
