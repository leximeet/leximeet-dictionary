# 词遇词包分发与多端接入方案

状态：2026-09-28 的 0.0.1 本地候选。三资产已全量重建、逐个核验并在隔离目录安装抽验；手动候选流水线已写入源码，尚未运行远端 Actions、公开发布 Release，也尚未在词遇桌面端和浏览器插件完成安装、更新与回滚验收。[实际构建命令](BUILD.md)、[客户端数据契约](CLIENT_CONTRACT.md)、[维护者交接清单](RELEASE_CHECKLIST.md)和[数据说明](../DATA-LICENSE.md)分别记录现状。

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

## 0.0.1 三种独立资产

构建器现在会生成 `leximeet-dictionary-0.0.1-core.tar.gz`、`leximeet-dictionary-0.0.1-no-audio.tar.gz`、`leximeet-dictionary-0.0.1-with-audio.tar.gz` 和记录三者 SHA-256/大小的 `release-candidate.json`。两个完整包共用一套语义 schema；带发音版另含固定清单中的 436 条高频录音。新源码本地候选分别约 18 MB、433 MB、438 MB，单个文件低于 GitHub 当前每资产 2 GiB 上限；在提交构建源码并复跑最终构建前，这些仍是**本地候选而非 GitHub Release**。[GitHub Release 资产限制](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)。

独立核心包含约 5,000 词的 `core.jsonl.gz`（新构建原文件约 17.9 MB）、`core-manifest.json`、完整来源 `manifest.json`、`DATA-LICENSE.md` 和 `notices/`。它不含 SQLite 和录音，可供浏览器在安装时流式导入 IndexedDB。核心包的外层 SHA-256、内部文件哈希、schema、词条数、重复 ID 和路径安全均可由 `verify-core` 检查。桌面端选择完整 SQLite；插件端先用核心包，非核心词的扩展分片策略仍是后续工作。两端共享条目语义、来源和版本约束，不要求共享文件格式。

## 客户端安装与更新契约

1. 客户端配置固定的词典版本和所需 edition，不自动跟随 GitHub `latest`。安装清单需记录资产 URL、文件大小、SHA-256、schema 范围和本地已安装版本；候选状态不能成为生产自动安装目标。
2. 下载完整资产到临时目录；先校验外层 SHA-256、大小和归档路径，再解包。不可把未经校验的 tar 成员写到用户数据目录。
3. 按 [客户端契约](CLIENT_CONTRACT.md)复核 `edition.*.json`、`manifest.json`、SQLite 完整性和音频清单；核心包则核 `core-manifest.json` 与逐行词条。成功后原子切换只读词典版本，保留上一版用于回滚。
4. 用户笔记、标签、单词本、复习进度和按需音频缓存分别管理；词典更新不能覆盖或清空它们。缺网、下载失败或校验失败时继续使用旧版。
5. 发布者保留该版本的来源锁、完整数据许可、构建源码 commit、QA 结果和各资产 SHA-256。用户有权从词卡追溯来源和音频署名。

开发阶段可让桌面端/插件端通过本地目录读取固定样本或本地候选包做集成测试。那属于测试输入，不把尚未发布的 Release URL 写进生产配置。

## 当前 GitHub Actions 能做什么

现有 [`.github/workflows/test.yml`](../.github/workflows/test.yml) 在 `push`/`pull_request` 时运行 Python 3.11 编译与 11 项夹具测试。新增的 [`.github/workflows/candidate.yml`](../.github/workflows/candidate.yml) 只在维护者手动触发时运行：初始化 ECDICT/CMUdict 固定子模块，下载三个固定数据文件，构建器依 `sources.lock.json` 逐文件验哈希；随后全量构建、`verify`、`report`、从固定 `audio.lock.json` 重建录音并在线复查许可、生成并验证三个归档。工作流只授予 `contents: read`，**没有创建 tag、PR 或 Release 的步骤**。新远端目前只有 `LICENSE`；只有维护者将本地完成的版本推到默认分支后，GitHub 才能通过 UI 手动触发这个工作流。[GitHub 手动运行工作流规则](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)。

一次候选工作流会**构建并核验三种资产**，但每次只上传手动选择的 `core`、`no-audio` 或 `with-audio` 其中一种，连同清单和 QA 报告，保留 1 天。这是因为旧版两个完整归档合计约 869 MB，而 [GitHub Actions 当前 Free 计划每仓库 artifact 存储额度为 500 MB](https://docs.github.com/en/actions/reference/limits)；同时上传两版可能超额。正式发布若使用 Release assets，需先完成审核，再由维护者在足够空间的本机或独立 runner 生成并上传三份固定哈希资产。Actions artifact 有保留期，不能作为客户端长期下载 URL；[Release assets](https://docs.github.com/en/rest/releases/assets)才是版本化分发入口。CI 成功不等同于 200 条人工词义复核、音频署名抽查或真实客户端验收。当前工作流只完成本地静态和夹具验证，远端首次运行仍待维护者推送后验证。

## 仓库重建后的本地迁移

新远端 `main` 的初始提交为 `ef991030b4322799d0f7279c2b0e8fbd3ce4709c`，仅有与旧仓库相同的 GPL-3.0 `LICENSE`。词典历史已按顺序迁移到从这个新提交派生的本地分支 `codex/dictionary-v0.0.1-recreated`，可正常快进到新仓库历史；旧工作树和其中的个人文件未覆盖。迁移完成并不代表用户已推送，也不代表 0.0.1 Release 已具备发布条件。
