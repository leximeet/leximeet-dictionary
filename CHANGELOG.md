# 更新日志

本日志记录词遇共享词典项目自身的变化。上游词典的数据版本与构建产物由 `sources.lock.json` 和构建 manifest 记录。

## 0.0.1 发布候选（未公开发布）

### 新增

- Python 标准库流式构建器，固定并校验 open-dictionary v2.0 distribution/audit、ECDICT、CMUdict 和 Open English WordNet 2025 输入；生成完整 JSONL、5,000 词核心 JSONL、只读 SQLite 与双版本安装清单。
- 同版 audit 按 entry_id 与词性/词源/义项数校验后补英文原义、标签和 IPA；ECDICT 中文只作为词条级回退；WordNet 概念网络独立存储，CMUdict ARPAbet 不冒充 IPA。
- Commons 高频离线录音核权工具、无音频版按需缓存工具、逐文件署名与 SHA-256；音频与词典语义版分离。
- 提供两份完整、可重复打包的 `tar.gz` 候选归档和 `release-candidate.json` 校验清单。
- 生成覆盖率报告和 200 条分层人工复核工作表；补齐数据许可、使用说明及中文迭代文档。

### 已知发布门禁

- ECDICT 历史字段权利、200 条人工语义复核及桌面/插件真实安装、离线、升级和回滚尚未验收。当前清单保持 `candidate-needs-license-and-human-review`。

## 初始设计基线

### 新增

- 建立 ECDICT、Wiktextract、Open English WordNet、open-dictionary、CMUdict 五个固定 Git 子模块引用。
- 写出中文项目 README、上游数据审计及加工词典格式草案。
- 约定词典数据、用户单词本与音频文件分别管理，并明确许可证、来源和哈希门禁。
- 补充 qwerty → kajweb → 原始词书的来源链、在线有道发音与独立重建词典的许可边界。
- 固定 qwerty-learner、DictionaryByGPT4、Aictionary 的研究修订与本地数据哈希，记录尚未锁定的 Release/dump 工件。
- 完成共享词典设计基线、标签作用域、跨版本 ID 规则及分阶段实施与验收任务。
