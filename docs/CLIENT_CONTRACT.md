# 桌面端与插件端消费契约（0.0.1）

本契约描述**已经生成的数据结构**与客户端实现责任；当前没有声称词遇桌面端或各浏览器插件已经完成集成。字段实义见 [FORMAT.md](FORMAT.md)，构建与哈希验证见 [BUILD.md](BUILD.md)。

## 安装与版本检查

客户端只选择一种 `edition.*.json`。先解包到临时目录，校验 edition 引用的 `manifest.json` SHA-256，再逐项校验 `outputs` 字节数和 SHA-256；带发音版还要校验 `audio/manifest.json` 及每个文件的字节数、SHA-256、作者、许可链接和文件页。只接受已实现的 `leximeet.edition.v1`、`leximeet.manifest.v1`、`leximeet.entry.v1`。验证完才原子切换当前只读版本，并保留上一版本用于回滚；校验或迁移失败时保持旧版本可查。用户笔记和单词本不在词包目录，也不随词包覆盖。

`release_status=candidate-needs-license-and-human-review` 的本地归档仅用于验证；正式默认下载入口须在发布门禁完成后另行签署/标记。客户端不得仅凭文件名 `0.0.1` 判断它已正式发布。

## 查询

桌面端可以直接以只读模式打开 `dictionary.sqlite`。先运行精确词头查询，再在无结果时查词形索引；按原文大小写完全一致的词头或词形排先，不能将同形异义的多个条目合成一个结果。

~~~sql
SELECT payload FROM entries
WHERE lookup_key = :normalized_casefold_word
ORDER BY CASE WHEN headword = :original_word THEN 0 ELSE 1 END, headword;

SELECT e.payload FROM forms f JOIN entries e USING(entry_id)
WHERE f.form_key = :normalized_casefold_word
ORDER BY CASE WHEN f.form_text = :original_word THEN 0 ELSE 1 END, e.headword;
~~~

`:normalized_casefold_word` 的规则是 Unicode NFC 后 casefold；原始输入单独保留供排序。两条 SQL 是先后回退，不应对已查到的词头再叠加词形结果。`payload` 为 `leximeet.entry.v1` JSON；前端按 `origin` 区分策展词卡和 ECDICT-only 回退。`ecdict.zh_fallback` 是词条级补充；不可显示在某个 `senses[i]` 下当作已对齐翻译。义项 `labels` 和 `topics` 的 scope 均为 sense，考试 `exam_tags` 是 entry 级来源声称。`legacy_phonetic` 不要标为 IPA；WordNet 候选应在独立区块标为“待对齐概念”。

浏览器插件可将 5,000 词 `core.jsonl.gz` 在安装/更新时流式导入自己的只读 IndexedDB 或等效索引，再按需获取完整扩展包。不要每次打开查词面板都解压完整 JSONL，也不要把公共词典与可写用户单词本放在同一重建事务中。完整 `entries.jsonl.gz` 与 SQLite 的 JSON `payload` 采用相同 entry schema；插件与桌面端可用固定样本比对其语义结果。

## 发音与缓存

提供方优先级、在线接口示例、配额与缓存权利边界见[音频提供方与按需缓存](AUDIO_PROVIDERS.md)。

带发音版先用 `audio/manifest.json` 按 `entry_id` 找离线素材，再由用户操作触发播放。无音频版、或带发音版无对应离线文件时，可用 `audio_candidates` 表/目录找到 Commons 文件线索；点击后通过 Commons Action API `imageinfo` 重新核对许可、作者、文件页、MIME 和大小，下载并计算内容哈希，再写入客户端独立缓存。候选 URL **未经核权**，不能直接作为离线素材或默认自动播放。缓存键包含文本、地区、提供方、音色/文件、语速和版本；地区/音标/词性不明确时，应保留“未指定”，避免把名词 `record` 的读音贴到动词义项。

客户端应展示来源文件作者、许可名称及链接、文件页，并提供独立缓存清理入口。请求失败、离线、没有授权素材或没有设备 TTS 时，朗读按钮可提示不可用，但不得阻断本地词卡。系统 TTS 若作为客户端备选，应显示为“合成语音”，并遵守设备/服务的使用条款；公共词典不把合成音频伪装为真人录音。

## 用户数据与下一版迁移

`entry_id`/`sense_id` 在 0.0.1 固定输入与规则内确定。以后更换 open-dictionary 版本、拆分义项或升级 ECDICT 时，构建端必须给出旧 ID 到新 ID 的重定向账本并运行回归审校；客户端在无匹配时仍保存用户看到的旧词卡快照、原文、笔记和复习状态。用户自定义标签/单词本从来不写入公共 `entries`。这部分升级、回滚和跨端一致性仍需在真实桌面与插件端验证。
