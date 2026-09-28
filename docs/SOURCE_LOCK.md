# 上游版本锁定与数据工件门禁

核查日期：2026-09-28。本文固定本轮设计所依据的仓库修订和候选数据版本。仓库 commit、发布标签、实际下载的文件哈希是三个不同层次；只有拿到文件并复算 SHA-256 后，才称该数据输入“可复现锁定”。本文件不授权任何未经审查的数据再分发。机器可读的审计快照在 [sources.lock.json](../sources.lock.json)；当前构建器尚不存在，不能把该 JSON 当作已生效的下载/发布门禁。

## A. 已固定的仓库修订

前五项是本仓库已经提交的 Git 子模块指针，构建时应使用 Git 记录的 gitlink，而不是运行时跟随上游默认分支。后三项是本地 reference/resource 快照，只用于审计和可选模块设计；它们不参与默认公开词包的构建，也未作为子模块引入。

| 来源 | 固定修订 | 角色 | 当前状态 |
| --- | --- | --- | --- |
| ECDICT | bc015ed2e24a7abef49fc6dbbb7fe32c1dadaf8b | 英汉回退、显式考试标签 | 子模块已锁 |
| Wiktextract | 1a05e46f9efbccda6a2b2f8e21b30a9c0c46513a | 提取工具及字段契约 | 子模块已锁；不等于已锁原始 dump |
| open-dictionary | 647df7a33e211a03014b6647f7832b0b183911b3 | 主词卡契约与管线参考 | 子模块已锁 |
| Open English WordNet | bff3181fe5c810dcd157cba0eed60322a6e0aaed | 语义网络源码参考 | 子模块已锁；正式数据版次另列 |
| CMUdict | 74790861f652b15e4ac49015a90074ad62a27690 | 美式 ARPAbet | 子模块已锁 |
| DictionaryByGPT4 | 8c9b050b653108145a94a559c816e0e499ef1627 | 可选助记内容候选 | 审计基线；默认包禁用 |
| qwerty-learner | 122acd90b4079dd040c28a14356447f6553cff83 | 词表组织与交互参考 | 审计基线；第三方词表禁用 |
| Aictionary | 00eb58cdba6626bbbd8d35ff206ed28ed67553fb | 词库下载、音频提供方参考 | 行为参考，非数据输入 |

仓库地址分别为 [ECDICT](https://github.com/skywind3000/ECDICT)、[Wiktextract](https://github.com/tatuylonen/wiktextract)、[open-dictionary](https://github.com/ahpxex/open-dictionary)、[Open English WordNet](https://github.com/globalwordnet/english-wordnet)、[CMUdict](https://github.com/cmusphinx/cmudict)、[DictionaryByGPT4](https://github.com/Ceelog/DictionaryByGPT4)、[qwerty-learner](https://github.com/RealKai42/qwerty-learner)、[Aictionary](https://github.com/ahpxex/Aictionary)。

## B. 数据工件锁定状态

| 工件 | 选定版本或本地哈希 | 本地校验与用途 |
| --- | --- | --- |
| ECDICT 的 ecdict.csv | SHA-256 1a6947e04785db63613a92e14903cdae7954f7e84860b10e68e5c7cbb3f9c3cf | 已对本地子模块文件计算；可用于基线导入，发布前仍需字段来源审计 |
| CMUdict 的 cmudict.dict | SHA-256 81917843c7f44ce2b094ac63873c2c7a4cf802040792c455ba3ca406891c3d22 | 已对本地子模块文件计算 |
| open-dictionary 发行版 | 选 v2.0；标签解析到 commit 53189a610287efb9ce627f9ab93409c639acdc47；契约 distribution_entry_v5 | 已锁发行标签，尚未下载 Release 文件并复算压缩文件哈希 |
| open-dictionary 的 Wiktextract 源谱系 | 上游发行说明声称快照日期 2025-10-23，raw-wiktextract-data.jsonl.gz SHA-256 dcdf2c2d5941a116d9104e3e3f118d3cc58c8488eba3d5ffee461947c3aa05a9 | 上游公布值，未取得原文件；仅作为首选同快照对齐目标 |
| open-dictionary 的非压缩 distribution.jsonl | 上游发行说明公布 SHA-256 95026a4b78aa83f1f32481e8ff30ea3f7d942b648b3d6e66ef64ca3a194cb66e | 尚未取得文件，不能代替 distribution.jsonl.gz 的哈希 |
| Open English WordNet 正式数据 | 选 2025 Edition 的核心版；[官方发布页](https://github.com/globalwordnet/english-wordnet/releases/tag/2025-edition) | 已锁版次，尚未下载指定 JSON/XML 文件并复算哈希；2025 Plus 不自动混入 |
| DictionaryByGPT4 的 gptwords.json | 本地 SHA-256 51bc73affec742690d9683f282f8944e7a191e94592ca9c7c2a317e5f92fb5d0 | 仅候选研究，逐条事实和许可审核前不入默认包 |
| qwerty-learner 的 src/resources/dictionary.ts | 本地 SHA-256 fc3b33cf8c728a69b79e8935a6cfb1aa33f046158e05167d34e288d535db8982 | 仅锁审计入口；380 个本地 JSON 词表未逐文件锁定或取得再分发授权 |
| Kaikki 当前原始提取包 | 2026-09-02 English Wiktionary dump，网页显示 2026-09-25 提取，压缩包约 2.8 GB | 与 open-dictionary v2.0 的 2025-10-23 谱系不同；未下载、未哈希、不能直接做同义项精确连接 |

open-dictionary 的 [v2.0 发行说明](https://github.com/ahpxex/open-dictionary/releases/tag/v2.0)给出词条数、原始快照哈希和非压缩分发文件哈希。[Kaikki 下载页](https://kaikki.org/dictionary/rawdata.html)持续更新，浮动 URL 不构成锁定。初次构建优先取得 v2.0 的 distribution、audit 和其原始快照；若原快照不可取得，Wiktextract 补充只能采用有证据的低置信对齐，不能把新版数据按词头直接并入旧版义项。

## C. 下一次下载后必须补齐的记录

每个进入构建的外部文件都要在 sources.lock.json 和构建清单中补齐固定 URL、发行版或 dump 日期、下载日期、字节数、压缩文件 SHA-256、解压后 SHA-256、内容许可证、所需署名及保存位置。对照上游公布的校验和后仍须本地复算。构建清单还要记录代码 commit、转换规则版本、输入文件哈希、输出文件哈希和可复现命令。

当前网络环境的 7897 与 12334 代理均未连通，因此没有下载 v2.0 的 SHA256SUMS.txt 或任何大体积 dump。目标磁盘本轮仅约有 5.7 GiB 空闲，而 Kaikki 当前原始提取包约 2.8 GB（解压约 23.9 GB）；在扩容或准备独立存储前禁止在本机获取/解压全量包。本轮没有运行词典构建，也没有生成发布包。

## D. 版本更新规则

升级任何来源时先建立新锁文件记录，检查 schema 差异和许可，再跑固定样本（bank、record、May、read、短语、缩写、罕见词）。比较词条、义项和音标的增删，生成旧到新 ID 映射，完成客户端回滚验证后才能替换默认包。不要执行浮动 latest 下载，也不要因上游 Git commit 更新就悄悄改变已发布词包。
