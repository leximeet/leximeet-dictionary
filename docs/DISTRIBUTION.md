# 词遇词包分发与多端接入方案

状态：2026-09-28 的 0.0.1 本地候选。尚未公开发布 Release，也尚未在词遇桌面端和浏览器插件完成安装、更新与回滚验收。[实际构建命令](BUILD.md)、[客户端数据契约](CLIENT_CONTRACT.md)和[数据说明](../DATA-LICENSE.md)分别记录现状。

## 选择：运行时消费 Release，源码开发才使用 Git 引用

| 方式 | 得到的内容 | 适合场景 | 本项目结论 |
| --- | --- | --- | --- |
| 把整个词典仓库设为各客户端的 Git 子模块 | 固定源码提交与上游 gitlink；仍须另取 open-dictionary Release、WordNet ZIP 并自行构建大词包 | 调试构建器、共同修改 schema 或复现加工 | 不作为桌面端/插件端安装方式 |
| 客户端直接 clone 词典仓库 | 源码、文档和子模块指针；默认没有构建好的 SQLite、核心词包或录音 | 词典维护者开发 | 不作为最终用户下载入口 |
| 从固定版本的 GitHub Release 下载资产 | 指定版本的可安装词包、音频版选择、校验清单和许可证 | 桌面端安装、插件初始化与更新、其他项目 CI | 正式分发入口；客户端锁版本与 SHA-256，不跟随 `latest` |

Git 子模块 pin 的是源码 commit，不是加工后 1.22 GB SQLite 的内容，也不包含通过 gitignore 排除的 `build/`/`dist/`。把仓库设为子模块只会让每个客户端承担上游源码与构建依赖，并不能省去产物发布。[Git 子模块说明](https://git-scm.com/book/en/v2/Git-Tools-Submodules)与[GitHub Release 定义](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)可供核对。

目标分发路径如下；图中的 Release 步骤尚未执行：

~~~mermaid
flowchart LR
    S[固定的上游 Git 提交与数据文件] --> B[词典构建器]
    B --> V[哈希、结构与人工验收]
    V --> R[维护者发布版本化 Release]
    R --> D[桌面端：完整 SQLite]
    R --> P[浏览器插件：独立核心分片]
    D --> U[用户单词本独立保存]
    P --> U
~~~

## 0.0.1 已有的资产与尚缺的分片

构建器已经能生成 `leximeet-dictionary-0.0.1-no-audio.tar.gz`、`leximeet-dictionary-0.0.1-with-audio.tar.gz` 和 `release-candidate.json`。两个 tar.gz 各自是完整安装包，共用一套语义 schema；带发音版另含高频录音清单与文件。旧版全量本地构建分别约 432 MB、437 MB，单个文件低于 GitHub 当前每资产 2 GiB 上限，但它们现在仍是**本地候选，不是 GitHub Release**。[GitHub Release 资产限制](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)。

`core.jsonl.gz` 已由构建器生成约 5,000 词、旧版约 17.7 MB，却仍包在上述两个完整归档内。浏览器插件若只需要核心词，不应为了取得这一个文件下载 432 MB。正式发布前需要新增独立、带同版 manifest 和许可证的核心分片，或设计可按需获取的完整扩展分片；此功能**尚未实现**。桌面端可以选择完整 SQLite；插件端从核心分片导入 IndexedDB，之后按需安装更大分片。两端共享条目语义、来源和版本约束，不要求共享文件格式。

## 客户端安装与更新契约

1. 客户端配置固定的词典版本和所需 edition，不自动跟随 GitHub `latest`。安装清单需记录资产 URL、文件大小、SHA-256、schema 范围和本地已安装版本。
2. 下载完整资产到临时目录；先校验外层 SHA-256、大小和归档路径，再解包。不可把未经校验的 tar 成员写到用户数据目录。
3. 按 [客户端契约](CLIENT_CONTRACT.md)复核 `edition.*.json`、`manifest.json`、SQLite 完整性和音频清单；成功后原子切换只读词典版本，保留上一版用于回滚。
4. 用户笔记、标签、单词本、复习进度和按需音频缓存分别管理；词典更新不能覆盖或清空它们。缺网、下载失败或校验失败时继续使用旧版。
5. 发布者保留该版本的来源锁、完整数据许可、构建源码 commit、QA 结果和各资产 SHA-256。用户有权从词卡追溯来源和音频署名。

开发阶段可让桌面端/插件端通过本地目录读取固定样本或本地候选包做集成测试。那属于测试输入，不把尚未发布的 Release URL 写进生产配置。

## 当前 GitHub Actions 能做什么

当前唯一工作流是 [`.github/workflows/test.yml`](../.github/workflows/test.yml)：`push` 和 `pull_request` 时使用 Python 3.11，运行 `compileall` 与 7 项夹具单元测试。它**不会**初始化数据子模块、下载固定的大型数据文件、运行全量构建或 `report`、生成两版 tar.gz、上传 Actions artifact、创建 Git tag 或发布 GitHub Release。重建后的远端目前只有 `LICENSE`；工作流也要等维护者将本地完成的版本推送后才存在于远端。

下一阶段应增加独立的**手动候选构建工作流**，只授予 `contents: read`：checkout 固定子模块，下载锁定数据并验证哈希，构建、`verify`、`report`，按需做高频录音元数据核验和 `verify-audio`，`package` 后复算归档哈希，并将候选包、清单和报告上传为 Actions artifact。不能把一次 CI 成功等同 200 条人工词义复核或真实客户端验收。只有这些门禁完成后，由维护者手动决定 Git tag、Release 和资产上传；流水线不自动发布。GitHub 的 [workflow artifacts](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflow-artifacts)用于运行间交接且有保留期，[Release assets](https://docs.github.com/en/rest/releases/assets)才适合作为客户端固定版本下载源。

## 仓库重建后的本地迁移

新远端 `main` 的初始提交为 `ef991030b4322799d0f7279c2b0e8fbd3ce4709c`，仅有与旧仓库相同的 GPL-3.0 `LICENSE`。词典历史已按顺序迁移到从这个新提交派生的本地分支 `codex/dictionary-v0.0.1-recreated`，可正常快进到新仓库历史；旧工作树和其中的个人文件未覆盖。迁移完成并不代表用户已推送，也不代表 0.0.1 Release 已具备发布条件。
