# 音频来源评估与合规说明

- 日期：2026-10-20
- 目标：为英文单词提供**合法、稳定、来源明确**的真人录音，并缓存到本机。
- 结论：使用 **Wikimedia Commons 官方 MediaWiki API**，只接受许可证明确的社区真人录音。

## 1. 为什么选择 Wikimedia Commons

| 条件 | 情况 |
| --- | --- |
| 合法使用 | 每个文件有独立的许可证和作者元数据，常见 Public domain、CC0、CC BY、CC BY-SA |
| 来源明确 | API 返回文件页、原始文件、许可证、作者、描述和分类 |
| 访问方式 | 官方 API，无需 API Key；媒体文件由 `upload.wikimedia.org` 提供 |
| 真人录音 | `En-us-*`、`En-uk-*`、`En-gb-*` 是社区发音文件；`LL-Q1860 (eng)-*` 来自 Lingua Libre 真人录制 |
| 稳定性 | Wikimedia 是长期运行的非营利项目；文件可能被重命名/删除，但已缓存音频仍可播放 |
| 使用限制 | 需要遵守 API 礼仪、User-Agent 政策和限流；本项目会节流、缓存并尊重 429 |

## 2. 访问方式

### API

```text
https://commons.wikimedia.org/w/api.php
```

使用的参数：

```text
action=query
format=json
formatversion=2
titles=File:En-us-hello.ogg|File:En-uk-hello.ogg|...
prop=videoinfo
viprop=url|mime|derivatives|extmetadata
```

- 先用精确文件名查询 `En-us-<word>`、`En-uk-<word>`、`En-gb-<word>` 的 OGG/WAV/MP3/FLAC 变体。
- 没有精确结果时，用 `generator=search` + `intitle:<word> filetype:audio` 做一次搜索，并只保留已知真人录音前缀。
- 每个文件通过 `extmetadata` 获取 `LicenseShortName`、`LicenseUrl`、`Artist`、`Credit`、`ImageDescription`、`Categories`。
- 通过 `derivatives` 优先选择 `audio/mpeg` 转码；没有时使用原始 OGG/WAV。
- 媒体只允许来自 `https://upload.wikimedia.org/`，拒绝其他主机，避免 SSRF。

### 传输实现

本机验证时发现：

- Python `httpx` 访问 Wikimedia API 时收到机器人策略 HTTP 403。
- Python `urllib` 经过系统代理时，代理出口被 Wikimedia 限流（HTTP 429）。
- 系统 `curl` 直连可以正常访问 API 和 MP3 转码。

因此后端：

1. 默认优先使用系统 `curl` 直连（Windows 10/11 自带 `curl.exe`）。
2. 没有 curl 时使用 `urllib` 兜底。
3. 如果网络必须走系统代理，设置 `VOCABULARY_AUDIO_USE_PROXY=1`，改用 urllib + 系统代理。
4. 不伪造浏览器 User-Agent，不绕过访问控制。

### API 礼仪与限流

- 请求带项目 User-Agent：`VocabularyAudio/0.1 (local educational project)`；分发前应补充可联系的项目地址。
- API 查询之间至少间隔 **0.5 秒**。
- 连接重置等瞬时错误最多重试 **4 次**，每次递增等待。
- HTTP 429 读取 `Retry-After`，媒体下载等待后重试一次；仍失败则返回明确错误。
- 所有成功音频落盘缓存；重复点击不再请求 Wikimedia。
- 不批量抓取、不遍历词库、不抓取 HTML 页面。

参考：

- <https://www.mediawiki.org/wiki/API:Etiquette>
- <https://foundation.wikimedia.org/wiki/Policy:User-Agent_policy>
- <https://commons.wikimedia.org/wiki/Commons:API>
- <https://commons.wikimedia.org/wiki/Commons:Licensing>

## 3. 许可过滤

只接受以下许可证（大小写不敏感）：

- Public domain / PD
- CC0
- CC BY（允许版本变体，如 CC BY 3.0 us）
- CC BY-SA（允许版本变体）

拒绝：

- CC BY-NC、CC BY-ND、NC/ND 组合
- GFDL-only（许可条款复杂，当前不纳入）
- “All rights reserved”、fair use、许可证缺失或无法识别
- 标题/描述/分类含 `text-to-speech`、`synthetic`、`espeak`、`festival tts`、`google translate`、`microsoft speech` 等合成语音标记

每个缓存的 `.json` 元数据保存：

```json
{
  "word": "hello",
  "accent": "us",
  "provider": "Wikimedia Commons",
  "title": "File:En-us-hello.ogg",
  "source_page": "https://commons.wikimedia.org/wiki/File:En-us-hello.ogg",
  "audio_url": "https://upload.wikimedia.org/.../En-us-hello.ogg.mp3",
  "license": "Public domain",
  "license_url": null,
  "attribution": "Dvortygirl",
  "fetched_at": "2026-10-20T...+00:00"
}
```

前端必须显示来源链接和许可证；有作者时显示作者。公共领域文件也显示来源，便于审计。

## 4. 真人与口音判断

只接受以下文件命名系列：

- `En-us-*` → 美式
- `En-uk-*` / `En-gb-*` → 英式
- `LL-Q1860 (eng)-*` → Lingua Libre 真人录制，口音未标注

口音标签来自文件名，不根据猜测生成。只有同时存在美式和英式候选时，界面才显示两个按钮；只有一种时显示静态口音标签；无法确定时显示“口音未标注”。

**不使用浏览器 SpeechSynthesis、edge-tts 或其他机器合成语音冒充真人录音。**

## 5. 缓存设计

- 缓存目录：`data/audio_cache/`
- 缓存键：`sha256("wikimedia-commons|v1|" + word + "|" + accent)`
- 文件：`<cache_id>.mp3`（或 `.ogg`/`.wav`），旁边 `<cache_id>.json`
- 最大音频：10 MB
- 原子写入：先写 `.part`，再替换；失败清理临时文件
- 进程内按单词加锁，避免同一单词并发重复下载
- 成功响应第二次返回 `cached=true`，不重复下载
- 前端优先重播已加载音频；同一单词/口音不重复请求
- 暂未实现自动清理；长期使用需要增加缓存上限和清理策略

## 6. 替代方案与限制

| 方案 | 结论 |
| --- | --- |
| Wiktionary 页面抓取 | 音频通常与 Commons 同源，但 HTML 结构更易变；使用 Commons API 更稳定 |
| Forvo | 需要 API Key 和商业/使用条款，未接入 |
| Merriam-Webster / Oxford API | 需要 Key，许可限制较多，未接入 |
| Free Dictionary API | 音频来源和许可链不够明确，未采用 |
| 浏览器 SpeechSynthesis | 机器合成，不能标为真人；本项目不采用 |
| edge-tts 等非官方接口 | 服务条款和稳定性不可靠，禁止 |
| 本地 Piper 等 TTS | 合成语音；若未来使用必须明确标注“合成语音”，不能作为真人录音 |
| 自建真人录音库 | 最可控，但需要录音、授权和存储，当前不做 |

当前限制：

- 不是每个词都有录音；技术词、屈折形式、专有名词覆盖较低。
- 同一个人可能录制多个词，但不同词的口音/音质不一致。
- Wikimedia 可能限流；首次未缓存请求可能等待，成功后会缓存。
- 来源页可能失效；缓存元数据保留当时的信息。
- 录音格式和浏览器支持：优先 MP3，当前在 Chromium 验证；OGG/WAV 的浏览器兼容性需另行验证。

## 7. 隐私边界

为获取**未缓存**单词的真人录音，只发送：

- 被点击的单词文本（例如 `hello`）
- 语言/口音参数（`auto`、`us` 或 `uk`）

不发送：

- PDF 文件、书名、页面文字或整页/整本内容
- 照片、OCR 文本
- 文件名、用户身份、设备信息（User-Agent 只标识项目工具）

已缓存的单词完全在本机播放，不发起外部请求。
