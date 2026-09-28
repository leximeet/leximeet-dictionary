# 从源码构建与核验 0.0.1

构建脚本需要 Python 3.11+；批量音频还需要与 [audio-tools.lock.json](../audio-tools.lock.json) 一致的 eSpeak NG 1.52.0、opus-tools 0.2 / libopus 1.6.1。所有上游输入由 [sources.lock.json](../sources.lock.json) 固定哈希。本页的本地命令是故障排查和离线复核用；正式发版可交给手动 GitHub Action。命令在仓库根目录执行；`build/` 和 `dist/` 被 Git 忽略。构建器不会覆盖已有输出目录。

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

## 4. 在 GitHub Actions 构建并发布

本地 `main` 上已经准备好 `v0.0.1` tag 后，由维护者推送代码和 tag：

```bash
git push origin main
git push origin v0.0.1
```

等待 `Dictionary tests` 通过，再在 GitHub 仓库的 **Actions → Build 0.0.1 dictionary draft → Run workflow** 中选 `main` 手动运行。工作流从远端 `v0.0.1` tag 检出源码，下载并按哈希验证固定数据，核权 436 条真人录音，生成所有核心词音频，构建 `core` 和 `full`，深检两个词包，最后上传 `release.json` 与全部分片到 **草稿 Release**。它不会推送代码、打 tag 或正式发布。维护者检查运行日志、草稿资产与抽样音质后，在 GitHub 页面发布草稿。正式 Release 出现前，其他项目不要依赖该下载地址。

这条流水线使用标准 `macos-15-intel` 运行器，受 GitHub 单次任务 6 小时和运行器磁盘限制；音频工具版本若与 `audio-tools.lock.json` 不同会立即停止，不会悄悄换声线。**流水线配置已写入仓库，远端实际运行要等维护者推送后才能验证。**失败时可以用本页 1–3 节在本地构建并复核，排查原因后重新运行；已有草稿 Release 不会被自动覆盖。

不要把约 1.74 GB 的完整版放进 Actions artifact：GitHub Free 组织的 artifact 存储额度为 500 MB，而 [Release](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases) 单文件上限 2 GiB、总量没有相同限制。本项目按不超过 256 MiB 切分大文件。正式发布后，端侧按 [客户端接入协议](CLIENT_CONTRACT.md) 获取固定版本的 `release.json`，以其中的哈希和大小为准。需要手动上传本地已核验词包时，可参考 [GitHub CLI `gh release create`](https://cli.github.com/manual/gh_release_create)；这只是流水线失败时的备选路径。
