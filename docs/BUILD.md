# 0.0.1 构建、查询与双版本词包使用

本页以 Python 3.11+ 标准库运行；构建器没有第三方 Python 依赖。代码在仓库根目录执行。生成目录 `build/` 和下载目录 `downloads/` 已忽略，不提交 Git。0.0.1 **发行候选**使用同一份只读词典核心，提供 `edition.no-audio.json` 和 `edition.with-audio.json` 两个安装清单：后者在前者基础上安装经过逐文件核权的高频录音。其余词继续按用户点击朗读时请求与缓存，断网查词不受影响。

无音频版朗读的 Commons 在线接口、设备 TTS、Azure、有道和其他候选来源的调用方式及缓存许可，见[音频提供方与按需缓存](AUDIO_PROVIDERS.md)。

## 固定输入

先执行 `git submodule update --init`。五个输入的准确 SHA-256、字节数、URL 和版本见仓库根目录 `sources.lock.json`；构建器会逐文件核对。尤其注意：`upstream/open-dictionary` 的 Git commit **不是** v2.0 Release 数据文件；`upstream/wiktextract` 也只是提取工具，不是英语 dump 本身。

~~~sh
mkdir -p downloads/open-dictionary/v2.0 downloads/english-wordnet/2025
curl -fL 'https://github.com/ahpxex/open-dictionary/releases/download/v2.0/distribution.jsonl.gz' -o downloads/open-dictionary/v2.0/distribution.jsonl.gz
curl -fL 'https://github.com/ahpxex/open-dictionary/releases/download/v2.0/audit.jsonl.gz' -o downloads/open-dictionary/v2.0/audit.jsonl.gz
curl -fL 'https://en-word.net/static/english-wordnet-2025-json.zip' -o downloads/english-wordnet/2025/english-wordnet-2025-json.zip
python3 -m leximeet_dictionary build \
  --distribution downloads/open-dictionary/v2.0/distribution.jsonl.gz \
  --audit downloads/open-dictionary/v2.0/audit.jsonl.gz \
  --ecdict upstream/ecdict/ecdict.csv \
  --cmudict upstream/cmudict/cmudict.dict \
  --wordnet downloads/english-wordnet/2025/english-wordnet-2025-json.zip \
  --out build/v0.0.1
python3 -m leximeet_dictionary verify build/v0.0.1
~~~

下载失败时不要切换浮动 `latest` 数据源。输入哈希不符时构建器直接拒绝。完整 WordNet ZIP 在内存和磁盘上以压缩形式读取，无须解包；审计 JSONL 使用流式提取与磁盘索引，避免解压 23.9 GB 的当前 Kaikki 全量快照。首版只对 open-dictionary v2.0 **同版 audit** 的词性组和义项顺序做结构核验后附加英文原义；无法对齐时明确标为 `missing-or-unaligned`，不猜配。ECDICT 只有词条级中文回退，不配到具体义项。

## 两个安装清单

| 文件 | 无音频版 | 带发音版 |
| --- | --- | --- |
| `manifest.json`、`dictionary.sqlite`、`entries.jsonl.gz`、`core.jsonl.gz` | 共用 | 共用 |
| `audio-candidates.jsonl.gz` | 仅保存待核权的 Commons 线索，按需核权/缓存 | 同左，供未随包录音的词使用 |
| `edition.no-audio.json` | 安装入口；离线音频为 0 | — |
| `edition.with-audio.json`、`audio/manifest.json`、`audio/files/*` | — | 安装入口；录音各有作者、许可、文件页、SHA-256 |

生成带发音增量包：

~~~sh
python3 -m leximeet_dictionary audio-pack \
  --db build/v0.0.1/dictionary.sqlite \
  --out build/v0.0.1/audio --limit 500
python3 -m leximeet_dictionary verify-audio build/v0.0.1/audio
python3 -m leximeet_dictionary package --root build/v0.0.1 --out dist
~~~

`dist/` 会得到 `leximeet-dictionary-0.0.1-no-audio.tar.gz`、`leximeet-dictionary-0.0.1-with-audio.tar.gz` 和记录两份字节数/SHA-256 的 `release-candidate.json`。两个归档各自完整可安装，不需要客户端同时下载两版。候选归档的 `release_status` 仍是待审状态；生成归档不会自动推送或发布。

筛选顺序按 ECDICT 原始 `frq`，缺失时才用 `bnc`，并严格匹配 `En-us-<word>.ogg` 等 Commons 文件名；带词性后缀的录音只能进入相同词性。候选 URL 从 audit 提取，但**不是已核权资产**。`audio-pack` 请求 Commons `imageinfo` 元数据，检查许可白名单、作者、许可链接、媒体类型和大小，下载后记录内容 SHA-256；拒绝原因写入 `audio/manifest.json`。自动元数据检查尚需抽样人工复核。文件没有通过核验时不进入离线包，UI 应显示无可用录音或调用用户选定的系统 TTS。

无音频版的按需缓存演示：

~~~sh
python3 -m leximeet_dictionary cache-audio \
  --db build/v0.0.1/dictionary.sqlite \
  --cache audio-cache --region en-US bank
~~~

此命令只有在用户触发时访问 Commons；返回包含本地文件路径、作者、许可和来源页的元数据，重复请求会检查缓存哈希并复用。缓存键包含文本、地区、提供方、音色/文件、语速和版本。浏览器插件或桌面端可按相同契约实现本地提供方适配器；当前仓库的 Python 命令**不等于**已有原生客户端集成。在线服务返回失败、无对应文件或断网时必须保持离线词条可读。缓存由客户端独立管理和清理，不属于用户的单词本或公共词典写入操作。

## 查询与质量报告

~~~sh
python3 -m leximeet_dictionary lookup --db build/v0.0.1/dictionary.sqlite bank --wordnet
python3 -m leximeet_dictionary report --db build/v0.0.1/dictionary.sqlite --out build/v0.0.1/qa
python3 -m unittest discover -s tests -v
~~~

SQLite `entries` 支持精确词头及大小写候选，`forms` 仅在没有词头结果时回退；若来源同时存在 `May` 与 `may` 两条记录，完全匹配者排先。实际 v2.0 输入只有小写 `may` 词头时，查询 `May` 也会返回该词条，不会凭大小写捏造新词条。`wordnet_candidates()` 返回尚未对齐的独立候选概念及有向关系，客户端不得将其误显示为某个 open-dictionary 义项已被 WordNet 验证。`qa/quality-report.json` 是自动覆盖和本机热缓存查找基线；`qa/review-sample.csv` 是 200 条分层人工复核工作表，`review_status=pending` 不等于验收通过。

客户端安装时先把新包放入临时位置，对清单、schema、所有文件哈希及 SQLite 完整性进行校验，再切换只读包指针；校验失败维持上一版。私人单词本、标签、笔记和复习状态在独立存储，公共包不可写。浏览器可消费 `core.jsonl.gz` 的较小高频包；`entries.jsonl.gz` 是完整交换格式，不能在插件启动时一次加载进内存。当前尚未实现插件与桌面端的真实安装/回滚验证，因此不把上述接口契约当成已完成端到端兼容证明。

复核工作表额外提供前两个英文原义/中文解释、词条级中文回退、IPA 与标签预览，留有释义匹配、标签范围、发音和备注列，便于逐条填写结论。

## 发布门禁

公开发布需要：ECDICT 历史字段的权利结论，`qa/review-sample.csv` 的 200 条分层人工判断，具体客户端离线/升级/回滚和用户数据隔离测试，以及离线音频的逐文件授权抽查。当前只可称为可复现的 **0.0.1 发布候选**。代码许可证、数据层许可证与音频文件许可证见 [DATA-LICENSE.md](../DATA-LICENSE.md)。
