# 0.0.1 客户端接入协议

桌面端与浏览器插件从固定版本的 `release.json` 读取资产，不把本仓库作为运行时 Git 子模块。发布物只有 `core` 和 `full` 两个版本；多个音频 `.pack` 是**下载分片**，不是更多版本。此文档定义文件协议，端侧原生安装与播放仍由各端项目实现。

| 版本 | 词条 | 离线音频 | 适用方式 |
| --- | ---: | ---: | --- |
| `core` | 当前固定输入 117,902 条：全部 open-dictionary 策展词卡及 33,690 条有 ECDICT 词频或考试标签的缺词 | 每个 `entry_id` 至少一段随包录音 | 应用内置 |
| `full` | 当前固定输入全部 811,092 条 | 共享核心词的 117,902 条随包录音；非核心词不保证离线发音 | 用户主动下载后替换当前词包 |

实际数量以同版 `release.json` 为准。核心词卡保留原有完整义项、例句、标签和来源；完整版包含核心版的词条与音频。断网时两版均可查词，核心词可朗读；非核心词可在联网时由客户端按需朗读并缓存。`full` 的音频索引直接引用 `core` 的分片，客户端已有且 SHA-256 相同的核心分片无需重复下载。

## 文件与字段

`release.json` 使用 `leximeet.release.v1`，包含 `dictionary_version`、`entry_schema`、`assets`、`editions.core` 和 `editions.full`。`assets` 按文件名给出 `bytes` 与 `sha256`；每个 edition 的 `assets` 列出安装该版必需的**全部**文件。发布清单本身由固定 Release URL/版本号定位，不要使用浮动的 latest。单个资产小于 2 GB。

| 文件 | 用途 |
| --- | --- |
| `core.entries.jsonl.gz`、`full.entries.jsonl.gz` | 逐行 `leximeet.entry.v1` 完整词条；插件和桌面端都能导入自己的本地索引 |
| `full.dictionary.sqlite.part-*` | 完整版的分片查询库；按 `editions.full.sqlite.parts` 顺序拼接成 SQLite 后使用。核心版以 JSONL 导入端侧索引 |
| `core.audio-index.jsonl.gz` | 每个核心词一行的音频定位与来源记录；两版共用 |
| `audio-core-*.pack` | 多段 Ogg 音频原样串接的二进制分片；两版共用 |
| `audio-sources.json`、`audio-tools.lock.json`、`LICENSE`、`DATA-LICENSE.md`、`notice-*` | 真人录音逐文件署名、合成参数、数据与工具来源声明；资产名与 GitHub Release 文件名一致 |

音频索引的每条记录包含 `entry_id`、`shard`、`offset`、`bytes`、`sha256`、`format`、`kind`、`style`、`source_ref`。`offset` 和 `bytes` 是所在 `.pack` 的**字节范围**：读取 `[offset, offset + bytes)` 后得到独立、可播放的 Ogg 文件。非核心词查不到音频索引时，端侧应保留词卡并按需提供在线朗读。`kind` 为 `human` 或 `synthetic`；`style=spelled-characters` 表示原词头无可听声波时的字符拼读，界面不要把它展示为真人词典发音。真人署名详见 `audio-sources.json`。

```js
// 插件端参考：先按索引找到该词的记录，再从对应分片读取字节范围。
const ogg = shardBlob.slice(record.offset, record.offset + record.bytes, "audio/ogg");
const url = URL.createObjectURL(ogg);
audioElement.src = url;
// 播放结束后 URL.revokeObjectURL(url)。
```

## 下载、校验与替换

1. 使用固定的 `v0.0.1` Release 地址获取 `release.json`，检查 schema 与版本。内置核心版时，应把清单和 `core.assets` 一起打入应用安装包。
2. 用户主动升级时，读取 `full.assets`，按 `bytes` 与 SHA-256 比对已安装资产，只下载缺失或不匹配的文件。下载到临时目录，支持单分片重试；不要覆盖当前可用词包。
3. 全部分片到齐后检查文件哈希，按 `editions.full.sqlite.parts` 拼接 SQLite 并核对 `sqlite.bytes/sha256`；再检查 JSONL 词条 ID、核心音频索引与分片范围。两版的 `audio_covered_entry_count` 均须等于**核心版**的 `entry_count`。词遇提供 `release-verify --deep` 和 `release-assemble` 作为参考实现。
4. 将已校验目录切换为当前词包；失败时保留原核心版。用户单词本、笔记、自定义标签和在线朗读缓存必须放在词包目录之外。

查询先按 Unicode NFC + casefold 查词头，找不到再查词形；按 `senses[].display_order` 展示。`ecdict.zh_fallback` 是**词条级**中文回退，不是逐义翻译。`senses[].labels/topics` 属于义项，`ecdict.exam_tags` 属于词条。IPA 与 CMUdict ARPABET 是不同记法；WordNet 是未和具体义项对齐的概念候选。在线音频服务只作额外语音来源，不计入离线覆盖。

构建、校验与提取一条录音的命令见 [BUILD.md](BUILD.md)。
