# 0.0.2 核心版任务清单

勾选只表示对应步骤已经核验；远端两项须以 [Actions](https://github.com/leximeet/leximeet-dictionary/actions) 和 [Releases](https://github.com/leximeet/leximeet-dictionary/releases) 的实际结果为准。先把核心版变成可按考试/专业学习的词典。0.0.1 完整版保持原样，非核心词的学习内容和全部离线音频等 1.0.0 核心结构稳定后再做。设计依据见 [0.0.2 设计](DESIGN_0.0.2.md)。

| 完成 | 任务 | 做完后怎样检查 |
| --- | --- | --- |
| [x] | 核对现有字段和缺口 | 核心版 117,902 词；84,212 词已有短助记，GPT 候选实测后仍有 33,411 词无学习材料；数据写入设计文档。 |
| [x] | 固定首批参考输入 | `learning-sources.lock.json` 固定官方 0.0.1 Release 清单、qwerty 10 份词表和 DictionaryByGPT4 JSONL 的 SHA-256；哈希不符即停。 |
| [x] | 建立核心学习索引候选 | `learning-build` 生成独立 SQLite，不改 0.0.1 词条；本地报告列出 23 个目录、32,236 条 qwerty 词表成员；audit 文件逐条列出跳过原因。 |
| [x] | 区分考试词书、考试标签、专业义项 | 查询结果保留 `catalog_id/category/source/method/sense_ids/position`；单元测试检查顺序、义项作用域及歧义。 |
| [x] | 接入现有短助记与 GPT 候选 | 分来源、类型、格式、复核状态存储，长文不覆盖词义；单元测试和本地查询可见。 |
| [x] | 记录助记覆盖与后续缺口 | `learning-missing` 能导出暂无助记的核心词；本地试产为 33,411 行。该批内容留到 1.0.0 之后与完整版共同补齐，不是 0.0.2 发布条件。 |
| [x] | 写出一个完整真实词条的中文字段说明 | [词条结构讲解](WORD_ENTRY_MODEL.md) 使用 `photosynthesis` 原始值、JSONC 注释、v2 完整 JSON 与 Mermaid 图，并说明音频、WordNet 与学习索引分层。 |
| [x] | 保留 qwerty 词书补充字段 | 每本词书独立保存译文和英美原始音标，不覆盖主词义；真实构建中 32,236 条成员有补充译文。 |
| [x] | 预留完整核心单词 JSON 扩展结构 | `leximeet.entry.v2` 保留现有词卡，短语、关系、练习、配图均有字段契约；[真实样本](examples/photosynthesis.v2.json)与 [JSON Schema](../schemas/leximeet.entry.v2.schema.json)可核对，117,902 条核心词可导出 JSONL。 |
| [x] | 实现核心学习索引深度核验 | `learning-verify` 检查 117,902 条核心词、80,970 条目录成员及义项引用，并报告助记实际覆盖数。 |
| [x] | 实现 0.0.2 核心版发布协议与本地校验器 | `core-release-build/verify` 只打核心版，复用 0.0.1 核心音频；夹具集成测试覆盖部分助记发包与资产损坏。见[客户端协议](CLIENT_CONTRACT_0.0.2.md)。 |
| [x] | 编写固定输入的自动 GitHub Actions 工作流 | `core-v0.0.2.yml` 由 `v0.0.2` tag 推送触发，固定源码与两个参考仓库提交，只下载 0.0.1 核心资产；全部校验通过后核对草稿资产并自动发布。 |
| [x] | 修正专业目录学习顺序 | 先按匹配义项 `priority`，再按历史词频排序；本地医学目录首页不再从罕见缩写 `be/it/do` 开始。 |
| [x] | 抽查 GPT 候选并约定展示方式 | [抽查记录](qa/0.0.2/REVIEW.md)列出 2 篇已排除文章；其余材料保留 `ai-unreviewed`，接入协议要求折叠展示，发布包附来源声明。逐篇事实核验属于后续内容维护。 |
| [x] | 抽查目录质量 | 专业目录首页顺序已修正；深检保证成员和义项引用有效，509 条 qwerty 未匹配记录只在 audit 中，不进入词书。词书归属不会自动改写义项 topic。 |
| [x] | 用官方 0.0.1 资产复现 0.0.2 核心词包 | 正式 v0.0.1 的 13 个核心资产先通过深检，再产出 17 个 0.0.2 资产并通过深检：117,902 词全部有音频，84,491 词有助记。 |
| [ ] | 远端运行 0.0.2 GitHub Actions | 先推送含自动工作流的 `main`，再推送指向同一提交的 `v0.0.2` tag；检查远端测试、深检和 17 个资产的哈希。 |
| [ ] | 验收正式 Release | 工作流应在资产核验后自动把草稿发布；检查 Release 已公开、`release.json` 可下载且资产哈希一致。0.0.2 不验收客户端实现或练习题。 |

本地复现命令。`BASE` 必须是从[官方 v0.0.1 Release](https://github.com/leximeet/leximeet-dictionary/releases/tag/v0.0.1)下载的核心资产目录，下载步骤见[流水线](../.github/workflows/core-v0.0.2.yml)。本机旧 `dist/v0.0.1` 的音频与正式 Release 不同，不能作为 0.0.2 的固定输入。将 `/path/to` 换为自己的实际路径：

```bash
BASE=/path/to/official-v0.0.1-core
python3 -m leximeet_dictionary learning-build \
  --core "$BASE/core.entries.jsonl.gz" \
  --qwerty-dicts /path/to/qwerty-learner/public/dicts \
  --gpt-file /path/to/DictionaryByGPT4/gptwords.json \
  --out build/learning-v0.0.2.sqlite
python3 -m leximeet_dictionary learning-verify --core "$BASE/core.entries.jsonl.gz" --db build/learning-v0.0.2.sqlite
python3 -m leximeet_dictionary core-release-build --base "$BASE" --db build/learning-v0.0.2.sqlite --out build/v0.0.2-candidate
python3 -m leximeet_dictionary core-release-verify build/v0.0.2-candidate --deep
python3 -m unittest discover -s tests -v
```

词遇产品接入前以对应版本的公开 Release 清单为准；本地试产文件不能直接称为已发布的 0.0.2。`main` 推送或面向 `main` 的 PR 会运行轻量测试，只有 `v0.0.2` tag 推送会启动发布。0.0.1 的历史构建工作流仍可手动重放，但不会再次自动发布。
