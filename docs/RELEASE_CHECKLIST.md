# 0.0.1 维护者交接与发布门禁

本页区分**可以审查并由维护者推送的源码**、**本地可安装候选包**与**允许生产客户端自动下载的正式 Release**。当前只有前两项。维护者负责推送与发布；本仓库的构建命令不会创建 PR、tag、Release 或推送 Git。词遇桌面端、插件端尚在等待本词包，维护者已决定它们的原生集成测试由各消费项目接入时执行，**不是本词典 0.0.1 的发布门禁**。

## 候选资产与复核入口

| 资产 | 面向 | 安装前检查 |
| --- | --- | --- |
| `dist/final/leximeet-dictionary-0.0.1-core.tar.gz` | 浏览器插件的 5,000 词离线核心 | 对照同目录 `release-candidate.json` 的外层 SHA-256，运行 `verify-core`；导入私有只读索引 |
| `dist/final/leximeet-dictionary-0.0.1-no-audio.tar.gz` | 桌面/其他客户端的完整离线词典 | `verify-archive`、解包后 `verify --deep`；朗读按用户点击与提供方策略执行 |
| `dist/final/leximeet-dictionary-0.0.1-with-audio.tar.gz` | 需要高频离线录音的完整词典 | 同上，另验 `verify-audio` 与逐文件署名；其他词仍按需缓存 |

三个归档互相独立。客户端应该锁定明确版本和外层 SHA-256，从固定版本的 GitHub Release 下载；不把词典 Git 仓库当运行时子模块，也不跟随 `latest`。完整语义和私有用户数据边界见 [CLIENT_CONTRACT.md](CLIENT_CONTRACT.md)。本地 `dist/` 与 `build/` 已被忽略，维护者推送源码不会自动上传这些文件。

本地候选的生成修订为 `94fd055b186b8c0d263aca7c7388e8b7dc1fabc8`，`generator.dirty=false`。下面的 SHA-256 仅对应当前待审候选；人工审校若要求改数据或发布状态，必须重新构建并以新哈希替换。

| 本地资产 | 字节数 | SHA-256 |
| --- | ---: | --- |
| core | 17,963,726 | `47b3501ad4d0fcd9c894637820ef7b90bdca8e30c8b5e06d9ca6f7e2f7a92347` |
| no-audio | 433,452,931 | `0ba53f6e5b0ef7d2271ad1eb6850bc6f6e913d960b959dd8f995b47b9903ab07` |
| with-audio | 437,918,827 | `e7161a5d6428da4476eb5c1f3a8e86a0e120771d7c18f55539bec60b1662a29e` |

当前自动验收：11 项夹具、全量六输入哈希、811,092 词条的 JSONL/SQLite 逐行深度校验、三归档外层/成员验证、两种完整包及核心包的隔离安装抽验。固定 34 个功能词补了 161 条独立英文义项；436 条离线 Commons 录音有文件哈希和元数据。第二次全量构建的 JSONL、SQLite、manifest 与第一次字节一致；源码修订记录采用最近一次改变构建内容的 Git 提交，纯文档提交或合并不应改变词包。具体字节数与 SHA-256 以本地最终 `dist/final/release-candidate.json` 为准，不能使用历史迭代记录里的旧候选哈希。

## 正式 Release 尚需的证据

1. 在 `build/v0.0.1-final/qa/review-sample.csv` 完成 **210 条**词义、标签、读音及来源定位复核，包括功能词。`qa/agent-meaning-review.csv` 已对 210 条进行源字段一致性检查和预览级编辑筛查，发现 9 处应修正或回查；其中 99 条 ECDICT-only 记录没有逐义项结构。机器通过不等于独立词义复核通过，具体见 [抽样复核记录](QA_REVIEW_0.0.1.md)。
2. 在 `build/v0.0.1-final/qa/audio-review-sample.csv` 完成 **40 条**录音听辨、作者、许可、链接复核。`qa/agent-audio-review.csv` 已复核 40 条文件哈希、OGG 容器、文件名、署名及许可字段；听辨结论仍单列，不能从文件名推定真实发音。有问题的资产从固定清单移除并重建。
3. 维护者推送源码并使手动候选工作流出现在默认分支后，运行 `.github/workflows/candidate.yml`。它从固定输入独立重建三资产，每次按选择上传其中一份；核对生成修订、各文件哈希和 QA 报告。
4. 上述词典自身门禁通过后，另行将包内 `release_status=candidate-needs-human-review` 升为正式可安装状态并重新生成、核验三资产；**不能只改文件名或 GitHub Release 标题**。生产客户端应拒绝当前候选状态。保留源码修订、输入锁、实际归档哈希、编辑审核记录和各来源许可证/署名。

本词典已给出客户端消费契约、三个独立归档及其本地隔离解包验证。桌面端和插件端的实际安装、离线查询、升级回滚、朗读失败降级和私人数据隔离测试，在各自接入本词典后完成；不据此阻止先把可验证的词典包交给消费项目。

维护者可先推送源码供协作审查，不等于公开发布词包。正式 Release 资产的最终 SHA-256 必须以通过上述门禁后重新生成的清单为准。用户自定义标签、单词本和朗读缓存不属于公共只读词包。
