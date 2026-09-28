# 上游版本锁定与数据工件门禁

核查日期：2026-09-28。本文固定 0.0.1 发布候选的仓库修订和数据版本。仓库 commit、发布标签、实际文件哈希是不同层次；已进入构建的五个数据文件均已在本地复算 SHA-256，构建器运行前逐文件核对 [sources.lock.json](../sources.lock.json)。**输入可复现不等于数据权利或语义质量已通过发布审核。**

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
| open-dictionary v2.0 distribution.jsonl.gz | 压缩 97,071,330 bytes；SHA-256 69af69cdc685b5dce465613d1cc8fffb598eb46714f57cf73bd6606c2ceb7e43；流式解压 366,537,907 bytes，SHA-256 95026a4b78aa83f1f32481e8ff30ea3f7d942b648b3d6e66ef64ca3a194cb66e | 已下载并本地复算，和上游 SHA256SUMS 一致；发行标签解析到 53189a610287efb9ce627f9ab93409c639acdc47 |
| open-dictionary v2.0 audit.jsonl.gz | 压缩 148,028,969 bytes；SHA-256 e3eadd2d0029423ef7130e3bb6890e2f6cb316c64c2e935c479fe6dcb872340b；流式解压 625,376,982 bytes，SHA-256 1b6a1b82750320491d50d5204236e26295afe3b1b92fd8d37e518ce456a82ab4 | 已下载并本地复算，和上游 SHA256SUMS 一致；只提取短原义、标签、读音及音频线索，不复制历史引文 |
| open-dictionary 的 Wiktextract 源谱系 | 上游发行说明声称快照日期 2025-10-23，raw-wiktextract-data.jsonl.gz SHA-256 dcdf2c2d5941a116d9104e3e3f118d3cc58c8488eba3d5ffee461947c3aa05a9 | 上游公布值，未取得原文件；仅作为首选同快照对齐目标 |
| open-dictionary 的非压缩 distribution.jsonl | 上游发行说明公布 SHA-256 95026a4b78aa83f1f32481e8ff30ea3f7d942b648b3d6e66ef64ca3a194cb66e | 对压缩包流式解压本地复算一致，未单独落盘；该哈希仍不能代替 gzip 文件哈希 |
| Open English WordNet 正式数据 | `english-wordnet-2025-json.zip`，9,986,555 bytes；SHA-256 7d749f6e2c39e6970e4997839dcf6e42fd281f3c2fae0171d2192bae8cfa4b51；[官方发布页](https://github.com/globalwordnet/english-wordnet/releases/tag/2025-edition) | 2025 Edition 核心版已下载并本地复算；2025 Plus 不混入 |
| DictionaryByGPT4 的 gptwords.json | 本地 SHA-256 51bc73affec742690d9683f282f8944e7a191e94592ca9c7c2a317e5f92fb5d0 | 仅候选研究，逐条事实和许可审核前不入默认包 |
| qwerty-learner 的 src/resources/dictionary.ts | 本地 SHA-256 fc3b33cf8c728a69b79e8935a6cfb1aa33f046158e05167d34e288d535db8982 | 仅锁审计入口；380 个本地 JSON 词表未逐文件锁定或取得再分发授权 |
| Kaikki 当前原始提取包 | 2026-09-02 English Wiktionary dump，网页显示 2026-09-25 提取，压缩包约 2.8 GB | 与 open-dictionary v2.0 的 2025-10-23 谱系不同；未下载、未哈希、不能直接做同义项精确连接 |

open-dictionary 的 [v2.0 发行说明](https://github.com/ahpxex/open-dictionary/releases/tag/v2.0)给出词条数、原始快照哈希和非压缩分发文件哈希。[Kaikki 下载页](https://kaikki.org/dictionary/rawdata.html)持续更新，浮动 URL 不构成锁定。初次构建优先取得 v2.0 的 distribution、audit 和其原始快照；若原快照不可取得，Wiktextract 补充只能采用有证据的低置信对齐，不能把新版数据按词头直接并入旧版义项。

## C. 已完成输入锁定与仍需的发布证据

已启用的五个输入在 sources.lock.json 中有路径/URL、字节数、SHA-256 与许可线索，构建清单回填输入/输出文件哈希。Release 发布前仍要记录构建源码 commit、验证 200 条分层样本并得出 ECDICT 字段级再分发结论；当前清单会明确标记为候选状态。

7897 与 12334 代理未连通，使用直连取得 v2.0 的校验和、distribution/audit 压缩包及 WordNet 核心 ZIP，并已完成本地全量构建。Kaikki 当前原始提取包约 2.8 GB（解压约 23.9 GB），与 v2.0 的 2025-10-23 谱系不同，受磁盘和对齐证据限制未纳入 0.0.1；同版 audit 提供所需的原义和读音补充。构建产物留在忽略目录，尚未公开发布。

## D. 版本更新规则

升级任何来源时先建立新锁文件记录，检查 schema 差异和许可，再跑固定样本（bank、record、May、read、短语、缩写、罕见词）。比较词条、义项和音标的增删，生成旧到新 ID 映射，完成客户端回滚验证后才能替换默认包。不要执行浮动 latest 下载，也不要因上游 Git commit 更新就悄悄改变已发布词包。
