# 0.0.2 核心版任务清单

勾选只表示本地已有可复查产物；**0.0.2 尚未发布**。先把核心版变成可按考试/专业学习的词典。0.0.1 完整版保持原样，非核心词的学习内容和全部离线音频等 1.0.0 核心结构稳定后再做。设计依据见 [0.0.2 设计](DESIGN_0.0.2.md)。

| 完成 | 任务 | 做完后怎样检查 |
| --- | --- | --- |
| [x] | 核对现有字段和缺口 | 核心版 117,902 词；84,212 词已有短助记，GPT 候选实测后仍有 33,411 词无学习材料；数据写入设计文档。 |
| [x] | 固定首批参考输入 | `learning-sources.lock.json` 有 qwerty 10 份词表、DictionaryByGPT4 JSONL 的 SHA-256；导入时哈希不符即停。 |
| [x] | 建立核心学习索引候选 | `learning-build` 生成独立 SQLite，不改 0.0.1 词条；本地报告列出 23 个目录、32,236 条 qwerty 词表成员；audit 文件逐条列出跳过原因。 |
| [x] | 区分考试词书、考试标签、专业义项 | 查询结果保留 `catalog_id/category/source/method/sense_ids/position`；单元测试检查顺序、义项作用域及歧义。 |
| [x] | 接入现有短助记与 GPT 候选 | 分来源、类型、格式、复核状态存储，长文不覆盖词义；单元测试和本地查询可见。 |
| [x] | 记录助记覆盖与后续缺口 | `learning-missing` 能导出暂无助记的核心词；本地试产为 33,411 行。该批内容留到 1.0.0 之后与完整版共同补齐，不是 0.0.2 发布条件。 |
| [x] | 写出一个完整真实词条的中文字段说明 | [词条结构讲解](WORD_ENTRY_MODEL.md) 使用 `photosynthesis` 原始值、JSONC 注释、v2 完整 JSON 与 Mermaid 图，并说明音频、WordNet 与学习索引分层。 |
| [x] | 保留 qwerty 词书补充字段 | 每本词书独立保存译文和英美原始音标，不覆盖主词义；真实构建中 32,236 条成员有补充译文。 |
| [x] | 预留完整核心单词 JSON 扩展结构 | `leximeet.entry.v2` 保留现有词卡，短语、关系、练习、配图均有字段契约；[真实样本](examples/photosynthesis.v2.json)与 [JSON Schema](../schemas/leximeet.entry.v2.schema.json)可核对，117,902 条核心词可导出 JSONL。 |
| [x] | 实现核心学习索引深度核验 | `learning-verify` 检查 117,902 条核心词、80,970 条目录成员及义项引用，并报告助记实际覆盖数。 |
| [x] | 实现 0.0.2 核心版发布协议与本地校验器 | `core-release-build/verify` 只打核心版，复用 0.0.1 核心音频；夹具集成测试覆盖部分助记发包与资产损坏。见[客户端协议](CLIENT_CONTRACT_0.0.2.md)。 |
| [x] | 编写固定输入的手动 GitHub Actions 工作流 | `core-v0.0.2.yml` 固定源码与两个参考仓库提交，只下载 0.0.1 核心资产；全部校验通过后才上传草稿。尚未远端运行。 |
| [ ] | 复核 GPT 内容的展示与署名 | [首轮抽查](qa/0.0.2/REVIEW.md)发现 `law`、`will` 等问题；修订或排除已知错误，确认客户端折叠显示 `ai-unreviewed`，正式包附来源声明。 |
| [ ] | 复核目录质量并补专业覆盖 | 特别检查计算机书仅 456/1,646 词已有计算机 topic、生物医学书仅 109/408 词已有生物或医学 topic 的缺口，以及多义词错标、509 条 qwerty 未匹配记录和词书排序；人工抽样结果入报告。 |
| [x] | 试产真实 0.0.2 核心词包 | 本地 `core-release-build` 与 `core-release-verify --deep` 已通过；17 个资产，117,902 条核心词全部有音频、84,491 条有助记。 |
| [ ] | 远端运行 0.0.2 GitHub Actions | 源码与来源固定后，固定 tag 并手动运行；以远端日志及草稿资产哈希为准，不以本地夹具测试代替。 |
| [ ] | 发布前验收和更新公开文档 | 全量核心包、抽样词卡/题目/助记、客户端接入协议、README、CHANGELOG、来源声明均与实际 0.0.2 资产一致；再决定 tag/Release。 |

当前试产命令（将 `/path/to` 换为各自本地参考仓库路径）：

```bash
python3 -m leximeet_dictionary learning-build \
  --core dist/v0.0.1/core.entries.jsonl.gz \
  --qwerty-dicts /path/to/qwerty-learner/public/dicts \
  --gpt-file /path/to/DictionaryByGPT4/gptwords.json \
  --out build/learning-v0.0.2-v2.sqlite
python3 -m leximeet_dictionary learning-catalogs --db build/learning-v0.0.2-v2.sqlite
python3 -m leximeet_dictionary learning-members --db build/learning-v0.0.2-v2.sqlite subject:topic:biology --limit 20
python3 -m leximeet_dictionary learning-missing --core dist/v0.0.1/core.entries.jsonl.gz --db build/learning-v0.0.2-v2.sqlite --out build/learning-v0.0.2-missing.jsonl
python3 -m leximeet_dictionary learning-export --core dist/v0.0.1/core.entries.jsonl.gz --db build/learning-v0.0.2-v2.sqlite --out build/core.entries.v2.jsonl.gz
python3 -m leximeet_dictionary learning-verify --core dist/v0.0.1/core.entries.jsonl.gz --db build/learning-v0.0.2-v2.sqlite
python3 -m leximeet_dictionary core-release-build --base dist/v0.0.1 --db build/learning-v0.0.2-v2.sqlite --out build/v0.0.2-candidate
python3 -m leximeet_dictionary core-release-verify build/v0.0.2-candidate --deep
python3 -m unittest discover -s tests -v
```

词遇产品接入前以对应版本的公开 Release 清单为准；本地试产文件不能直接称为已发布的 0.0.2。
