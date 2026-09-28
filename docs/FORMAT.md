# 词典产物格式草案

状态：0.0.1 构建器已有可执行的 `leximeet.entry.v1` 和 `leximeet.manifest.v1`；下文的 `v1alpha1` JSON 是早期设计示例，**不是当前实际产物**。实际字段与双版本安装方式以本节、[构建与使用](BUILD.md)和 `leximeet_dictionary/builder.py` 为准。客户端真实试读与发布许可审核仍未完成。

## 0.0.1 已实现的字段契约

一行规范 JSONL 是一个 `entry`，含 `schema_version`、独立 `entry_id`、`headword`、仅供查找的 `lookup_key`、`origin`、`source_entry_id`、`headword_summary_zh`、`memory_hook_zh`、`study_notes_zh`、`forms[]`、`pronunciations[]`、`senses[]`、`ecdict`、`audit_status` 和 `audio_ids[]`。`origin` 为 `curated` 或 `ecdict-fallback`。`ecdict.zh_fallback`/`en_fallback` 始终是词条级原字段；`exam_tags[]` 是来源声称，`frequency_ranks` 保留原 `bnc`/`frq` 名称与正数序位，`legacy_phonetic` 不标 IPA。

`senses[]` 逐条保留 open-dictionary v2.0 的源 `entry_id`、词性、词源组、源 `sense_id` 和组索引，并提供 LexiMeet 自己的 `sense_id`。`english_gloss` 只在**同版 audit** 的词性组、词源组和义项数均对齐时出现，来源标记为 Wiktionary 派生的 audit；中文学习者解释、例句、优先级仍为策展层。`labels[]` 与 `topics[]` 以义项为 scope；未做跨快照义项推断。`pronunciations[]` 区分 `IPA` 与 `ARPABET`，读音地区仅按源标签确定；ECDICT 旧记法在另一字段。

`dictionary.sqlite` 的 `entries` 是词卡正文，`forms` 是词形查询索引，`audio_candidates` 是**待核权线索**，`wordnet_synsets`/`wordnet_lemmas` 是独立概念网络。WordNet 候选查询结果显式标为 `unmapped-headword-candidate`，不装作某个义项的已确认同义词。`audio-candidates.jsonl.gz` 只供在线提供方查线索；词卡的 `audio_ids[]` 在本版为空，录音关联由单独的 `audio/manifest.json` 完成。

无音频版和带发音版分别由 `edition.no-audio.json`、`edition.with-audio.json` 定义，二者共享同一 `manifest.json`、SQLite 和 JSONL。带发音版增装 `audio/` 中经许可元数据审核的高频录音；其他词仍走按需缓存。清单中的 SHA-256 是安装及回滚校验依据。**首次 0.0.1 构建的稳定 ID 只对固定输入与规则成立；下一次来源升级必须提供显式重定向账本，不能凭现有 UUIDv5 规则声称跨版本自动稳定。**

## 1. 三种不同用途的文件

| 文件 | 用途 | 选择理由 |
| --- | --- | --- |
| 规范词条 JSONL + manifest.json | 可追溯的发布中间层与交换格式 | UTF-8、一行一词条，便于流式处理、逐条校验、增量比对和按来源审计。大文件使用 gzip/zstd；不做一个巨大的 JSON 数组。 |
| SQLite 查询包 | 桌面端离线检索及批量筛选 | 有词头、词形、标签、义项与全文索引；能原子替换整个只读词典版本。它由规范层构建，不手工编辑。 |
| 插件核心包与可选分片 | 浏览器离线查询 | 小型高频核心包随插件提供，扩展分片按需下载并校验；查询可预建索引或首次导入扩展独立存储。不能启动时把完整 JSONL 读进内存。 |

三个产物共用 entry_id、sense_id、来源语义和 schema 版本，但字节格式不同。大型静态词典和**用户单词本**应分存储：词典是只读、可整体替换的公开数据；用户在浏览器或桌面上的笔记、复习进度、收藏与自定义词是可写私有数据。

## 2. 一个词条的逻辑模型

~~~text
entry（词头和查找键）
 ├─ source_refs（源快照、源记录和字段的证据）
 ├─ forms（lemma、屈折形、拼写变体，不混成同一个词）
 ├─ pronunciations（地区、词性、记法、转写方法）
 │   └─ audio_ids → 独立音频清单/音频包
 ├─ senses（词性、词义、双语释义、例句、优先级）
 │   └─ relations → 可核验的 WordNet synset/sense
 └─ labels（ECDICT 原始考试标签、词频值及其来源）
~~~

词头匹配只产生**候选 entry**，不是义项等同证明。同形异义（bank）、名词/动词重音变化（record）、大小写有意义的词（May/may）、短语、连字符变体和屈折形必须有独立的分组/对齐规则。查找键可做 Unicode 规范化、大小写折叠和标点容错，但 entry_id 不由简单 lower-case 结果直接生成。首次发布后保持稳定 ID，合并/拆分词条时提供 ID 重定向表，避免用户笔记悬空。

### JSONL 行示例

以下是**人为编写的字段示例，不代表已从上游加工或人工核实的词条**。实际发音和义项需从固定快照取得。

~~~json
{
  "schema_version": "leximeet.entry.v1alpha1",
  "entry_id": "demo-en-record",
  "headword": "record",
  "language": "en",
  "lookup_keys": ["record"],
  "forms": [],
  "pronunciations": [
    {
      "pronunciation_id": "demo-pron-n",
      "region": "en-US",
      "part_of_speech": "noun",
      "notation": "IPA",
      "text": "/ˈrɛkərd/",
      "derivation": "source-transcription",
      "source_ref_ids": ["demo-source-wikt-n"],
      "audio_ids": []
    },
    {
      "pronunciation_id": "demo-pron-v",
      "region": "en-US",
      "part_of_speech": "verb",
      "notation": "IPA",
      "text": "/rɪˈkɔrd/",
      "derivation": "source-transcription",
      "source_ref_ids": ["demo-source-wikt-v"],
      "audio_ids": []
    }
  ],
  "senses": [
    {
      "sense_id": "demo-sense-n",
      "part_of_speech": "noun",
      "priority": "core",
      "glosses": [
        {"language": "zh-Hans", "text": "记录", "source_ref_ids": ["demo-source-zh"]}
      ],
      "examples": [],
      "source_ref_ids": ["demo-source-wikt-n"]
    }
  ],
  "labels": [
    {
      "scheme": "exam",
      "code": "cet4",
      "status": "source-asserted",
      "source_ref_ids": ["demo-source-ecdict"]
    }
  ],
  "relations": [],
  "source_refs": [
    {
      "source_ref_id": "demo-source-ecdict",
      "source_id": "ecdict",
      "source_record_id": "record",
      "snapshot_id": "demo-only"
    },
    {
      "source_ref_id": "demo-source-wikt-n",
      "source_id": "wiktionary",
      "source_record_id": "demo-noun",
      "snapshot_id": "demo-only"
    },
    {
      "source_ref_id": "demo-source-wikt-v",
      "source_id": "wiktionary",
      "source_record_id": "demo-verb",
      "snapshot_id": "demo-only"
    },
    {
      "source_ref_id": "demo-source-zh",
      "source_id": "ecdict",
      "source_record_id": "record:translation",
      "snapshot_id": "demo-only"
    }
  ]
}
~~~

上例的 source_refs 使用演示用 ID；正式产物必须使每个被引用的 source_ref_id 都在词条或全局来源索引中存在。所有数组可为空，但不得用假内容填满缺失字段。priority 的 core/common/rare 来源于 open-dictionary 时要保留其 source_ref；由本项目判定时应记录规则版本。English WordNet 的关系应附 synset_id 与映射置信级，不直接用无向的“相关词”列表淹没义项区别。

## 3. 发音模型

| 字段 | 含义 | 注意 |
| --- | --- | --- |
| notation | IPA、ARPABET、ECDICT_LEGACY 等明确记法 | ECDICT_LEGACY 不应在 UI 中标成 IPA。 |
| text | 保留原始文本或有规则版本的转换结果 | 保留 Unicode 原值，不能静默把 U+04D9 等字符替换掉。 |
| region | en-US、en-GB、未指定等 | 不从发音字符串猜地区。 |
| part_of_speech / form | 该读音适用的词性或词形 | 没证据就设为未知，不能按位置硬配义项。 |
| derivation | source-transcription、machine-converted、human-reviewed | 机器转换要有 conversion_rule_version 和原始 pronunciation_id。 |
| source_ref_ids | 具体版本与原始位置 | 能回溯 Wiktionary 页面/快照、open-dictionary 记录或 CMUdict 行。 |
| audio_ids | 经过证据校验的音频资产引用 | IPA 存在不意味着一定有录音。 |

建议展示排序为：有地区/词性证据的原始 IPA；受同一 Wiktionary 谱系策展的 open-dictionary IPA；可追溯的 CMUdict 转写（明显标注为转换）；其他只在高级来源详情中呈现。对单词 read、record、lead 等设计专项对照样本，校验词性、多音与重音。机器转换后的字符串不能反向冒充原始 IPA。

### 音频独立清单

词条只存 audio_id。音频清单每行至少有 audio_id、entry_id/pronunciation_id、语言地区、content_sha256、mime_type、duration_ms、来源文件页、作者、license_id、license_url、attribution_text、处理/转码记录。可分发文件单独存放，如 audio/sha256 前缀/内容哈希.ogg；一个源文件的 OGG 与转码 MP3 分别登记哈希和关系。

没有逐文件许可与作者信息的 Commons 链接仅是**待核验线索**，不能进入离线音频包。系统 TTS 是运行时能力，不伪装为真人录音，也不在词典 JSON 中保存“微软/谷歌免费音频”一类未经核实的资源 URL。

## 4. 来源与发布 manifest

规范 JSONL 之外，manifest.json 必须包括：

- schema_version、dictionary_version、created_at、生成代码 commit、排序/压缩方式；
- 每个输入的 source_id、repo commit 或数据快照日期、下载 URL、字节数、SHA-256、原始许可与署名；
- 每个输出分片的相对路径、词条范围/分片策略、压缩方式、字节数、SHA-256、总词条数；
- 发布包的数据许可、完整署名入口、人工审计和自动校验结果；
- ID 重定向表版本，以及兼容客户端的最小 schema 版本。

只有 Git 子模块 SHA 而没有 dump 或 Release 的字节哈希，构建仍不可重现。构建过程应固定排序、时间戳处理和压缩参数，使同样输入能得到同样内容哈希；若不能做到，至少公开差异及原因。

## 5. 标签、频率与用户数据

ECDICT tag 的来源标签、词书成员、人工选出的“核心词”和用户自己的标签是四种不同语义。示例结构中的 labels 应具有 scheme、code、source_ref_ids 与 status；qwerty 某词书成员在未获权并复核之前不变成官方考试标签。ECDICT bnc/frq 的 0 表示缺失，不是最低频；各来源词频不应混成一个无单位的整数。

插件与桌面端共享一个可迁移的单词本时，用户数据至少应持有独立的 user_word_id、原始选中文本、规范查找词、可选 entry_id/sense_id、所见词典版本和必要的词卡快照。用户自己的释义或标签永远不覆盖公共词典行；词典升级后用稳定 ID 或重定向表重新关联，关联失败时仍能显示用户保存的快照。桌面连接状态只影响用户数据同步来源，不改变公共词典中的词条身份。

## 6. 首次发布的最低验证

1. 校验 JSONL 可逐行解析、schema 字段类型正确、引用 ID 完整、entry_id/sense_id 唯一、输出哈希匹配。
2. 每条被发布的释义、例句、IPA、关系和标签都有来源；禁止将 AI 生成内容标成词典原文。
3. 按高频词、罕见词、词组、缩写、同形异义、英美多音、大小写和词形变化分层抽样，记录人工核查结论。
4. 比较 ECDICT 基础包与增强包的增量覆盖、误配率、包体积、插件离线首次载入与重复查询时延。
5. 验证音频许可证/署名、缺失与损坏文件的 UI 回退；验证词包更新失败后仍能查询上一版本。

## 7. 本轮设计补充：ID、标签与词表

- open-dictionary v2.0 的源 sense_id 在词性/词源组内按位置编号，不能直接用作 LexiMeet 跨版本稳定 sense_id。源定位必须带发行版、entry_id、pos、etymology_id、sense_id；LexiMeet ID 自行维护版本映射和重定向。
- entry.labels 仅存来源明确的词条级断言，例如 ECDICT 显式考试 tag；领域、语法、语域、时代等按来源所属范围进入 sense 或 pos group；地区音标标签进入 pronunciation。每条断言保留 scheme、scope、原值、标准 code、source_ref、置信度及审核状态。
- Wordlist、WordlistMembership 独立于 ExamAssertion。词表成员关系只有在该词表本身可分发并记录版次时才进入公开包；用户自定义标签、单词本及其关联始终在私有库。
- ECDICT translation 未经核准对齐时是词条级中文回退，不应伪造成英文义项的翻译。WordNet 的 synset 映射也必须有义项证据及版次。
- DictionaryByGPT4 的助记长文属于可关闭的学习层候选，音频提供方与缓存属于客户端运行时层；两者都不能填充主词义的来源空缺。
