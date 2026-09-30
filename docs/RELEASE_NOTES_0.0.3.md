# LexiMeet Dictionary 0.0.3

提供五种共享资产的组合：lite-text、lite-audio、core-text、core-audio、full-text。lite 有 26,417 词，无音频版下载大小为 45.84 MB，带音频版为 99.95 MB；两个 lite 包均严格小于 100 MB。所有大小包含清单、来源和许可文件，以十进制 MB 计，精确值见随包 release.json。

- lite 保留全部 23 个学习目录成员和固定高频功能词，再按历史词频补入能容纳的词；每个入选词保留完整词卡。
- core 保留 117,902 个核心词，full-text 保留 811,092 个词。core 的考试／专业目录和已有助记沿用 0.0.2。
- lite-audio 和 core-audio 都逐词附带离线录音；full-audio 的全词音频留到 1.0.0。
- 词卡和音频按层复用，非核心词只作为差量分片下载。取消下载重复的学习数据库，由消费端建立本地查询索引。
- 新清单使用 leximeet.release.v3；每片提供大小和 SHA-256。参考安装器支持缓存复用、损坏重下与安装失败回退。

完整使用说明见[词包与接入](https://github.com/leximeet/leximeet-dictionary/blob/v0.0.3/docs/PACKAGES_0.0.3.md)。旧版本继续使用各自清单；不要用新版组合名读取 0.0.1/0.0.2 的资产。
