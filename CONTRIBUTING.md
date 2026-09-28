# 参与贡献

欢迎修正词义、来源、发音或构建脚本。词典数据变更请同时给出**词头、`entry_id`、原字段、建议内容和可核查来源**；发音问题请说明音频索引中的 `kind`、`style` 与问题词。不要直接修改生成的 `build/`、`dist/` 文件。

代码改动保持简单、附中文注释，并运行 `python3 -m unittest discover -s tests -v`。影响词包格式时同步更新 [客户端协议](docs/CLIENT_CONTRACT.md)、[构建说明](docs/BUILD.md)与 [CHANGELOG.md](CHANGELOG.md)。新数据源应先记录固定版本、文件哈希、许可与逐字段用途，再进入构建器。

公开问题可使用 GitHub Issue；安全漏洞请按 [SECURITY.md](SECURITY.md) 私下报告。维护者会在核对证据后合并或修订贡献。
