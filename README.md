# LexiMeet Dictionary｜词遇共享词典

面向词遇浏览器插件、桌面端及后续客户端的离线词典加工项目。目标是从可追溯的开放来源生成**同一语义契约、按客户端能力分档的词典包**：词卡既能快速显示常用词的可靠释义与音标，也能展开词形、义项、例句和词义关系。

> 0.0.1 状态：构建器、无音频词包、WordNet 概念表、Commons 音频核权/缓存工具和测试已实现，本地全量构建与自动校验已通过。**当前产物仍是发布候选，尚未接入插件或桌面端，也尚未通过 ECDICT 字段权利和人工语义抽检门禁。**[构建与使用](docs/BUILD.md)说明实际命令，[客户端契约](docs/CLIENT_CONTRACT.md)说明接入规则，[数据许可](DATA-LICENSE.md)说明发行边界。

无音频版的在线真人录音、系统朗读，以及微软和有道服务的费用与缓存许可比较，见[音频提供方与按需缓存](docs/AUDIO_PROVIDERS.md)。

## 为什么不直接把五份词典拼成一个 JSON

来源分工不同，同一个词的中文释义、英语义项、发音、词义关系和考试标签也不能按词形直接覆盖：

| 层次 | 优先来源 | 用途与边界 |
| --- | --- | --- |
| 宽覆盖英汉底座、词形和现有考试标签 | [ECDICT](upstream/ecdict) | 本地 CSV 实测 770,611 行；中文释义覆盖广，但音标是混合旧记法，不能当作规范 IPA，也没有可用的独立音频。 |
| 可溯源的英语义项、IPA、例句、词形 | [Wiktextract](upstream/wiktextract) 处理的 Wiktionary 快照 | 同时固定**工具 commit 与源 dump 日期/哈希**；只选 English 词条。原始数据的许可不等于工具代码许可。 |
| 学习者向双语解释与义项优先级 | [open-dictionary](upstream/open-dictionary) | 现有 84,212 词条的发布说明与 JSONL/SQLite 契约可供参考或再加工；它本身派生自 Wiktionary/Wiktextract，不能当作独立证据投票。 |
| 词义网络 | [Open English WordNet](upstream/english-wordnet) | 同义词集、上位词、反义词等关系；只在义项可对齐时建立关系，不能凭词形合并。 |
| 美式发音补充与校验 | [CMUdict](upstream/cmudict) | ARPAbet 音素和重音，保留原记法；转换出的 IPA 需要单独标记为机器转换，不含真人录音。 |

这不是声称存在一个同时覆盖 77 万词、每词都有完整义项/双语例句/英美真人录音的现成词典。**覆盖率、展示质量、来源许可和可分发性需要分别测量。**详细实测与取舍见 [来源审计](docs/SOURCES.md)，端到端规则见 [设计基线](docs/DESIGN.md)，数据/仓库修订见 [版本锁定](docs/SOURCE_LOCK.md) 与 [机器可读锁文件](sources.lock.json)，实施顺序与验收见 [任务文档](docs/TASKS.md)，产物契约见 [格式设计](docs/FORMAT.md)。

## 上游引用

本仓库的 upstream/ 是 Git 子模块，只保存上游 Git commit 指针；不把源仓库历史复制进主仓库。当前固定版本：

| 路径 | Git commit | 作用 |
| --- | --- | --- |
| upstream/ecdict | bc015ed2e24a7abef49fc6dbbb7fe32c1dadaf8b | 英汉底座 |
| upstream/wiktextract | 1a05e46f9efbccda6a2b2f8e21b30a9c0c46513a | Wiktionary 提取工具 |
| upstream/english-wordnet | bff3181fe5c810dcd157cba0eed60322a6e0aaed | 词义网络仓库；正式数据版次仍需独立固定 |
| upstream/open-dictionary | 647df7a33e211a03014b6647f7832b0b183911b3 | 学习者词典加工管线；Release 数据仍需独立固定 |
| upstream/cmudict | 74790861f652b15e4ac49015a90074ad62a27690 | 美式音素词典 |

~~~sh
git clone https://github.com/leximeet/leximeet-dictionary.git
cd leximeet-dictionary
git submodule update --init
git submodule status
~~~

实际构建命令见[构建与使用](docs/BUILD.md)。`sources.lock.json` 已为 v2.0 的 distribution/audit、ECDICT CSV、CMUdict 和 WordNet 2025 ZIP 固定字节数与 SHA-256；构建器在处理前逐文件验证。不要使用浮动的 latest URL 作为可复现构建输入。

### 为什么暂不把所有参考项目设为子模块

- DictionaryByGPT4：本地 JSONL 实测 8,714 行、按忽略大小写去重后 7,954 个词头，主要是 AI 长文讲解。适合作为经人工核查的可选学习卡片，不适合充当词义或词源事实的主来源；考试词表、生成内容和再分发边界仍需逐项核对。
- qwerty-learner：本地有 380 个 JSON 词表，含不错的英美音标字段，但其 README 将词表归于 kajweb、语音归于有道；kajweb 又自述从词典 App 抓取。程序的 GPL-3.0 许可证不能自动授予这些第三方词表、译文和音频的再分发权。可以借鉴词表加工流程并独立实现，输入仍需有可核查的授权。具体使用边界见[来源审计第 5 节](docs/SOURCES.md#5-qwerty-复用方式与发布边界)。
- open-dict-data/ipa-dict：可研究美国 IPA 补缺，但美式数据源于 CMUdict 转换，英式数据另有 GPL-3.0 上游；当前优先保留更原始的 CMUdict 与可溯源的 Wiktionary IPA。
- rspeer/wordfreq：可研究频率排序，但其 README 说明语料大致停在 2021 年；不能用它代替现时词频，也要核对数据许可。
- MuJing、Read Frog 等应用是消费端/产品参考，不是本项目应重复引入的独立底层词典。MuJing 的本地查询直接使用 ecdict.db；Read Frog 的“Dictionary”是翻译/AI 动作入口。

这些候选会留在来源审计中；只有版本、字段价值、原始数据许可、署名和产物测试都明确后才升级为加工输入。

## 发音与音频

**“音标”是文本标注，“发音”也可能指可播放的录音或合成语音，两者单独存储。** ECDICT 的 phonetic 不能直接显示为标准 IPA：本地 abandon 是 <code>ә'bændәn</code>，其中 <code>ә</code> 为西里尔字符 U+04D9；它还大量使用 ASCII 撇号与冒号。ECDICT 的 audio 列在这份 CSV 中全部为空。

建议词卡的展示顺序：

1. 有来源、地区和词性标记的 Wiktionary/Wiktextract IPA；学习者常用词可优先采用 open-dictionary 已策展的 US/UK IPA，但须保留其 Wiktionary 衍生谱系，不能算独立复核。
2. 美式缺口用 CMUdict ARPAbet 补充；若转换为 IPA，应标注转换规则、原始音素和较低置信级。不要把一个拼写的多个读音强行分配给未经核实的义项。
3. ECDICT 原始 phonetic 仅留作诊断/兼容字段，未经验证的转换结果不进入主词卡。

真人音频仅在逐文件确认许可、作者署名、来源页、媒体类型和 SHA-256 后进入**独立音频包**。Wiktextract 的 sounds 可包含 Commons 文件名、ogg_url、mp3_url 和 audio-ipa，但音频的许可要在 Commons 文件页逐个核对；一个 IPA 项与另一个音频项也不能自动认定匹配。无可分发录音时，客户端可提供明确标为“合成语音”的系统 TTS 备选。词条 JSON 只引用 audio_id，不嵌入音频二进制或未经审查的第三方直链。

## 加工与发布路线

~~~text
固定 Git 子模块 + 固定数据快照/校验和
        │
        ▼
逐源导入与原样留存（source_ref、原始字段、许可证）
        │
        ▼
词头规范化 → 词形/同形异义分组 → 义项对齐 → 字段级择优
        │
        ▼
发音/音频审查、标签清洗、冲突与人工抽样
        │
        ▼
规范 JSONL + manifest ─┬─ 桌面 SQLite 检索包
                        └─ 插件按需分片/分级离线包
~~~

规范层使用 **UTF-8 JSONL（一行一词条）+ manifest**，便于流式加工、重建和按词条比对；不维护一个几百 MB 的单体 JSON 数组。桌面端可使用有索引的 SQLite 查询包，浏览器插件使用小型核心词包和可下载的扩展分片，按需安装与校验。客户端共享字段含义和版本规则，不要求共享同一个物理文件。浏览器的个人单词本与只读公共词典分开保存；未来连接桌面端时只同步同一本用户单词本及其稳定 ID，不把词典更新误当作用户编辑。

第一轮加工前至少完成：

1. 固定 Wiktionary/Kaikki English 数据快照、open-dictionary Release、WordNet 正式数据版次及各文件 SHA-256。
2. 输出字段级来源与许可证清单，决定可发布的 ECDICT 基础包和含 CC BY-SA 内容的增强包边界。
3. 对同形异义、英美/词性多读音、词义关系、例句、考试标签做抽样人工复核；计算每字段覆盖率、冲突率、词包大小和端上查询耗时。
4. 在隔离浏览器配置与桌面测试数据中验证安装、离线查询、增量升级、回滚、损坏包拒绝和连接桌面后的单词本一致性。

## 许可与分发

本仓库目前的 [LICENSE](LICENSE) 为 **GPL-3.0，约束本仓库自身代码**。上游 Git 子模块各自保留许可证；它不把所有词典数据改授为 GPL-3.0。ECDICT 仓库标示 MIT，但 README 也叙述了多个历史资料来源；正式发布前保留来源与署名审计。Wiktextract **工具代码**为 MIT，Wiktionary **内容**按其自身许可处理。open-dictionary 将其发布的数据工件声明为 CC BY-SA 4.0，Open English WordNet 为 CC BY 4.0 并要求保留相关署名，CMUdict 有自身许可与声明。融合产物须逐字段保留来源，按实际纳入的数据履行署名与相同方式共享义务；不能仅写一句“开源”就整体打包。

仓库不收录尚未核验的 Wiktionary dump、Release 文件、qwerty 词表、有道录音或 Commons 音频。生成词包发布之前必须提供独立的数据许可说明、机器可读来源清单、原始快照哈希及可复现构建记录。当前桌面端只包含 ECDICT 词包；本项目文档不代表已经完成桌面或插件集成。

## 致谢与来源

感谢 [ECDICT](https://github.com/skywind3000/ECDICT)、[Wiktionary 贡献者](https://en.wiktionary.org/)、[Wiktextract/Kaikki](https://github.com/tatuylonen/wiktextract)、[Open English WordNet 与 Princeton WordNet](https://github.com/globalwordnet/english-wordnet)、[open-dictionary](https://github.com/ahpxex/open-dictionary)、[CMUdict](https://github.com/cmusphinx/cmudict) 的贡献者；感谢 [DictionaryByGPT4](https://github.com/Ceelog/DictionaryByGPT4)、[qwerty-learner](https://github.com/RealKai42/qwerty-learner)、[MuJing](https://github.com/tangshimin/MuJing) 和 [Read Frog](https://github.com/mengxi-ream/read-frog) 提供学习体验与数据组织方面的参考。各项目的代码、数据和媒体许可仍以其原始声明为准。
