# 0.0.1 维护者交接与发布门禁

本页区分**可以审查并由维护者推送的源码**、**本地可安装候选包**与**允许生产客户端自动下载的正式 Release**。当前只有前两项。维护者负责推送与发布；本仓库的构建命令不会创建 PR、tag、Release 或推送 Git。

## 候选资产与复核入口

| 资产 | 面向 | 安装前检查 |
| --- | --- | --- |
| `dist/final/leximeet-dictionary-0.0.1-core.tar.gz` | 浏览器插件的 5,000 词离线核心 | 对照同目录 `release-candidate.json` 的外层 SHA-256，运行 `verify-core`；导入私有只读索引 |
| `dist/final/leximeet-dictionary-0.0.1-no-audio.tar.gz` | 桌面/其他客户端的完整离线词典 | `verify-archive`、解包后 `verify --deep`；朗读按用户点击与提供方策略执行 |
| `dist/final/leximeet-dictionary-0.0.1-with-audio.tar.gz` | 需要高频离线录音的完整词典 | 同上，另验 `verify-audio` 与逐文件署名；其他词仍按需缓存 |

三个归档互相独立。客户端应该锁定明确版本和外层 SHA-256，从固定版本的 GitHub Release 下载；不把词典 Git 仓库当运行时子模块，也不跟随 `latest`。完整语义和私有用户数据边界见 [CLIENT_CONTRACT.md](CLIENT_CONTRACT.md)。本地 `dist/` 与 `build/` 已被忽略，维护者推送源码不会自动上传这些文件。

当前自动验收：11 项夹具、全量六输入哈希、811,092 词条的 JSONL/SQLite 逐行深度校验、三归档外层/成员验证、两种完整包及核心包的隔离安装抽验。固定 34 个功能词补了 161 条独立英文义项；436 条离线 Commons 录音有文件哈希和元数据。第二次全量构建的 JSONL、SQLite、manifest 与第一次字节一致；源码修订记录采用最近一次改变构建内容的 Git 提交，纯文档提交或合并不应改变词包。具体字节数与 SHA-256 以本地最终 `dist/final/release-candidate.json` 为准，不能使用历史迭代记录里的旧候选哈希。

## 正式 Release 尚需的证据

1. 在 `build/v0.0.1-final/qa/review-sample.csv` 完成 **210 条**词义、标签、读音及来源定位复核，包括功能词；当前均为 `pending`。发现错义项或标签时先修复并全量重建，再重新抽样。
2. 在 `build/v0.0.1-final/qa/audio-review-sample.csv` 完成 **40 条**录音听辨、作者、许可、链接复核；当前均为 `pending`。有问题的资产从固定清单移除并重建。
3. 在隔离的词遇浏览器插件与桌面端中，验证核心/完整包安装、断网查词、损坏拒绝、升级回滚、朗读失败降级，以及用户单词本、笔记与词典只读包隔离。Python 解包抽验只证明参考路径，不代替原生端验收。
4. 维护者推送源码并使手动候选工作流出现在默认分支后，运行 `.github/workflows/candidate.yml`。它从固定输入独立重建三资产，每次按选择上传其中一份；核对生成修订、各文件哈希和 QA 报告。仅推送功能分支时，手动工作流可能尚未在默认分支显示。
5. 上述门禁均通过后，另行将包内 `release_status=candidate-needs-human-review` 升为正式可安装状态并重新生成、核验三资产；**不能只改文件名或 GitHub Release 标题**。生产客户端应拒绝当前候选状态。保留源码修订、输入锁、实际归档哈希、人工审核记录和各来源许可证/署名。

维护者可先推送源码供协作审查，不等于公开发布词包。正式 Release 资产的最终 SHA-256 必须以通过上述门禁后重新生成的清单为准。用户自定义标签、单词本和朗读缓存不属于公共只读词包。
