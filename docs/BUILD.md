# 从源码构建与核验 0.0.1

构建脚本需要 Python 3.11+；批量音频还需要与 [audio-tools.lock.json](../audio-tools.lock.json) 一致的 eSpeak NG 1.52.0、opus-tools 0.2 / libopus 1.6.1。所有上游输入由 [sources.lock.json](../sources.lock.json) 固定哈希。命令在仓库根目录执行；`build/` 和 `dist/` 被 Git 忽略。构建器不会覆盖已有输出目录。

## 1. 固定词典底座

```bash
git submodule update --init upstream/ecdict upstream/cmudict
mkdir -p downloads/open-dictionary/v2.0 downloads/english-wordnet/2025
curl -fL 'https://github.com/ahpxex/open-dictionary/releases/download/v2.0/distribution.jsonl.gz' -o downloads/open-dictionary/v2.0/distribution.jsonl.gz
curl -fL 'https://github.com/ahpxex/open-dictionary/releases/download/v2.0/audit.jsonl.gz' -o downloads/open-dictionary/v2.0/audit.jsonl.gz
curl -fL 'https://en-word.net/static/english-wordnet-2025-json.zip' -o downloads/english-wordnet/2025/english-wordnet-2025-json.zip

python3 -m leximeet_dictionary build \
  --distribution downloads/open-dictionary/v2.0/distribution.jsonl.gz \
  --audit downloads/open-dictionary/v2.0/audit.jsonl.gz \
  --ecdict upstream/ecdict/ecdict.csv \
  --cmudict upstream/cmudict/cmudict.dict \
  --wordnet downloads/english-wordnet/2025/english-wordnet-2025-json.zip \
  --out build/base
python3 -m leximeet_dictionary verify build/base --deep
```

输入哈希不匹配即停止；不要用上游浮动的 latest 替换固定文件。`build/base/dictionary.sqlite` 可以立即用于开发查询，但可安装的 0.0.1 版本还必须完成下列逐词音频与发包。

## 2. 离线录音

先从固定的 [audio.lock.json](../audio.lock.json) 复核并安装 436 条 Commons 真人录音。此命令联网核对当前署名和许可；若已有从相同锁生成的缓存，可用 `--source-dir <目录>` 复用文件哈希，但它不能代替首次在线权利核查。

```bash
python3 -m leximeet_dictionary audio-pack-locked \
  --db build/base/dictionary.sqlite --out build/base/audio \
  --audio-lock audio.lock.json --sources-lock sources.lock.json
python3 -m leximeet_dictionary verify-audio build/base/audio
```

其余**核心词**在本地用锁定的 `en-us` 声线生成 Ogg Opus。macOS 可用 Homebrew 安装工具，但**先检查实际版本**；若版本与锁不符，应取得锁定版本，不要静默改锁。缺少核心词音频会使构建失败。重复执行 `offline-audio` 会校验并复用已生成文件，适合中断后续跑；试产用 `--max-entries` 的部分缓存不可发包。0.0.1 不要求非核心词随包音频。

```bash
espeak-ng --version
opusenc --version
python3 -m leximeet_dictionary offline-audio \
  --db build/base/dictionary.sqlite --human-dir build/base/audio \
  --out build/audio-cache --workers 8
```

`build/audio-cache/build-result.json` 的 `target_entries` 应为 117,902，`covered_core_entries` 应为 117,902，`complete` 必须为 `true`。缓存中保留每词 SHA-256、真人/合成类型及无法直接发声时的字符拼读标记。

## 3. 分片发包与全量校验

```bash
python3 -m leximeet_dictionary release-build \
  --source build/base --audio-cache build/audio-cache \
  --out dist/v0.0.1 --shard-mib 256
python3 -m leximeet_dictionary release-verify dist/v0.0.1 --edition core --deep
python3 -m leximeet_dictionary release-verify dist/v0.0.1 --edition full --deep
python3 -m leximeet_dictionary release-assemble dist/v0.0.1 --out /tmp/leximeet-dictionary.sqlite
python3 -m unittest discover -s tests -v
```

`dist/v0.0.1/release.json` 列出两个版本及每个下载资产的精确字节数与 SHA-256。完整版复用核心音频索引与分片，另外下载 `full.dictionary.sqlite.part-*`；客户端按 `sqlite.parts` 的顺序重组并核对整个 SQLite 哈希。`release-verify --deep` 逐条检查 JSONL、核心词音频、分片字节与重组后的 SQLite。抽听时可用 `release-audio --edition core --entry-id <词条 ID> --out /tmp/sample.ogg dist/v0.0.1` 从分片提取独立文件。

本仓库没有自动推送、打 tag、创建 PR 或发布 Release 的步骤。维护者检查数据与音质后自行上传 `release.json` 及清单中全部资产；端侧按 [客户端接入协议](CLIENT_CONTRACT.md) 下载和安装。GitHub Action 负责源码测试与固定词典数据校验；全量音频和 Release 的逐片校验在发布机执行。

维护者确认本地 `main`、词包与清单后，可自行发布：

```bash
git push origin main
git tag -a v0.0.1 -m 'LexiMeet Dictionary 0.0.1'
git push origin v0.0.1
gh release create v0.0.1 dist/v0.0.1/* --verify-tag --title 'LexiMeet Dictionary 0.0.1' --notes-file CHANGELOG.md
```

`dist/v0.0.1/` 的文件是平铺的 Release 资产，`release.json` 也要一同上传；发布后不要只上传核心版而遗漏完整版分片。GitHub 的[单个 Release 资产上限为 2 GiB](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)，本项目按不超过 256 MiB 切分大文件。上述 `gh release create` 用法见 [GitHub CLI 文档](https://cli.github.com/manual/gh_release_create)。
