# 上游词典审计与取舍

本页记录 2026-09-28 的本地核查与上游官方说明。**本地实测**仅适用于下列 commit 和文件；**上游声称**不等于本项目重新测量；**计划**不代表已有发布许可或词包。

## 1. 本地参考资料盘点

核查目录是词遇工作区的 reference/resource。它含 ECDICT、open-dictionary、DictionaryByGPT4、qwerty-learner、MuJing、Read Frog、TypeWords 等项目。能否引用 Git 仓库、能否提取内容、能否在词遇安装包中再分发，是三个不同问题。

| 项目 | 本地 commit / 证据 | 实测或上游信息 | 本项目定位 |
| --- | --- | --- | --- |
| ECDICT | bc015ed2；ecdict.csv | 本地 770,611 行、65,933,428 字节；上游另有更大的压缩版，本次未审计 | 宽覆盖英汉底座、词形、现有考试标签 |
| open-dictionary | 647df7a；README、docs/export_contracts.md、LICENSE-DATA.md | README 声称 v2.0 简体中文构建 84,212 词；Release 提供 distribution.jsonl.gz、distribution.sqlite.gz 和审计工件；本地没有取得这些 Release 工件 | 高质量学习者义项及展示规则的候选来源 |
| DictionaryByGPT4 | 8c9b050；gptwords.json | 本地 17,077,970 字节，8,714 行、7,954 个忽略大小写后不同词头 | 经审核的可选 AI 学习内容，不作为基础释义 |
| qwerty-learner | 122acd9；public/dicts | 本地 380 个 JSON、77,132,056 字节；各词表含不同目标和语言 | 词书/练习体验参考；第三方数据暂不再分发 |
| MuJing | 本地 Dictionary.kt、dict/ecdict.7z | 代码查询 ecdict.db，项目中另有 ecdict.7z | ECDICT 消费案例，不能算额外独立词典 |
| Read Frog | 本地 README 与扩展代码 | 字典动作、在线/AI 翻译、TTS、Notebase 等 | 插件交互参考，不是离线大词典输入 |

现有桌面端 ECDICT 词包为 726 个 gzip JSONL 分片加 manifest，共 24,353,837 字节（约 23.23 MiB），可作浏览器首版压缩体积的**基线**，不能当作融合后词包的实测大小。原始 CSV 与已压缩词包的字节数不可直接比较查询性能。

### ECDICT 字段实测

使用 Python csv.DictReader 对上述 CSV 逐行统计非空字段；词频另计大于零的值。CSV 中的值是词条行，不等于去重后的英文 lemma、有效义项或可展示词卡数。

| 字段 | 非空行 | 占 770,611 行约数 | 处理方式 |
| --- | ---: | ---: | --- |
| word | 770,611 | 100% | 原词头保留；另建不丢失大小写的查询键 |
| translation | 768,739 | 99.76% | 简明中文回退，需拆分并识别词性前缀 |
| definition | 160,884 | 20.88% | 可做英语回退，不直接作为精细义项树 |
| phonetic | 218,065 | 28.30% | 保留原始文本，不标成标准 IPA |
| tag | 14,942 | 1.94% | 仅带有显式 zk/gk/cet4/cet6/ky/ielts/toefl/gre 的词条可产生对应标签 |
| exchange | 96,290 | 12.50% | 解析词形变化，记录类型和原字符串 |
| pos / audio | 0 / 0 | 0% / 0% | 不能凭字段名承诺词性频率或录音 |
| detail | 1 | 小于 0.01% | 不能承诺自带例句 |
| bnc / frq 大于零 | 45,443 / 42,231 | 5.90% / 5.48% | 0 是缺失/哨兵值，不能把所有词条当作有词频 |

这份 CSV 中 <code>ә</code>（U+04D9，西里尔字符）出现在 100,414 条非空 phonetic 中，ASCII 撇号出现在 172,023 条，ASCII 冒号出现在 76,856 条。例：<code>abandon → ә'bændәn</code>、<code>queue → kju:</code>、<code>record → ri'kɒ:d</code>。将这些文本统一贴上“IPA”标签会误导用户；转换应有规则版本、差异检查和人工抽样。ECDICT README 也把 detail/audio 写作“待添加”，与本地空字段相符。

ECDICT README 说明曾从不同资料汇集词条，仓库 LICENSE 为 MIT。项目在再分发时仍保留版本、许可文件和上游署名，并把来源历史记录为审计事项。

### qwerty 与 GPT4 的实际增量

qwerty 的一些词表项含 name、usphone、ukphone、trans，格式适合借鉴，但一个词存在于某词书只说明**列表成员关系**，不能自动证明“官方 CET4 词”或覆盖全部考试范围。其 README 明示字典数据来自 kajweb、语音来自有道。直接复制音标、译文、词表或语音链接时需要追到相应原始授权；程序 GPL-3.0 不自动覆盖第三方数据。

进一步核查 [qwerty 数据来源声明](https://github.com/RealKai42/qwerty-learner#%E6%95%B0%E6%8D%AE%E6%9D%A5%E6%BA%90) 与 [kajweb/dict](https://github.com/kajweb/dict)：后者自述从“X 道背单词(app)”抓取，并给出有道、新东方等词书的原始地址；检查其仓库根目录时未见数据再分发许可证。**公开 Git 仓库、项目代码 GPL-3.0、上游贡献者署名，均不能证明原词书权利人已许可二次打包。**有道当前[词典服务条款](https://c.youdao.com/dict/law/youdao_dict_service.html)限制程序化提取和向第三方提供相关资料；这是对未来使用方式的警示，不能倒推认定 qwerty 既往行为违法。qwerty 当前代码的一个发音路径按词头生成 dictvoice 在线请求，另有浏览器 speechSynthesis 路径；此处不能推断它把所有录音文件打包进了词表。

DictionaryByGPT4 的 JSONL 每行主要是 word 与 content 长文，没有机器可核验的 sense_id、地区音标或逐条引文。按忽略大小写的词头与这份 ECDICT CSV 比较，7,954 个不同词头里 7,939 个已存在，仅 15 个未命中；这 15 个也含疑似拼写问题，不能视为 15 个已核验新词。它很适合启发“理解、例句、文化、记忆”的卡片设计，但 AI 文本可能混杂词源、典故、例句与推测，需要引用/事实校验。其仓库 LICENSE 为 CC BY-SA 4.0；若要使用，还要核查实际输出与组成素材的权利、标注 AI 来源，并避免覆盖可信词典义项。

## 2. 新增的上游与主要区别

| 来源 | 上游官方资料 | 给词遇带来的净增价值 | 不能解决的问题 |
| --- | --- | --- | --- |
| Wiktextract + English Wiktionary | [Wiktextract README](https://github.com/tatuylonen/wiktextract/blob/master/README.md)、[Kaikki 下载页](https://kaikki.org/dictionary/rawdata.html) | POS、sense、forms、examples、IPA、地区标签、Commons 音频引用；大量词源和词用信息 | 提取工具 MIT 不覆盖 Wiktionary 文本；下载的 English Wiktionary 全量包含其他语言，必须筛 lang_code=en；质量与字段覆盖不均 |
| Open English WordNet | [README](https://github.com/globalwordnet/english-wordnet)、[LICENSE](https://github.com/globalwordnet/english-wordnet/blob/main/LICENSE.md) | synset 与上位/反义/部分整体等关系。官方 2025 核心版标示 135,969 words、107,519 synsets；2025+ 含更多专有名词 | 不是英汉翻译主词典；不应按同形词盲连任意 synset；当前子模块 commit 不等于已下载/校验 2025 正式数据 |
| open-dictionary | [README](https://github.com/ahpxex/open-dictionary)、[数据许可](https://github.com/ahpxex/open-dictionary/blob/main/LICENSE-DATA.md) | Wiktionary 策展后学习者解释、双语例句、义项 core/common/rare 优先级、US/UK IPA、成熟 JSONL/SQLite 发布样式 | 派生自同一 Wiktionary 谱系，不能与 Wiktextract 算两份独立证据；其公开契约不含 audio_url |
| CMUdict | [README](https://github.com/cmusphinx/cmudict/blob/master/README)、[LICENSE](https://github.com/cmusphinx/cmudict/blob/master/LICENSE) | 当前子模块 cmudict.dict 实测 135,166 行（含多读音行）；美式 ARPAbet 音素与重音，多读音可保留；许可文本允许再分发并要求保留声明 | 不是 IPA 原文，没有英式读音或真人音频；转换成 IPA 有音系和方言信息损失 |

Wiktextract 的 sounds 中 ipa 与 audio 可以在同项，也可能分项；数据结构允许 audio-ipa。只有同一发音记录或另有明确校验关联时，才把具体录音附到具体 IPA。Wikimedia Commons 的[再利用说明](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia/en)要求核对每个媒体文件的许可、作者和署名方式，不能以“来自 Commons”代替许可。

## 3. “最佳组合”的结论

原提案“ECDICT + Wiktextract + Open English WordNet + open-dictionary + DictionaryByGPT4，再加 qwerty 标签”覆盖的**功能方向**是合理的，却不是当前最适合直接加工发布的来源清单。

建议首版离线词卡以 **ECDICT + open-dictionary v2.0 发布工件** 建立可用基线；取得固定 English Wiktionary 快照后再用 Wiktextract 补原始义项、标签与完整发音候选。**Open English WordNet 2025 core 与 CMUdict** 作为分阶段启用的语义和美式音素模块。open-dictionary 在同源词义冲突中视为 Wiktionary 的策展层，不计独立票。DictionaryByGPT4 与 qwerty 暂作研究/人工验证来源，不进入默认包。音频另作许可审查。仓库与候选数据修订见 [版本锁定](SOURCE_LOCK.md)，具体实施见 [任务文档](TASKS.md)。

还值得观察：

- [open-dict-data/ipa-dict](https://github.com/open-dict-data/ipa-dict)：多地区 IPA 比较方便；其 US 数据以 CMUdict 转换为基础，UK 数据又有 GPL-3.0 上游，当前投入后的独立增量和许可成本不如直接选 CMUdict + Wiktionary。
- [rspeer/wordfreq](https://github.com/rspeer/wordfreq)：Zipf 分值可用于排序和词包分级，README 说明基础语料约停于 2021 年，应把它当作历史频率估计并做许可审核。
- [Kaikki 按语言下载](https://kaikki.org/dictionary/)：这是数据快照服务，不是应设成 Git 子模块的源仓库；必须固定下载文件的哈希与采集日期。

不能只看词条总量评判效果。首个可用版本至少应报告：词头交集/增量，核心词的中英释义、IPA、录音和例句覆盖率，词性/同形异义误配率，来源冲突率，人工抽样错误率，包体积、离线查询时延和许可证清单。

## 4. 版本与许可门禁

| 层次 | 必须记录 | 当前状态 |
| --- | --- | --- |
| Git 上游 | HTTPS URL、commit、仓库许可证、引用路径 | 五个子模块已固定 |
| 数据工件 | 发行版、URL、下载日期、字节数、SHA-256、原始许可 | Wiktionary/Kaikki、open-dictionary、OEWN 的具体文件尚未固定 |
| 字段级加工 | source_ref、源字段、转换规则版本、人工修订记录 | 契约已设计，管线未实现 |
| 媒体 | Commons 文件页、作者、许可证版本、署名文本、SHA-256、音频格式 | 未审查、未打包 |
| 发布包 | 生成代码 commit、输入快照哈希、schema、构建时间、包 SHA-256、数据许可/署名 | 未生成 |

任何缺失许可证、缺失哈希、无法证明来源或不能在目标许可下再分发的内容都不得进入公开发布包。保留多层包可降低耦合：ECDICT 基础包、增强义项包和独立音频包分别列明组成，不让一个来源的限制暗中扩展到所有包。

## 5. qwerty 复用方式与发布边界

以下是工程风险判断，不是对上游项目是否侵权的认定。代码许可证、词典内容权利、在线服务条款需要分别核验；重新导出为 JSONL 或重写转换器不会清除输入数据的权利限制。[GNU GPL FAQ](https://www.gnu.org/licenses/gpl-faq.en.html#GPLOutput)也说明，通常转换程序的许可证并不自动决定输出内容的许可证。

| 用法 | 本项目判断 | 发布前动作 |
| --- | --- | --- |
| 借鉴“来源文件 → 清洗 → 标准词条 → 分片/索引”流程、词表选择交互，独立实现代码 | 可行；[WIPO](https://www.wipo.int/en/web/copyright/faq-copyright)区分思想、方法与具体表达 | 记录设计参考；输入数据仍须单独核权 |
| 复制 qwerty 转换代码或运行时代码 | GPL-3.0 可提供复用路径，但要保留原署名、许可证和相应源码；不因此取得第三方词典权利 | 明确复制文件和修改记录，检查与词遇 GPL-3.0 的组合分发义务 |
| 复制 qwerty 的 JSON 词表、音标、译文、例句，转换字段后打包 | 当前来源链没有充分再分发授权证据，不进入默认包 | 逐词书取得上游权利证明；不能以改写格式、AI 改写译文或仅保留单词顺序规避来源审查 |
| 仅提取 qwerty 中 CET/GRE 等成员关系作为 tag | 大规模复制特定书的选词、分类或排序仍有来源与编排风险；标签名本身也不能证明官方认可 | 优先使用有明确许可的独立来源；保留标签来源和含义，不宣称“官方词表” |
| 仿照 dictvoice 直接请求有道录音，或缓存/打包返回音频 | 在线使用、批量抓取、音频再分发属于不同授权；“开放 API”致谢并非明确许可 | 无书面或公开可适用许可时，不把它设为默认来源；优先逐文件许可明确的录音或明确标记的系统 TTS |

ECDICT 仓库标示 MIT，但其[选词说明](https://github.com/skywind3000/ECDICT/wiki/%E9%80%89%E8%AF%8D)提到多种词书、考试大纲和语料库，因此 ECDICT 的 oxford、collins、tag、词频等字段也应保留来源审计，不能把“仓库 MIT”理解为每个历史输入都有独立授权证明。Wiktextract 的 MIT 只覆盖提取工具；[Wiktionary 文本](https://en.wiktionary.org/wiki/Wiktionary:Copyrights)采用 CC BY-SA 4.0 / GFDL，例句与媒体还可能有其他权利。open-dictionary 明确将[发布数据](https://github.com/ahpxex/open-dictionary/blob/main/LICENSE-DATA.md)定为 CC BY-SA 4.0，Open English WordNet 的[许可](https://github.com/globalwordnet/english-wordnet/blob/main/LICENSE.md)要求同时署名其团队与 Princeton WordNet，CMUdict 要保留自己的许可声明。

CC BY-SA 内容进入公开产物时必须署名、标注修改，并对实际改编部分履行相同方式共享。[Creative Commons FAQ](https://creativecommons.org/faq/#if-cc-sa-licensed-content-is-included-in-a-database-does-the-entire-database-have-to-be-licensed-under-an-sa-license)指出，仅将独立作品汇编在一个数据库，并不自动要求整个数据库同用 SA；但词遇计划做字段级加工与义项融合，具体是否构成改编要按产物判断。代码仓库的 GPL-3.0 也不能代替数据包的 CC BY-SA 声明。构建时给每个字段保留来源、许可和加工记录，分别发布数据许可清单；无法证明权利的字段剔除。
