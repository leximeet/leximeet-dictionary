# 0.0.2 核心版任务清单

勾选只表示本地已有可复查产物；**0.0.2 尚未发布**。先把核心版变成可按考试/专业学习的词典。0.0.1 完整版保持原样，非核心词的学习内容和全部离线音频等 1.0.0 核心结构稳定后再做。设计依据见 [0.0.2 设计](DESIGN_0.0.2.md)。

| 完成 | 任务 | 做完后怎样检查 |
| --- | --- | --- |
| [x] | 核对现有字段和缺口 | 核心版 117,902 词；84,212 词已有短助记，GPT 候选实测后仍有 33,411 词无学习材料；数据写入设计文档。 |
| [x] | 固定首批参考输入 | `learning-sources.lock.json` 有 qwerty 8 份词表、DictionaryByGPT4 JSONL 的 SHA-256；导入时哈希不符即停。 |
| [x] | 建立核心学习索引候选 | `learning-build` 生成独立 SQLite，不改 0.0.1 词条；本地报告列出 21 个目录、24,928 条 qwerty 词表成员；audit 文件逐条列出跳过原因。 |
| [x] | 区分考试词书、考试标签、专业义项 | 查询结果保留 `catalog_id/category/source/method/sense_ids/position`；单元测试检查顺序、义项作用域及歧义。 |
| [x] | 接入现有短助记与 GPT 候选 | 分来源、类型、格式、复核状态存储，长文不覆盖词义；单元测试和本地查询可见。 |
| [x] | 导出下一批 AI 待补词 | `learning-missing` 只导出没有材料的核心词和现有真实释义；本地试产为 33,411 行，逐词带词卡哈希。 |
| [x] | 写出一个完整真实词条的中文字段说明 | [词条结构讲解](WORD_ENTRY_MODEL.md) 使用 0.0.1 的 `photosynthesis` 原始值、JSONC 注释和 Mermaid 图，并说明音频、WordNet 与学习索引分层。 |
| [ ] | 确定 qwerty 每份词表的对外使用依据 | 对候选词表逐份记录权利依据；不能发布者用明确授权来源或独立整理版本替换；公开资产不含待核候选。 |
| [ ] | 复核 GPT 内容的展示与署名 | 抽查匹配、多义词、事实性表述、Markdown 安全；正式包附 CC BY-SA 声明与来源。 |
| [ ] | 补齐 33,411 个无助记核心词 | 用真实词义作约束生成，写入模型/提示词/词卡哈希/复核状态；空值和错词数为 0，抽样复核记录可追溯。 |
| [ ] | 复核目录质量并补专业覆盖 | 特别检查计算机书仅 456/1,646 词已有计算机 topic、生物医学书仅 109/408 词已有生物或医学 topic 的缺口，以及多义词错标、307 条 qwerty 未匹配记录和词书排序；人工抽样结果入报告。 |
| [ ] | 确定并实现 0.0.2 发布协议 | 将核心学习资产、SHA-256、来源声明和升级步骤纳入新版 `release.json`；0.0.1 两版可继续安装，失败可回退。 |
| [ ] | 核心版构建与校验上 GitHub Actions | CI 从固定输入重建学习索引，验证词书引用、逐词助记覆盖、目录查询和许可清单；不要求重新生成完整版词卡/音频。 |
| [ ] | 发布前验收和更新公开文档 | 全量核心包、抽样词卡/题目/助记、客户端接入协议、README、CHANGELOG、来源声明均与实际 0.0.2 资产一致；再决定 tag/Release。 |

当前试产命令（将 `/path/to` 换为各自本地参考仓库路径）：

```bash
python3 -m leximeet_dictionary learning-build \
  --core dist/v0.0.1/core.entries.jsonl.gz \
  --qwerty-dicts /path/to/qwerty-learner/public/dicts \
  --gpt-file /path/to/DictionaryByGPT4/gptwords.json \
  --out build/learning-v0.0.2.sqlite
python3 -m leximeet_dictionary learning-catalogs --db build/learning-v0.0.2.sqlite
python3 -m leximeet_dictionary learning-members --db build/learning-v0.0.2.sqlite subject:topic:biology --limit 20
python3 -m leximeet_dictionary learning-missing --core dist/v0.0.1/core.entries.jsonl.gz --db build/learning-v0.0.2.sqlite --out build/learning-v0.0.2-missing.jsonl
python3 -m unittest discover -s tests -v
```

词遇产品接入前以对应版本的公开 Release 清单为准；本地试产文件不能直接称为已发布的 0.0.2。
