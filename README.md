<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/brand/logo-dark.png">
  <img src="assets/brand/logo-light.png" width="360" alt="词遇 LexiMeet 标志">
</picture>

<h1>LexiMeet Dictionary</h1>
<p><strong>词遇词典 · 为桌面端和浏览器插件准备的离线英汉词包</strong></p>
<p>
  <a href="https://github.com/leximeet/leximeet-dictionary/actions/workflows/test.yml"><img src="https://github.com/leximeet/leximeet-dictionary/actions/workflows/test.yml/badge.svg?branch=main" alt="Tests"></a>
  <a href="https://github.com/leximeet/leximeet-dictionary/actions/workflows/core-v0.0.2.yml"><img src="https://github.com/leximeet/leximeet-dictionary/actions/workflows/core-v0.0.2.yml/badge.svg?event=push" alt="0.0.2 Release"></a>
  <a href="https://github.com/leximeet/leximeet-dictionary/releases"><img src="https://img.shields.io/github/v/release/leximeet/leximeet-dictionary" alt="Latest release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/leximeet/leximeet-dictionary" alt="Code license"></a>
</p>
<p>
  <a href="https://github.com/leximeet/leximeet-dictionary/releases/tag/v0.0.2"><strong>下载核心版</strong></a> ·
  <a href="https://github.com/leximeet/leximeet-dictionary/releases/tag/v0.0.1">下载完整版</a> ·
  <a href="docs/CLIENT_CONTRACT_0.0.2.md">接入文档</a> ·
  <a href="docs/WORD_ENTRY_MODEL.md">词条结构</a> ·
  <a href="docs/ROADMAP.md">开发路线</a>
</p>

</div>

以 [open-dictionary v2.0](https://github.com/ahpxex/open-dictionary) 的学习词卡为主体，结合 ECDICT 的中文与缺词、Wiktionary 的部分功能词义项、CMUdict 音素和 WordNet 概念索引。0.0.2 又加入考试与专业词书，以及有来源的助记材料；每层数据保留来源，发布包附逐文件校验信息。

## 选择词包

| 发布包 | 内容 | 适合场景 |
| --- | --- | --- |
| **[v0.0.2 核心版](https://github.com/leximeet/leximeet-dictionary/releases/tag/v0.0.2)** | 117,902 条词卡及逐词离线音频；23 个考试与专业学习目录；84,491 词有助记 | 桌面端、插件端内置与按词书学习 |
| **[v0.0.1 完整版](https://github.com/leximeet/leximeet-dictionary/releases/tag/v0.0.1)** | 811,092 条词条；分片下载，复用核心词离线音频 | 用户主动下载全部词条 |

0.0.2 只发布核心版；完整版仍取自 0.0.1。非核心词尚无随包音频，可以由消费端按需在线朗读。每个版本都以自身 Release 的 `release.json` 为下载和校验入口。

**下一步：[0.0.3 开发路线](docs/ROADMAP.md)。**计划把 `lite / core / full` 与有声／无声组合成共享分片的词包：0.0.3 先交付五种组合，全词离线音频的 `full-audio` 留到 1.0.0。`lite` 精选约 25,000 个核心词并保留入选词的完整词卡；两个 lite 包都以下载资产小于 100 MB 为目标。这些组合目前尚未发布。

## 为什么做这份词典

| 能力 | open-dictionary v2.0 | ECDICT | LexiMeet Dictionary |
| --- | --- | --- | --- |
| 词条 | 84,212 条策展词卡 | 770,611 行原始 CSV | 核心版收齐主词卡；完整版合并为 811,092 条 |
| 释义与标签 | 逐义解释、领域与用法 | 中文回退、词条级考试标签 | 保留义项与词条各自的作用域，不把补充译文覆盖成主释义 |
| 学习 | 词卡中的短助记 | 考试标签与历史词频 | 有序词书、专业目录及独立的助记材料 |
| 发音 | IPA 与在线音频线索 | 旧式音标字段 | IPA/ARPABET 分开记录，核心词逐词离线发音 |
| 交付 | 上游数据格式 | CSV | JSONL、SQLite、音频分片与逐文件 SHA-256 |

ECDICT 补词多数没有人工整理的逐义解释，WordNet 概念也尚未与具体义项自动对齐；词遇不会把这些内容伪装成已审校词义。来源和数量见[词典总览](docs/DICTIONARY_OVERVIEW.md)。

## 接入与使用

消费端从固定版本的 `release.json` 读取 `editions.core.assets` 或 `editions.full.assets`，先按字节数和 SHA-256 校验，再安装词包。0.0.1 完整版的 SQLite 需要按 `sqlite.parts` 拼接；音频按索引中的 `offset`、`bytes` 从 `.pack` 读取。与旧版同名同哈希的核心音频分片可以复用。用户笔记、单词本和自定义标签存于词包之外。

```bash
# 已下载对应 Release 的全部所需资产后，深度校验发布目录。
python3 -m leximeet_dictionary core-release-verify dist/v0.0.2 --deep
python3 -m leximeet_dictionary release-verify dist/v0.0.1 --edition full --deep

# 使用 0.0.1 完整版时，校验分片并拼接查询库。
python3 -m leximeet_dictionary release-assemble dist/v0.0.1 --out /tmp/leximeet-dictionary.sqlite
python3 -m leximeet_dictionary lookup --db /tmp/leximeet-dictionary.sqlite bank
```

应用的下载与原子替换步骤见 [0.0.2 核心版协议](docs/CLIENT_CONTRACT_0.0.2.md)和 [0.0.1 完整版协议](docs/CLIENT_CONTRACT.md)；从源码构建见[构建说明](docs/BUILD.md)。仓库提供词包与参考校验器，桌面端和插件端的原生接入由各自项目完成。

## 自动化检查与发布

推送到 `main` 或向 `main` 提交 PR 会运行单元测试。`v0.0.2` tag 推送已触发[固定来源构建与深检](https://github.com/leximeet/leximeet-dictionary/actions/runs/36540185667)：流水线先创建草稿，核对 GitHub 上每个资产的大小和 SHA-256，全部通过后自动发布。[更新记录](CHANGELOG.md)、[0.0.3 开发路线](docs/ROADMAP.md)和[贡献指南](CONTRIBUTING.md)可查看当前状态与参与方式。

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
