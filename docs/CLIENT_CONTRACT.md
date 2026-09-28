# 词包消费契约（0.0.1）

浏览器插件和桌面端应从固定版本的 GitHub Release 获取资产，校验 `release-candidate.json` 中的外层 SHA-256，再按归档内 manifest 校验每个文件。开发期可以使用本地 `dist/final/`；当前 `candidate-needs-human-review` 状态不能被当成正式自动更新信号。源码仓库用于开发，不作为运行时词典子模块。

| 资产 | 适合的客户端 | 主要内容 |
| --- | --- | --- |
| `core.tar.gz` | 浏览器轻量离线初装 | 5,000 词 JSONL、清单、许可与审校依据 |
| `no-audio.tar.gz` | 完整离线查词 | SQLite、完整 JSONL、音频候选目录 |
| `with-audio.tar.gz` | 需要高频离线播放 | 与无音频版相同的词典，加 436 条录音及逐文件署名 |

完整包的 `dictionary.sqlite` 有 `entries` 词条表和 `forms` 词形索引；`entries.payload` 与 `entries.jsonl.gz` 使用同一 `leximeet.entry.v1` JSON。先按 Unicode NFC + casefold 查词头，没有结果时才回退到词形索引；大小写完全匹配的结果排前。参考实现可运行 `python3 -m leximeet_dictionary lookup --db build/v0.0.1-final/dictionary.sqlite bank`。

展示时按 `senses[].display_order` 排序。策展义项的中英文和 ECDICT 的 `zh_fallback` 不一定逐义对齐；后者只能标为“词条级回退”。若有 `editorial.display_zh`，标为“词遇审校”，其 `revisions[]` 保留旧值与证据。义项 `labels/topics` 与词条 `exam_tags` 不混用；IPA、CMUdict ARPABET 和 ECDICT 旧音标须区分。WordNet 只显示为未对齐的概念候选。

朗读先查独立离线录音包；其余在用户点击时查询并缓存已核权的 Commons 文件或使用设备 TTS。失败不影响离线查词。词包只读，用户单词本、标签、笔记和朗读缓存放在独立存储；安装新包先验证再原子切换，并保留旧版以便回滚。当前本仓库只验证了参考包与格式，真实客户端接入测试由各消费项目承担。
