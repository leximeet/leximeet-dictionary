# 词遇共享词典设计基线

状态：2026-09-28 的设计基线与 0.0.1 本地发布候选。配套的[版本锁定](SOURCE_LOCK.md)、[实际格式](FORMAT.md)、[来源审计](SOURCES.md)、[构建与使用](BUILD.md)和[实施任务](TASKS.md)记录输入、契约、证据与验收。构建器已实现同版 audit 的保守对齐、ECDICT 缺词回退、CMUdict、WordNet 独立概念表和双版本音频安装清单；真实客户端集成与发布门禁仍未完成。

## 1. 结论与产品边界

以 open-dictionary 为主词卡，Wiktextract 补足其未选出的原始词典信息，ECDICT 补中文和缺词，WordNet/CMUdict 做独立能力，整体方向合理。需改变的是“按词形叠加一切”这一隐含假设：来源的词义粒度、版本、许可和准确度不同，合并必须落到具体字段及义项，并允许保留多候选和无法对齐的状态。

词遇公共词典提供只读、可替换的离线查询数据，桌面端与各插件端消费同一个语义版本；用户保存的词、笔记、单词本、标签与复习状态存入各端的私有可写库。查词不要求登录、联网、在线音频或 AI。朗读是独立动作。公共词典升级不能覆盖用户编辑，也不能把一次预览自动转成用户 Encounter。

首版展示目标：常用词优先展示 open-dictionary 的学习者解释与双语例句；缺词时回退到 ECDICT 的词条级英汉释义；Wiktextract 的补充证据在能确认义项时进入对应义项，否则放入来源详情/待审候选。词卡应能解释“这一块内容来自哪里、为什么显示、哪里尚不确定”。

## 2. 来源职责和可信边界

| 来源 | 首版职责 | 合并边界 |
| --- | --- | --- |
| open-dictionary v2.0 | 中文学习者解释、学习提示、双语例句、core/common/rare 优先级、精选词形与 IPA | 发行契约为 distribution_entry_v5；解释及例句经过 LLM 生成，不能当作独立于 Wiktionary 的第二份事实证据 |
| Wiktextract + 固定 Wiktionary 快照 | 英文原义、额外词形/读音、义项 tags/topics、可追溯用例与来源信息 | 与 open-dictionary 同谱系；跨快照、跨词性或同形异义时禁止按词头直接合并 |
| ECDICT | 缺词回退、简明中文、显式考试标签、原始词频序位和词形 | translation 常是词条级串，未校准前不挂到任意英文 sense；phonetic 原样保存但不标作标准 IPA |
| Open English WordNet 2025 core | 概念 synset 和语义关系 | 只对已核准的义项映射补充；synset 不等于教材/考试标签 |
| CMUdict | 美式 ARPAbet 音素、重音和多读音 | 不是英式 IPA，也没有录音；转换 IPA 必须保留原文和规则版本 |
| DictionaryByGPT4 | 可选的助记卡片候选 | 长文没有可靠 sense ID，必须人工核事实并与主词义分层；不作为缺词或事实兜底 |
| qwerty-learner | 词表目录、分类 UX 和导入流程参考 | 其词表大量来自第三方；当前没有充分证据支持把词表、译文、音频或大规模成员关系放入公开词包 |
| Aictionary | 离线包下载及独立 TTS 提供方的产品参考 | 不作为词典来源；其默认 Edge TTS 路径不等于词遇获得稳定 API 或音频再分发许可 |

open-dictionary v2.0 的分发契约含义项 labels、topics、priority；这三者分别对应用法/领域/展示排序，不能等同考试词表。它也已经提供 memory_hook 与 study_notes，因此 DictionaryByGPT4 需要证明相对增量，不能因“有助记”就整包叠加。其发行数据将 Wiktionary 文本与生成解释一并按 CC BY-SA 4.0 发布。[发行说明](https://github.com/ahpxex/open-dictionary/releases/tag/v2.0)、[导出契约](https://github.com/ahpxex/open-dictionary/blob/647df7a33e211a03014b6647f7832b0b183911b3/docs/export_contracts.md)、[数据许可](https://github.com/ahpxex/open-dictionary/blob/647df7a33e211a03014b6647f7832b0b183911b3/LICENSE-DATA.md)是本轮依据。[Wiktextract 字段说明](https://github.com/tatuylonen/wiktextract/blob/1a05e46f9efbccda6a2b2f8e21b30a9c0c46513a/README.md)证实 sense.tags、sense.topics、sense.categories 与 sounds 的标签位置不同。

## 3. 逻辑模型：把不同问题分开

~~~text
DictionaryRelease（版本、许可和文件清单）
 ├─ LexemeEntry（词头、语言、同形异义与查找键）
 │   ├─ Form（屈折形/拼写变体）
 │   ├─ Pronunciation（IPA 或 ARPAbet、地区、词性、来源）
 │   ├─ Sense（词性、词源组、英文原义、学习者解释、例句）
 │   │   ├─ SenseLabelAssertion（领域、语法、语域、时代、地区）
 │   │   └─ SynsetMapping（WordNet 概念与关系，含置信度）
 │   ├─ ExamAssertion（来源声称的考试收录）
 │   └─ WordlistMembership（词表 ID、版次、来源与授权状态）
 ├─ AudioAsset / AudioProvider（与离线词典分离）
 └─ SourceRecord（输入版本、原始字段、转换规则、许可证）
UserWord / UserTag / WordBook / ReviewState（仅在用户私有库）
~~~

英语词头语言和释义语言独立记录；首版是 en → zh-Hans，后续其他释义语言可分版添加，不改变同一词条的语言身份。每个来源事实都存 source_ref、源字段/记录位置、快照或发行版、转换规则与审核状态。公开 JSONL 可以用词条内引用及全局 manifest 压缩重复信息，但不得失去反查能力。display_value 是一个带来源的选择结果，不是将互相冲突的原文覆盖掉。

### ID 与对齐

LexiMeet 自己发行 entry_id 和 sense_id，并维护版本间的保留、合并、拆分与重定向表。open-dictionary 的组内 sense_id 实际是按顺序编号（例如 s1），词性组还由 pos 与 etymology_id 共同确定；它不是跨版本全局稳定主键。源引用至少包括 open-dictionary 发行版、entry_id、pos、etymology_id、sense_id。WordNet synset ID 同样要连同 2025 版次记录。

导入时先用保留原文大小写的词头、语言、词性、词源组和多词表达式建立候选；再对英文原义、义项限定词、例句、词性做对齐评分。只有同快照或明确映射且达到阈值的候选允许自动附加标签/关系。存在一词多义、多音、大小写差异或不同快照时，写入待审队列。无法对齐的 ECDICT 中文仍可显示为“词条级中文补充”，不能假装是某个英文义项的翻译。发布后任何自动规则更改须产生差异报告和重定向验证。

## 4. 字段级展示规则

| 字段 | 首选及回退 | 阻断条件 |
| --- | --- | --- |
| 学习者中文解释 | open-dictionary 的 learner_explanation；缺失时 ECDICT translation 作为词条级补充 | 不用 GPT 长文或机器翻译覆盖已策展义项；未对齐时不挂 sense |
| 英文原义与上下文 | 同谱系 Wiktextract 的 gloss、raw_gloss、例句引用；在来源详情中可查看 | 例句若是引文需另查引用/版权，不能与 open-dictionary 生成例句混称 |
| 义项优先级 | open-dictionary 的 core/common/rare，记录源与生成性质 | 无此信息不推断 CEFR 或词频；全部 rare 时仍显示全部 |
| 词形 | open-dictionary 精选屈折形；Wiktextract/ECDICT 补候选 | 拼写变体、屈折形、词根关系不可混为同一种边 |
| 发音标注 | 有地区证据的原始 IPA；open-dictionary 精选 US/UK；CMUdict ARPAbet 独立补缺 | ECDICT 旧记法不能标 IPA；无证据不按词义强行配读音 |
| 考试信息 | ECDICT 显式 tag 作为“ECDICT 收录声明”；独立获权词表的成员关系另列 | 不能标“官方大纲”或由 qwerty 的 category 直接推断某词属于考试 |
| 频率/难度 | 保留 ECDICT bnc/frq 的原字段、量纲与缺失值；priority 只表示源内展示排序 | 不跨源取平均，不将 0 视为最低词频，不把 core 说成 CEFR |
| WordNet 概念 | 已对齐 sense 上显示 synset、上位/反义等 | 单凭同词头不得挂任意 synset |

## 5. 标签分类与归属

| 类型 | 应落位置 | 首版来源和语义 |
| --- | --- | --- |
| 考试标签 | ExamAssertion → entry | ECDICT 的 zk/gk/cet4/cet6/ky/ielts/toefl/gre 等原始声称；标来源与更新时间 |
| 词表/教材 | Wordlist 与 WordlistMembership | 只有逐词表拿到可适用的再分发许可后导入；“某词表收录”与“官方考试词”分开 |
| 领域 | SenseLabelAssertion → sense | open-dictionary meanings[].topics 与 Wiktextract senses[].topics，统一术语但保留原始值 |
| 语法 | sense、pos group 或 form | transitive、countable 等按源所在层保存，不能全压到 entry |
| 语域/时代 | sense | colloquial、archaic、obsolete 等，不随词头扩散到其他义项 |
| 地区/口音 | sense 或 pronunciation | 用于含义的地区词标和用于读音的地区标签分别存 |
| 频率/难度 | entry、pos 或 sense，按原字段 | 数值、等级、展示优先级分别建类型 |
| WordNet 概念 | synset mapping | 与考试/领域标签分开，可在语义网络视图展示 |
| 用户自定义标签 | UserTag、WordBook 及其关联 | 只写私有数据；同名公共标签不能改变用户的自定义归属 |

标签归一化有原始值、标准 code、scope、source_ref、confidence 和审核状态。第一版先做有限白名单映射，遇到未知 tag 仍保留原文；同一 Wiktionary 谱系的 open-dictionary/Wiktextract 标签去重为一个证据族，不做“两个来源一致所以置信更高”的投票。

## 6. 音频与在线提供方

音标文本、可播放录音、系统 TTS 与在线合成语音是四种不同资产。离线查词只读取本地词包；用户按朗读时先查经过授权的本地音频资产，再尝试设备可用的 TTS，最后才调用用户配置或明确许可的在线提供方。失败只影响朗读按钮，仍显示词卡和音标。浏览器端能否离线播 TTS 取决于设备已有语音，不在词典包中承诺。

音频缓存键至少包括规范文本、语言/地区、提供方、音色、语速、输出格式和提供方版本；缓存记录取得时间、源许可/条款、文件哈希、有效期、失败状态与用户删除入口。缓存不得默认上传为公共音频包；在线提供方请求前应说明会发送哪个词或短语，不发送用户所在网页或阅读上下文。Wiktextract 里的 Commons 链接只是候选，按文件页核作者、许可证和署名后才能下载或分发。该要求见 [Commons 再利用说明](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia/en)。

[Aictionary](https://github.com/ahpxex/Aictionary)默认使用 Edge TTS，但 [edge-tts](https://github.com/rany2/edge-tts)只是调用 Edge 在线朗读服务的社区实现，未给词遇独立的服务稳定性、商用或缓存再分发保证。因此不把它写成词遇默认公共 API。若需要正式在线方案，可提供用户自行配置的服务适配器；例如 [Azure Speech 正式文档](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/get-started-text-to-speech)要求资源密钥和区域，公开的 [F0 定价页](https://azure.microsoft.com/en-us/pricing/details/speech/)列有每月免费额度，但不能将项目密钥放入浏览器插件。提供方条款和缓存权利应在实现时逐项核对。

## 7. 构建、产物与客户端

~~~text
固定输入/许可清单 → 按源导入 → 词头与词源分组 → 义项候选对齐
       → 字段选择与标签归一化 → 审计/抽样 → 规范 JSONL + manifest
                                      ├→ 桌面端只读 SQLite 包
                                      └→ 插件核心分片 + 可选扩展分片
~~~

构建器应流式处理大输入，阶段产物可重跑且有确定性排序；不得依赖浮动 Kaikki URL。当前目标磁盘只剩约 5.7 GiB，无法承载 Kaikki 当前约 23.9 GB 的解压数据；全量导入需另备足够空间的隔离存储，先用固定小样本开发。发布 manifest 记录输入哈希、输出哈希、schema、生成 commit、数据许可证、署名、转换规则版本、ID 重定向和兼容客户端版本。浏览器初始包以高频核心词和已校验的离线最低能力为目标，完整扩展包按需下载；桌面端可装全量 SQLite。两端共同解析语义契约，查询索引和压缩方式可以不同。

升级采用先下载临时文件、验哈希与 schema、建立索引、原子切换、保留上一版回滚。用户词库在独立数据库，以用户 ID、可选 entry/sense ID 和旧版词卡快照关联；重定向失败时仍能读自己的笔记和旧快照。音频与词典包分别版本化。

## 8. 发布门禁

正式发布前必须完成：所有使用的文件本地 SHA-256 校验；字段级来源、许可及署名清单；200 个以上覆盖同形异义、多音、词组、大小写、考试词、缺词的分层人工样本；词头/义项/标签/音标的覆盖率与误配率报告；桌面和插件离线查询、损坏包拒绝、升级回滚、用户笔记关联及无网朗读失败的独立验证。未取得授权的 qwerty 词表、未经审查的 GPT 长文、无逐文件许可的音频不得进入默认公开包。

首版不承诺“每个词都有中英义项、例句与真人录音”。验收数值以固定样本和实际设备基线在实施任务中记录；任何较大范围的自动义项合并需人工抽样支持。
