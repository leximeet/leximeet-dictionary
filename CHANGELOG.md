# 更新日志

本日志记录词遇共享词典项目自身的变化。上游词典的数据版本与构建产物由 `sources.lock.json` 和构建 manifest 记录。

## 0.0.1 发布候选（未公开发布）

### 新增

- Python 标准库流式构建器，固定并校验 open-dictionary v2.0 distribution/audit、ECDICT、CMUdict 和 Open English WordNet 2025 输入；生成完整 JSONL、5,000 词核心 JSONL、只读 SQLite 与双版本安装清单。
- 同版 audit 按 entry_id 与词性/词源/义项数校验后补英文原义、标签和 IPA；ECDICT 中文只作为词条级回退；WordNet 概念网络独立存储，CMUdict ARPAbet 不冒充 IPA。
- 修复主词源过滤高频 article/conj 造成的缺义项：从已固定逐词 Kaikki 原始记录提取 34 个功能词、161 条英文义项及标签，保留原始 URL/文件哈希/位置；只补缺失词性，不跨快照自动对齐，中文仍为 ECDICT 词条级回退。
- Commons 高频离线录音核权工具、无音频版按需缓存工具、逐文件署名与 SHA-256；旧候选的 454 条录音中排除 18 条作者仅靠推定的文件，剩余 436 条写入固定 `audio.lock.json`，在线重建会复查当前许可。
- 提供浏览器核心、完整无音频、完整带发音三份独立、可重复打包的 `tar.gz` 候选归档和 `release-candidate.json` 校验清单；增加流式完整归档核验与核心词条核验。
- 增加只读权限、手动触发的候选构建 GitHub Actions 工作流；每次构建并验证三份资产，按额度选择上传其中一份和 QA 报告，不自动发布。
- 生成覆盖率报告、至少 200 条词义（含功能词）和 40 条录音的分层人工复核工作表；补齐数据许可、使用说明及中文迭代文档。
- 新源码全量重建得到 811,092 条词条、241,427 条策展义项和 436 条固定录音；逐行深度校验 JSONL/SQLite 与三归档，完成隔离目录安装抽验。

### 文档补充

- 核对 Commons、Web Speech API、微软 Azure AI Speech、有道智云和 Free Dictionary API 的官方接口、价格及缓存条款，补充无音频版按需朗读的接入文档；说明 ECDICT 仓库开源与第三方数据权利链的区别。
- 记录维护者选定的 ECDICT 署名及权利通知处理方式；以固定提交分析 Aictionary、qwerty-learner、Read Frog、Pot 的按需朗读实现；明确多端以版本化 Release 资产消费词包、源码开发才使用 Git 引用。
- 在重建仓库的新 `main` 上迁移词典历史；将新构建候选标记为 `candidate-needs-human-review`，把现有测试工作流限制为只读权限，并记录独立核心资产和候选构建流水线任务。

### 已知发布门禁

- 200 条人工语义复核、40 条录音抽查、远端手动 CI 首跑、桌面/插件真实安装与更新回滚尚未验收。新源码候选为 `candidate-needs-human-review`，不自动发布或供生产客户端安装。

## 初始设计基线

### 新增

- 建立 ECDICT、Wiktextract、Open English WordNet、open-dictionary、CMUdict 五个固定 Git 子模块引用。
- 写出中文项目 README、上游数据审计及加工词典格式草案。
- 约定词典数据、用户单词本与音频文件分别管理，并明确许可证、来源和哈希门禁。
- 补充 qwerty → kajweb → 原始词书的来源链、在线有道发音与独立重建词典的许可边界。
- 固定 qwerty-learner、DictionaryByGPT4、Aictionary 的研究修订与本地数据哈希，记录尚未锁定的 Release/dump 工件。
- 完成共享词典设计基线、标签作用域、跨版本 ID 规则及分阶段实施与验收任务。
