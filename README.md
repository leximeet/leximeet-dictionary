<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/brand/logo-dark.png">
  <img src="assets/brand/logo-light.png" width="360" alt="词遇-LexiMeet 标志">
</picture>

<h1>LexiMeet Dictionary</h1>
<p><strong>词遇词典 · 为桌面端和浏览器插件准备的离线英汉词包</strong></p>
<p>
  <a href="https://github.com/leximeet/leximeet-dictionary/actions/workflows/test.yml"><img src="https://github.com/leximeet/leximeet-dictionary/actions/workflows/test.yml/badge.svg?branch=main" alt="Tests"></a>
  <a href="https://github.com/leximeet/leximeet-dictionary/actions/workflows/packages-v0.0.3.yml"><img src="https://github.com/leximeet/leximeet-dictionary/actions/workflows/packages-v0.0.3.yml/badge.svg?event=push" alt="Release"></a>
  <a href="https://github.com/leximeet/leximeet-dictionary/releases"><img src="https://img.shields.io/github/v/release/leximeet/leximeet-dictionary" alt="Latest release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/leximeet/leximeet-dictionary" alt="Code license"></a>
</p>
<p>
  <a href="https://github.com/leximeet/leximeet-dictionary/releases/tag/v0.0.3"><strong>下载词包</strong></a> ·
  <a href="docs/PACKAGES_0.0.3.md">接入文档</a> ·
  <a href="docs/WORD_ENTRY_MODEL.md">词条结构</a> ·
  <a href="docs/ROADMAP.md">开发路线</a>
</p>

</div>

以 [open-dictionary v2.0](https://github.com/ahpxex/open-dictionary) 的学习词卡为主体，结合 ECDICT 的中文与缺词、Wiktionary 的部分功能词义项、CMUdict 音素和 WordNet 概念索引。0.0.2 又加入考试与专业词书，以及有来源的助记材料；每层数据保留来源，发布包附逐文件校验信息。

## 选择词包

**[0.0.3 已正式发布](https://github.com/leximeet/leximeet-dictionary/releases/tag/v0.0.3)。** 五种组合共享词卡与音频文件，安装时建立本地索引。下表为首次安装所需的下载大小，包含清单、来源和许可文件，以十进制 MB 计（1 MB = 1,000,000 字节）；精确值见 Release 的 `release.json`。

| 0.0.3 组合 | 词条 | 下载大小 | 离线录音 |
| --- | ---: | ---: | --- |
| **lite-text** | 26,417 | **45.84 MB** | 无 |
| **lite-audio** | 26,417 | **99.95 MB** | 每词都有 |
| core-text | 117,902 | 96.68 MB | 无 |
| core-audio | 117,902 | 344.41 MB | 每词都有 |
| full-text | 811,092 | 141.99 MB | 无 |

lite 适合端侧内置：先保留 23 个学习目录的全部成员和高频功能词，再按历史词频补入，使两包各自严格小于 100 MB；入选词保留完整词卡。core 包含全部 open-dictionary 词卡，其中 84,491 个核心词已有助记。full 的非核心差量分为 11 片；全词有声的 full-audio 留到 1.0.0。安装后还需要索引空间，**下载大小不等于安装占用**。详见[词包与接入](docs/PACKAGES_0.0.3.md)、[发布任务](docs/TASKS_0.0.3.md)和[开发路线](docs/ROADMAP.md)。

旧版 [0.0.2 核心版](https://github.com/leximeet/leximeet-dictionary/releases/tag/v0.0.2)和 [0.0.1 完整版](https://github.com/leximeet/leximeet-dictionary/releases/tag/v0.0.1)继续保留。旧客户端使用对应版本的固定清单。

## 为什么做这份词典

| 能力 | open-dictionary v2.0 | ECDICT | LexiMeet Dictionary |
| --- | --- | --- | --- |
| 词条 | 84,212 条策展词卡 | 770,611 行原始 CSV | 核心版收齐主词卡；完整版合并为 811,092 条 |
| 释义与标签 | 逐义解释、领域与用法 | 中文回退、词条级考试标签 | 保留义项与词条各自的作用域，不把补充译文覆盖成主释义 |
| 学习 | 词卡中的短助记 | 考试标签与历史词频 | 有序词书、专业目录及独立的助记材料 |
| 发音 | IPA 与在线音频线索 | 旧式音标字段 | IPA/ARPABET 分开记录，核心词逐词离线发音 |
| 交付 | 上游数据格式 | CSV | 压缩 JSONL、共享分片与逐文件 SHA-256；安装时建索引 |

ECDICT 补词多数没有人工整理的逐义解释，WordNet 概念也尚未与具体义项自动对齐；词遇不会把这些内容伪装成已审校词义。来源和数量见[词典总览](docs/DICTIONARY_OVERVIEW.md)。

## 接入与使用

其他词遇产品直接使用固定版本的 Release，无需把本仓库作为子模块。消费端从 `release.json` 读取 `editions["lite-audio"].assets` 等目标组合，按字节数和 SHA-256 校验，再建立本地索引。升级只下载缺失或哈希不同的文件；用户笔记、单词本和自定义标签存于词包之外。

按[接入文档](docs/PACKAGES_0.0.3.md)安装 Python 依赖后，可用参考安装器下载并安装 lite 带音频版：

```bash
mkdir -p downloads/v0.0.3
curl -fL https://github.com/leximeet/leximeet-dictionary/releases/download/v0.0.3/release.json \
  -o downloads/v0.0.3/release.json
python3 -m leximeet_dictionary package-install downloads/v0.0.3 \
  --edition lite-audio --cache build/package-cache --out build/dictionary-install \
  --url https://github.com/leximeet/leximeet-dictionary/releases/download/v0.0.3
```

将 `--edition` 改成其他组合即可切换，继续使用同一缓存便可复用文件。原生客户端自行实现下载、索引与播放，不要求浏览器运行 Python。详细协议见[0.0.3 接入](docs/PACKAGES_0.0.3.md)；旧版协议见 [0.0.2 核心版](docs/CLIENT_CONTRACT_0.0.2.md)和 [0.0.1 完整版](docs/CLIENT_CONTRACT.md)，源码构建见[构建说明](docs/BUILD.md)。

## 自动化检查与发布

推送到 `main` 或向 `main` 提交 PR 运行轻量测试。推送 `v0.0.3` tag 自动构建并深检五种组合、验证真实 lite 安装，再创建或补齐草稿；核对 GitHub 上每个资产的大小和 SHA-256 后自动发布。已发布资产不自动覆盖。0.0.3 的[发版流水线](https://github.com/leximeet/leximeet-dictionary/actions/runs/36660279575)已成功，34 个公开资产已与清单核对。触发方式见[构建说明](docs/BUILD.md)；参与入口见[更新记录](CHANGELOG.md)和[贡献指南](CONTRIBUTING.md)。

## 来源与致谢

| 项目 | 对词遇的贡献 |
| --- | --- |
| [open-dictionary](https://github.com/ahpxex/open-dictionary) 与 English Wiktionary 贡献者 | 主词卡、例句、词义与同版审计信息 |
| [Wiktextract / Kaikki](https://kaikki.org/dictionary/) | 主词库缺少的高频功能词义项 |
| [ECDICT](https://github.com/skywind3000/ECDICT) | 中文回退、缺词、考试标签与历史词频 |
| [qwerty-learner](https://github.com/RealKai42/qwerty-learner) | 0.0.2 固定词书的词头、顺序，以及逐书补充译文和原始英美音标；不覆盖主词义 |
| [DictionaryByGPT4](https://github.com/Ceelog/DictionaryByGPT4) | 0.0.2 独立的 AI 学习文章候选；标记待复核，不作为基础释义 |
| [CMUdict](https://github.com/cmusphinx/cmudict) · [Open English WordNet](https://github.com/globalwordnet/english-wordnet) | 美式音素与独立概念网络 |
| [Wikimedia Commons](https://commons.wikimedia.org/) · [eSpeak NG](https://github.com/espeak-ng/espeak-ng) · [Opus](https://opus-codec.org/) | 有署名的真人录音、合成发音与音频编码 |

感谢这些项目、词典编纂者、录音作者和维护者。具体版本、逐层许可、真人录音署名及权利处理方式见 [DATA-LICENSE.md](DATA-LICENSE.md) 和随包 `notice-*` 文件。仓库代码使用 [GPL-3.0](LICENSE)；不同数据和音频保留各自的来源与许可。若发现内容侵权或需要修订，请联系作者并说明具体词条或文件，维护者核查后移除或替换。

0.0.2 的 33,411 个核心词仍无助记；补齐工作与完整版学习内容安排在核心结构稳定之后。现有字段见[真实词条结构](docs/WORD_ENTRY_MODEL.md)，版本安排见[开发路线](docs/ROADMAP.md)。
