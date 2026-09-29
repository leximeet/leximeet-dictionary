# 0.0.2 设计：核心版学习词典

**目标**：词遇桌面端和插件端安装核心版后，能直接选择考试词书或专业词书，按稳定顺序学习单词，并在词卡上查看有来源的助记材料。0.0.1 的 117,902 条核心词、离线音频和 811,092 条完整版词条继续有效；本版本只加工核心版。完整版的同等学习内容与非核心词离线音频等核心结构在 1.0.0 稳定后再做。

## 已验证的起点

| 现有材料 | 核心版实测 | 直接用途 | 当前缺口 |
| --- | ---: | --- | --- |
| open-dictionary 主词卡 | 84,212 词，均有 `memory_hook_zh` | 词义、义项和已有助记 | 助记是主词卡的短提示，不能充当所有学习文章 |
| ECDICT 补词 | 33,690 词 | 中文回退、历史频率、考试标签 | 补词没有 `memory_hook_zh`；标签没有成书顺序 |
| ECDICT 考试标签 | 14,942 个核心词至少有一项 | 生成四级、六级、考研等**标签集合** | 不能冒称某个出版社的完整教材 |
| open-dictionary 义项领域 | 22,274 个核心词至少有一项 | 按具体意思生成专业分类 | 标签覆盖不全；不能从词头字面猜领域 |
| DictionaryByGPT4 | 本地 8,714 行；排除 2 篇已知错误后匹配 7,256 个核心词 | 导入独立的 AI 学习文章候选 | 与已有助记多重叠；不能代替逐词核实 |
| qwerty-learner | 首批固定 10 份英语词表 | 有序词书、每书译文及原始英美音标 | 有些词不在核心版；需要与主词义保持分层 |

试构建后，84,491 个核心词有至少一种学习材料，其中 84,212 个已有 open-dictionary 助记。DictionaryByGPT4 匹配的 7,256 词中，6,977 词与现有短助记重合，只为 279 个补词新增学习材料；剩余 **33,411 个**还没有材料。0.0.2 如实交付这一覆盖范围，剩余助记等核心结构在 1.0.0 稳定后与完整版一起生成。

## 两种目录，统一消费接口

`catalogs` 保存目录；`members` 保存 `catalog_id → entry_id` 和顺序。类型只有 `exam`（备考）和 `subject`（专业）。客户端用同一列表 API 显示两类，用户学习进度仍存于自己的数据库，不进入公共词包。

1. **有序词书**：`book:qwerty:CET4_T` 等从 qwerty 资源取词头、原位置、补充译文和英美原始音标，按 `entry_id` 关联词遇词卡。译文与音标分别保存在每本词书的 `source_payload`，不覆盖主词义或主 IPA；不导入音频和习题。未匹配、重复及大小写歧义出审计报告。
2. **考试标签集合**：`exam:ecdict:cet4` 等来自既有词卡的 `ecdict.exam_tags`。顺序是词遇按 ECDICT 历史词频和词头派生，不是来源教材顺序。可以作为可学习的“备考集合”，名称须标明“ECDICT 标签”。
3. **义项领域集合**：`subject:topic:computing` 等从 `senses[].topics` 得出。成员保存匹配的 `sense_ids`：进入“计算机”目录后默认突出显示计算机义项，而不是把整个多义词的所有解释都标为计算机。先按匹配义项的 `priority` 排序，再按 ECDICT 历史词频排同级词，避免罕见缩写因常用词头排在首页。首批五类是计算机、生物、医学、法律、金融；生物类明确合并 `biology/biochemistry/microbiology`，原始 topic 保留不变。
4. **专业词表**：`book:qwerty:itVocabulary`、`book:qwerty:BIOmedical` 是独立有序词书，保留词条级归属、补充译文和可用的原始音标。它们不能反过来证明某个具体义项属于医学或计算机。例如 `algorithm` 在程序员词表中，并不意味着 0.0.1 的每个义项都有 `computing` 标签。

首批本地比对也说明两种“专业词书”不能合成同一个真值：qwerty 计算机书在核心版匹配 1,646 词，仅 456 词同时有现成计算机义项 topic；另 1,190 词只有词书归属。生物医学书在核心版匹配 408 词，仅 109 词同时有生物或医学义项 topic；另 299 词只有词书归属。后者是人工/AI 复核领域漏标的候选，不可自动给它们所有义项贴专业标签。

目录可追加其他考试或专业来源，但必须保存来源、作用域、匹配方法和导入统计。不要把“考试”“专业”“词书 ID”“义项标签”压成一个无类型的 `tags` 数组。

## 助记层

词条原始 `memory_hook_zh` 保留。新增的 `mnemonics` 以 `entry_id + source` 为键：`kind` 区分短助记与长篇学习文章，`format` 区分纯文本/Markdown，`review_status` 标出已发布源内容、未经复核的 AI 候选与未来人工通过的材料。DictionaryByGPT4 的 `gptwords.json` 实际为逐行 JSON；同一词头重复、多义大小写不唯一或空内容时不自动选一条。其长文不能覆盖基础释义、英语例句和 open-dictionary 现有短助记。

0.0.2 不生成新的 AI 助记。`learning.mnemonics=[]` 是合法词卡：客户端隐藏助记区域，释义、词书和离线音频照常使用。`learning-missing` 可导出缺口清单，供 1.0.0 之后与完整版共同补齐；届时须以真实释义约束生成内容，并记录模型、输入词卡版本及复核状态。

## 数据交付与兼容

当前实现为单独的 `leximeet.learning.v2` SQLite：`metadata`、`catalogs`、`members`、`mnemonics`；它还能组装 `leximeet.entry.v2` 核心词 JSONL，字段位置见[真实词条讲解](WORD_ENTRY_MODEL.md)，新增字段契约见 [JSON Schema](../schemas/leximeet.entry.v2.schema.json)。它只读取 `core.entries.jsonl.gz`，不重建 0.0.1 的 1.74 GB 完整版，也不修改 `leximeet.entry.v1` 或音频分片。客户端按 `entry_id` 左连接词卡与学习索引；升级期间 0.0.1 词卡仍可独立查词。发布时把学习索引作为核心版资产纳入新版固定 `release.json`，记录大小、哈希和来源声明，端侧校验后原子替换。本地构建产物须经过远端发布校验，才能作为正式词包分发。

`core-release-build` 按 `leximeet.release.v2` 交付 0.0.2 的**单一核心版**：完整 v2 JSONL、学习 SQLite、固定来源锁、许可声明和复用的 0.0.1 核心音频索引与分片。来源锁固定**官方 v0.0.1 Release 清单**的 SHA-256，构建器拒绝使用同版本但音频不同的本地旧包。`release.json` 给出每个文件的字节数与 SHA-256，并分别记录助记、音频覆盖数；同名同哈希的音频资产可由客户端直接复用。`core-release-verify --deep` 核对逐词词卡、词书、现有助记及全部核心音频。消费协议见 [0.0.2 客户端接入](CLIENT_CONTRACT_0.0.2.md)。

基于官方 v0.0.1 核心资产的本地真实候选已完成深检：117,902 条词卡、117,902 条音频、84,491 条带助记，共 17 个发布资产。远端验收以 [Actions](https://github.com/leximeet/leximeet-dictionary/actions) 日志与公开 Release 的资产清单为准。

本地构建还写出同名 `*.report.json` 和 `*.audit.json`；后者记录未匹配、歧义、重复、排除及无效内容。加入 SAT、GMAT 后，实测 23 个目录、32,236 条 qwerty 词书成员，其中 32,236 条有补充译文、31,823 条有原始音标；qwerty 有 534 条跳过记录，GPT 有 699 条审计项，其中 2 条是已知错误文章的编辑排除。`learning-sources.lock.json` 固定 qwerty 十个 JSON 和 DictionaryByGPT4 的文件哈希。CLI 可在不提供这两种候选来源时，仅从核心词卡生成 ECDICT 考试集合、义项领域集合与现有短助记；这也是公共数据可独立工作的最低基线。目录快查与分页通过 SQLite 索引完成，消费端无须扫描 117,902 行 JSONL。

## 来源与署名

词书数据来自固定版本的 [qwerty-learner](https://github.com/RealKai42/qwerty-learner)，学习文章来自固定版本的 [DictionaryByGPT4](https://github.com/Ceelog/DictionaryByGPT4)；版本和输入哈希见 `learning-sources.lock.json`。导出时保留逐目录和逐材料的来源，不把补充译文改写成主词义。正式发布时在 `DATA-LICENSE.md` 与词包许可文件中保留相应署名。

## 后续路线

0.0.3 改为交付 `lite/core/full` 的五种分层词包，`full-audio` 在 1.0.0 交付。原计划 0.0.3 填充短语、近反义词、同根词、练习、配图和其他发音候选的工作顺延至 0.0.4；每项内容仍须保存来源、生成方式及审核状态。1.0.0 之后再补齐其余核心词助记和非核心词的学习内容。完整安排见[开发路线](ROADMAP.md)。
