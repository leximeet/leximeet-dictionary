# 构建与校验 0.0.1

需要 Python 3.11+；构建器仅使用标准库。代码和小型审校文件在 Git 中，大型上游数据按 `sources.lock.json` 固定字节数与 SHA-256。下列命令在仓库根目录执行，输出位于被 Git 忽略的 `build/`、`dist/`。

1. 初始化 ECDICT、CMUdict 子模块，下载 `sources.lock.json` 中指定的 open-dictionary v2.0 `distribution.jsonl.gz`、`audit.jsonl.gz` 和 Open English WordNet 2025 ZIP。不能用浮动的 latest 替换固定文件。

    mkdir -p downloads/open-dictionary/v2.0 downloads/english-wordnet/2025
    curl -fL https://github.com/ahpxex/open-dictionary/releases/download/v2.0/distribution.jsonl.gz -o downloads/open-dictionary/v2.0/distribution.jsonl.gz
    curl -fL https://github.com/ahpxex/open-dictionary/releases/download/v2.0/audit.jsonl.gz -o downloads/open-dictionary/v2.0/audit.jsonl.gz
    curl -fL https://en-word.net/static/english-wordnet-2025-json.zip -o downloads/english-wordnet/2025/english-wordnet-2025-json.zip
2. 构建并深度校验。构建器会逐个检查输入哈希；已提交的 `sources/function-words.jsonl` 和 `editorial/corrections.json` 也参与构建。

    git submodule update --init upstream/ecdict upstream/cmudict
    python3 -m leximeet_dictionary build --distribution downloads/open-dictionary/v2.0/distribution.jsonl.gz --audit downloads/open-dictionary/v2.0/audit.jsonl.gz --ecdict upstream/ecdict/ecdict.csv --cmudict upstream/cmudict/cmudict.dict --wordnet downloads/english-wordnet/2025/english-wordnet-2025-json.zip --out build/v0.0.1-final
    python3 -m leximeet_dictionary verify build/v0.0.1-final --deep
    python3 -m unittest discover -s tests -v

3. 需要带发音包时，从 `audio.lock.json` 重建并验证 436 条录音。联网模式会再次核对 Commons 的作者与许可；本地 `--source-dir` 只复用哈希相同的字节，不能代替在线权利复核。

    python3 -m leximeet_dictionary audio-pack-locked --db build/v0.0.1-final/dictionary.sqlite --out build/v0.0.1-final/audio --audio-lock audio.lock.json --sources-lock sources.lock.json
    python3 -m leximeet_dictionary verify-audio build/v0.0.1-final/audio

4. 打包、验证并导出供人阅读的全量表格。

    python3 -m leximeet_dictionary package --root build/v0.0.1-final --out dist/final
    python3 -m leximeet_dictionary verify-core dist/final/leximeet-dictionary-0.0.1-core.tar.gz
    python3 -m leximeet_dictionary verify-archive dist/final/leximeet-dictionary-0.0.1-no-audio.tar.gz
    python3 -m leximeet_dictionary verify-archive dist/final/leximeet-dictionary-0.0.1-with-audio.tar.gz
    python3 tools/export_markdown.py --db build/v0.0.1-final/dictionary.sqlite --out dist/final/leximeet-dictionary-0.0.1-details.md

`dist/final/release-candidate.json` 给出三种资产的字节数与外层 SHA-256；安装时还须验证归档成员和清单。生成目录应为空，构建器会拒绝覆盖旧数据库。包内 `release_status` 目前为 `candidate-needs-human-review`，可供集成开发；正式发布任务见 [TASKS.md](TASKS.md)。
