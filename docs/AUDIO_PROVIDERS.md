# 0.0.1 无音频版：按需朗读与免费音频来源

核查日期：2026-09-28。本文面向词遇桌面端和浏览器插件，解释“不随词典打包录音”之后怎样播放、何时可以落盘缓存，以及微软、有道等服务的实际边界。价格、配额和服务条款会变化，接入前应再次打开文末官方页面核对。本文是提供方选型和接入契约；当前仓库真正实现并测试的在线提供方只有 Wikimedia Commons。

## 先明确三种不同的能力

- 真人录音：一个具体媒体文件，须分别确认文件作者、许可、词头、地区、词性及格式。只有文件本身的许可允许复制时才可放进离线包或持久缓存。
- 在线 TTS：把文本请求给服务，生成合成音频。API 能返回 MP3，不等于允许把 MP3 长期保存、公开再分发，或把服务密钥放进开源客户端。
- 系统朗读：浏览器或操作系统直接把文本读出来。它可能不需要词遇自己的服务器和音频包，但通常不给应用音频字节，不能把“播放过”当成“已缓存一个可复用的文件”。

无音频版仍有本地词卡、IPA、CMUdict 音素及 Commons 候选线索；只有点击朗读时才查找录音或调用系统语音。断网时未缓存的真人录音可以不可用，但查词绝不能失败。缓存属于每个客户端的私有运行目录，不进入只读公共词典，也不与用户笔记、单词本和复习记录混放。

## 提供方结论

| 提供方 | 成本与鉴权 | 能否用作词遇的持久音频缓存 | 0.0.1 建议 |
| --- | --- | --- | --- |
| Wikimedia Commons 文件 + MediaWiki Action API | 免费查询，无应用密钥；须遵守接口礼仪与单文件许可 | 对许可适用、署名完整且经核验的文件可以下载并缓存 | 默认真人录音来源；仓库已实现 |
| Web Speech API / 设备 TTS | 通常无词遇侧 API 费用；音色及是否本地取决于设备和浏览器 | 标准 speechSynthesis 接口不输出文件字节，不能作为持久文件缓存来源 | 用户点击后的合成语音备选 |
| Azure AI Speech F0 | 官方定价页列神经 TTS 每月 50 万字符免费额度及 F0 限流，需 Azure 资源与鉴权 | 产品条款将预置神经语音输出的使用授权明确写给付费层客户；不能把 F0 输出当作可随意缓存、再分发的开源数据 | 仅用于评估；不作为默认公开产品缓存 |
| Azure AI Speech 付费层 | 按资源/地区计费，需密钥或令牌 | 产品条款允许付费层客户使用预置神经语音输出；具体缓存、展示及再分发方式仍须依所选合同和条款核对 | 可选商业提供方，经服务端代理接入 |
| 有道智云标准 TTS / 词典发音 | 应用 ID/密钥；新账户有 50 元体验资金，之后按成功调用计费 | 通用服务条款第 9.2 节限制未经许可缓存、再利用服务数据；不能默认实现“查一次长期缓存” | 不接入默认缓存链；取得明确许可后再评估 |
| Free Dictionary API | 公共免费查询接口；返回的音频可能来自不同域名 | API 免费和代码开源不足以证明每条音频的再分发权；项目示例曾返回第三方音频域名 | 仅作发现线索；须回溯到有许可的原始文件 |
| Edge Read Aloud / 社区 Edge TTS 接口 | Edge 浏览器功能；社区实现通常调用未作为开发者公共服务承诺的路径 | 未找到官方面向第三方的稳定、可缓存的免费发音 API 许可 | 不作为发布版依赖 |

依据：[Commons 复用指南](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia/en)、[MediaWiki imageinfo](https://www.mediawiki.org/wiki/API:Imageinfo)、[Web Speech API 规范](https://github.com/WebAudio/web-speech-api/blob/main/index.bs)、[Azure Speech 定价](https://azure.microsoft.com/en-us/pricing/details/speech/)、[Azure Speech 配额](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/speech-services-quotas-and-limits)、[微软产品条款](https://www.microsoft.com/licensing/terms/en-US/productoffering/MicrosoftAzure/allprograms)、[有道 TTS 定价](https://ai.youdao.com/DOCSIRMA/html/tts/price/yyhc/index.html)、[有道服务条款](https://ai.youdao.com/DOCSIRMA/html/agreement/terms/ydzyfwkt/index.html)、[Free Dictionary API 项目](https://github.com/meetDeveloper/freeDictionaryAPI)。Edge 行是对上述官方开发文档范围的判断，不把“未找到”说成技术上永远不能访问。

## 默认路径：Commons 真人录音按需核权并缓存

当前数据库的 audio_candidates 保存来自同版审计数据的线索，不是已授权文件。点击朗读时，先按词头、地区和词性筛选文件名，再用 Commons Action API 的 imageinfo 取得实际媒体 URL、大小、MIME 与扩展元数据。查询例子：

~~~sh
curl -G 'https://commons.wikimedia.org/w/api.php' \
  --data-urlencode 'action=query' \
  --data-urlencode 'format=json' \
  --data-urlencode 'formatversion=2' \
  --data-urlencode 'prop=imageinfo' \
  --data-urlencode 'iiprop=url|size|mime|extmetadata' \
  --data-urlencode 'titles=File:En-us-bank.ogg'
~~~

真正下载前至少检查：LicenseShortName 在允许的开放许可中，LicenseUrl 指向相应许可文本，Artist 不为空，Restrictions 不含不适用限制，descriptionurl 可追溯，MIME 是客户端支持的音频，字节数处于限制内，最终 URL 仍在 Commons 媒体域。下载后复算 SHA-256，并把作者、许可名/链接、文件页、地区、词性、媒体 URL、字节数和哈希写到缓存元数据。Commons 明确提醒单文件许可不同，网站并不保证上传者填写的版权信息绝对正确，因此公开音频包仍需人工抽查。[官方复用指南](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia/en)及[imageinfo 参数](https://www.mediawiki.org/wiki/API:Imageinfo)。

仓库现有的 Python 演示命令会执行上述按需核权、下载和缓存：

~~~sh
python3 -m leximeet_dictionary cache-audio --db build/v0.0.1/dictionary.sqlite --cache audio-cache --region en-US bank
~~~

同一个词再次点击时先校验缓存文件的 SHA-256 再复用。词性或地区不明确时，不能把名词录音贴到动词义项，也不能把不明地区录音标为美音。没有匹配录音就返回“无可用真人录音”，继续尝试设备 TTS，不影响离线释义。当前实现只接受保守文件名匹配及一组白名单许可，覆盖率因此不是 100%。

## 免费设备朗读：Web Speech API

浏览器插件及支持 Web Speech API 的桌面 WebView 可以在用户点击后调用 speechSynthesis；例如：

~~~js
const utterance = new SpeechSynthesisUtterance(word);
utterance.lang = "en-US";
utterance.rate = 1;
const voices = speechSynthesis.getVoices();
const local = voices.find(voice => voice.lang === "en-US" && voice.localService);
const matching = voices.find(voice => voice.lang === "en-US");
if (local || matching) utterance.voice = local || matching;
speechSynthesis.speak(utterance);
~~~

音色列表可能异步到达，客户端须处理 voiceschanged；用户切换英式/美式时重新选 voice。localService=true 表示该声音由本地合成器提供，但并不承诺每台设备都有该声音。浏览器标准 API 提供播放控制而非音频文件或 Blob 导出，因此不要为它设计“保存合成 MP3”的缓存命中逻辑。UI 应标“合成语音”，与真人录音区分。[规范接口](https://github.com/WebAudio/web-speech-api/blob/main/index.bs)、[MDN 用法](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesisUtterance)、[localService 含义](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesisVoice/localService)。

## 微软 Azure AI Speech：怎样接，为什么免费层不作默认缓存

官方 REST 接口是 POST https://{region}.tts.speech.microsoft.com/cognitiveservices/v1，请求正文为 SSML，Content-Type 为 application/ssml+xml，用 X-Microsoft-OutputFormat 指定音频格式，例如 audio-16khz-32kbitrate-mono-mp3。先创建 Speech 资源并确认地区、音色、配额；区域不匹配会认证失败。服务端保管资源密钥，可向 POST https://{region}.api.cognitive.microsoft.com/sts/v1.0/issueToken 发送 Ocp-Apim-Subscription-Key 换取有效期约 10 分钟的 Bearer 令牌，再由受控服务调用 TTS。不要把长期资源密钥硬编码到开源桌面端或浏览器插件。示意请求：

~~~http
POST /cognitiveservices/v1 HTTP/1.1
Host: {region}.tts.speech.microsoft.com
Authorization: Bearer <short-lived-token>
Content-Type: application/ssml+xml
X-Microsoft-OutputFormat: audio-16khz-32kbitrate-mono-mp3
User-Agent: LexiMeet

<speak version="1.0" xml:lang="en-US"><voice name="en-US-ChristopherNeural">bank</voice></speak>
~~~

成功返回音频字节；401 检查资源、地区和令牌，429 做限流/退避，网络失败保持离线查词。生产端点和可用音色以资源地区的官方列表为准。REST 细节见[微软官方接口](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/rest-text-to-speech)；F0 当前为每月 50 万神经 TTS 字符及每 60 秒最多 20 次标准语音请求，见[定价](https://azure.microsoft.com/en-us/pricing/details/speech/)与[配额](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/speech-services-quotas-and-limits)。

关键许可边界是[微软产品条款中的 TTS Service output use rights](https://www.microsoft.com/licensing/terms/en-US/productoffering/MicrosoftAzure/allprograms)：预置神经语音输出的使用授权写明“仅付费层客户”。所以 F0 的免费调用额度不应被解释为给词遇公开产品永久缓存、打包或再分发音频的授权。若以后选择付费层，还须核对具体订阅合同、语音及地区条款，并在产品中清楚标注合成语音；微软的[AI 服务行为准则](https://learn.microsoft.com/en-us/legal/cognitive-services/speech-service/text-to-speech/code-of-conduct)要求适当披露合成性质。

## 有道智云：可试用，但默认缓存链不适用

[官方语音合成 API](https://ai.youdao.com/DOCSIRMA/html/tts/api/yyhc/index.html) 为 POST https://openapi.youdao.com/ttsapi，表单包括 q、appKey、salt、curtime、signType=v3、sign、voiceName、format 等字段。签名是 SHA-256(appKey + input + salt + curtime + appSecret)；q 长度不超过 20 时 input=q，否则用 q 前 10 字符 + q 长度 + 后 10 字符。官方把 youmeimei / youyingying 分别列为词典美音 / 英音，把 youxiaomei / youxiaoying 列为普通英文美音 / 英音；具体费用还取决于输入是否在有道词典识别范围内。服务端调用的请求形状如下，尖括号值均为运行时生成或从密钥存储中读取，不可提交进仓库：

~~~http
POST /ttsapi HTTP/1.1
Host: openapi.youdao.com
Content-Type: application/x-www-form-urlencoded

q=bank&appKey=<app-id>&salt=<uuid>&curtime=<unix-seconds>&signType=v3&sign=<sha256>&voiceName=youmeimei&format=mp3
~~~

签名中的 q 使用原文；发送表单前再对各字段 URL encode。成功时返回 audio/mp3，失败时返回 application/json 和错误码。密钥只能放在受控服务端；客户端不得直接构造带密钥的请求。

[官方标准 TTS 价目表](https://ai.youdao.com/DOCSIRMA/html/tts/price/yyhc/index.html)列新账户 50 元体验资金，并将“英文词典发音”与一般在线语音合成分别计费；首档分别为 0.0012 元/次和 0.012 元/次。词典未收录的输入可能回退到一般语音合成并按相应价格计费。它是有额度的试用和按量收费服务，不是无限免费 API。

更重要的是，[有道智云服务条款第 9.2 节](https://ai.youdao.com/DOCSIRMA/html/agreement/terms/ydzyfwkt/index.html)限制未经书面许可缓存或再利用 API/服务数据。第 9.5 节对某些生成内容的权利归属有说明，但不能单凭它忽略第 9.2 节的缓存限制。另一个[有道少儿词典 API](https://ai.youdao.com/DOCSIRMA/html/dictionary/api/secd/index.html)虽然可返回发音，却更明确写明返回数据严禁缓存、再利用。因此不能用网页词典的非官方发音地址绕开正式 API 和条款；如果以后要用有道，须先取得适用于本产品缓存方式的明确许可，再实现单独的可关闭提供方。

## 其他公共查询接口与 Edge

[Free Dictionary API 项目](https://github.com/meetDeveloper/freeDictionaryAPI)可按 https://api.dictionaryapi.dev/api/v2/entries/en/bank 查询并得到音标与某些 audio URL；其项目示例出现过第三方 gstatic 音频链接。该 API 的免费访问不等于它返回的所有录音都有相同许可。词遇可将其中指向明确 Commons 文件页的结果重新用 Commons 许可流程核对，不把未知来源 URL 缓存进官方包。

Microsoft Edge 的 Read Aloud 是浏览器功能。微软面向 Web 开发者说明的语音接口是[Web Speech API](https://learn.microsoft.com/en-us/microsoft-edge/dev-guide/multimedia/web-speech-api)，可购买使用的云接口是[Azure AI Speech](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/rest-text-to-speech)。未查到将 Edge 内部朗读服务承诺给第三方开源应用长期调用、缓存与再分发的官方免费 API；因此不把社区反向实现视为稳定公共服务。这是目前文档证据下的选型判断。

## 客户端提供方与缓存契约

建议一次点击采用以下顺序：

1. 带音频版：先取已安装并通过哈希校验的离线素材；无音频版跳过。
2. 查客户端私有缓存，仅复用来源许可允许、元数据齐全、哈希正确且版本匹配的文件。
3. 向 Commons 查询并核验同一词头、地区、词性对应的录音；成功后缓存。
4. 若用户启用了设备 TTS，选择符合地区的 voice 播放，UI 标为“合成语音”；不伪造文件缓存。
5. 若以上都失败，仅提示本次无法朗读；离线词卡继续可用。未来付费、明确获权的提供方可以在第 3 步之后作为用户可选项。

AudioResult 至少区分 file / system-tts / unavailable；文件型结果需带 provider、entry_id、text、region、part_of_speech、voice_or_file、media_type、bytes、sha256、source_page、artist、license_name、license_url、cache_policy 和 provider_version。文件缓存键包含文本、地区、提供方、音色或文件、语速、版本；元数据与文件同生命周期，UI 应能展示署名与清理缓存。在线请求仅由用户朗读动作触发，不随词卡预取，避免成本、流量及不必要的服务日志。

发布/验收要覆盖：没网时查词仍成功；缓存命中不联网且复算哈希；错误地区、词性和未知许可不误播；设备无音色时正常退回；401/429/超时不导致词典崩溃；客户端清理缓存不删除用户单词本；浏览器及桌面端展示来源、许可和合成标记。当前 Python 实现只覆盖 Commons 路径及其单元测试；Web Speech、Azure、有道的客户端集成均尚未实现或验收。
