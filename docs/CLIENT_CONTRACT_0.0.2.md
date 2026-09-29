# 0.0.2 核心版客户端接入

0.0.2 只交付 `core`。客户端以固定 `v0.0.2` Release 的 `release.json` 为入口，按 `assets` 中的字节数和 SHA-256 下载、校验后原子替换当前核心词包。0.0.1 的 `core/full` 仍能单独安装；本版不生成新的完整版。

| 资产 | 用途 |
| --- | --- |
| `core.entries.v2.jsonl.gz` | 117,902 条完整 `leximeet.entry.v2` 词卡，保留 v1 字段，增加 `learning`。 |
| `core.learning.sqlite` | 词书目录、顺序、义项引用和助记；按 `entry_id` 与词卡关联。 |
| `core.audio-index.jsonl.gz`、`audio-core-*.pack` | 逐词离线音频；与 0.0.1 同名、同 SHA-256 的分片可复用。 |
| `learning-sources.lock.json`、`DATA-LICENSE.md`、`notice-*` | 固定来源与署名。 |

`release.json` 使用 `leximeet.release.v2`，`editions` 仅有 `core`；`entry_schema=leximeet.entry.v2`、`learning_schema=leximeet.learning.v2`。客户端先校验全部资产，再确认 `audio_covered_entry_count == entry_count`、`mnemonic_covered_entry_count <= entry_count`，以及 `base_release.manifest_sha256` 与来源锁一致。助记覆盖数不能假定等于词条数。`core-release-verify --deep` 是参考校验器；安装失败时继续使用旧词包，用户笔记、学习进度和自定义标签仍留在词包之外。

两种学习入口共用 `core.learning.sqlite` 的 `catalogs` 和 `members`：`category=exam` 展示考试词书与标签集合，`category=subject` 展示专业词书和义项领域集合。按 `catalog_id`、`position` 分页；`sense_ids` 非空时只突出这些义项，空数组表示词条级归属。`source_payload` 中的逐书译文和原始音标只作补充，主释义仍以 `senses[]` 为准。一个词的完整结构见[中文词条讲解](WORD_ENTRY_MODEL.md)和[真实 JSON](examples/photosynthesis.v2.json)。

助记以 `learning.mnemonics[]` 按来源展示：已有短助记与 DictionaryByGPT4 长文可以并列；空数组表示当前没有助记，此时隐藏助记区域，查词和朗读仍可用。`review_status=ai-unreviewed` 的长文放在明确标注“AI 材料，待核实”的折叠入口，不作为已核实词典事实或默认释义；[抽查记录](qa/0.0.2/REVIEW.md)已发现个别错误。渲染 Markdown 时关闭原始 HTML，不自动加载远程图片，链接只在用户主动点击后打开；没有安全 Markdown 渲染器时可按纯文本展示。离线音频仍按[0.0.1 音频索引协议](CLIENT_CONTRACT.md)读取。
