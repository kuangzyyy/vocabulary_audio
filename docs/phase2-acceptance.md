# Phase 2 验收记录：真实单词发音

- 日期：2026-10-20
- 环境：Windows 11，Python 3.12.10，Node 24.18.0
- 浏览器：ZCode In-app Browser（Chromium）
- 后端：<http://127.0.0.1:8000>
- 前端：<http://127.0.0.1:5173>

## 1. 自动化测试

```text
python -m pytest
48 passed

ruff check backend scripts
All checks passed

npm --prefix frontend test
12 passed（6 坐标 + 6 音频 UI）

npm --prefix frontend run build
built successfully
```

新增测试覆盖：

- Wikimedia Commons 页面解析：美式/英式/未标注口音、MP3 转码选择、原始 OGG 回退。
- 许可过滤：Public domain、CC0、CC BY、CC BY-SA 接受；NC/ND、未知许可拒绝。
- 合成语音标记拒绝；未知文件前缀拒绝。
- 音频缓存：首次下载、第二次 `cached=true`、UK/US 分别缓存、缓存文件丢失后重新获取。
- 无录音、无效单词、上游失败、无效缓存 ID 的错误码。
- 音频 API 响应字段和缓存文件 HTTP 服务。
- 前端：美式/英式双选项、单口音静态标签、未知口音不伪造选项、来源/许可文本。

## 2. 真实音频来源验证

使用 Wikimedia Commons 官方 API：

```text
GET https://commons.wikimedia.org/w/api.php
  ?action=query&format=json&formatversion=2
  &titles=File:En-us-hello.ogg|File:En-uk-hello.ogg|...
  &prop=videoinfo
  &viprop=url|mime|derivatives|extmetadata
```

实际获取结果：

| 单词 | 口音 | 文件 | 许可证 | 作者 |
| --- | --- | --- | --- | --- |
| hello | 美式 | En-us-hello.ogg | Public domain | Dvortygirl |
| hello | 英式 | En-uk-hello.ogg | CC BY 3.0 us | Association Shtooka, Judith Franck |
| sentence | 美式 | En-us-sentence.ogg | CC BY-SA 3.0 | Own work（来源页） |
| click | 英式 | En-uk-click.ogg | Public domain | 无（来源页） |
| vocabulary | 美式 | En-us-vocabulary.ogg | CC BY-SA 3.0 | Neskaya |

媒体使用 Wikimedia 生成的 MP3 转码，例如：

```text
https://upload.wikimedia.org/wikipedia/commons/transcoded/5/52/
  En-us-hello.ogg/En-us-hello.ogg.mp3
```

### 访问方式验证

- `httpx` 访问 Commons API：HTTP 403（机器人策略）。
- `urllib` 经系统代理访问：HTTP 429（代理出口被限流）。
- 系统 `curl` 直连：API 和 MP3 均 HTTP 200。
- 后端因此默认使用系统 `curl` 直连；`urllib` 作为兜底；可用 `VOCABULARY_AUDIO_USE_PROXY=1` 切回系统代理。
- 未使用伪造浏览器 UA、未绕过访问控制、未抓取 HTML 页面。

## 3. 浏览器端到端验证

测试 PDF：`audio_test.pdf`，包含 `Hello`、`sentence`、`Rotated`、`Click` 等词。

### 3.1 美式真人发音

点击 `Hello` 后：

- 结果栏显示 `Hello`。
- 音频状态：`播放中…`，`<audio>.currentTime` 前进，`duration = 0.53551s`。
- 音频 URL：本地缓存 `/api/audio/cache/...`。
- 显示“美式 · Wikimedia Commons 真人录音 · 本地缓存”。
- 显示两个口音按钮：`美式`（pressed）、`英式`。
- 来源：`https://commons.wikimedia.org/wiki/File:En-us-hello.ogg`。
- 许可证：`Public domain`。
- 作者：`Dvortygirl`。
- 重播按钮可见。

### 3.2 英式选择

点击“英式”后：

- 音频重新加载并播放，`duration = 1.121814s`。
- 按钮状态：美式 false、英式 true。
- 来源：`File:En-uk-hello.ogg`。
- 许可证：`CC BY 3.0 us`。
- 作者：`Association Shtooka, Judith Franck`。

### 3.3 重复点击

再次点击 `Hello`：

- `performance.getEntriesByType('resource')` 中 `/api/audio/word` 请求数仍为 1。
- 音频从 0 重新播放，没有重复下载。

### 3.4 单一口音

点击 `sentence`（只有美式）：

- 口音按钮数量为 **0**。
- 显示静态标签“美式发音”。
- 音频时长 1.266939s，许可证 CC BY-SA 3.0。
- 没有伪造英式选项。

点击 `Click`（只有英式）：

- 口音按钮数量为 **0**。
- 显示静态标签“英式发音”。
- 音频时长 1.925805s，许可证 Public domain。
- 没有伪造美式选项。

### 3.5 无录音

点击 `Rotated`：

- 结果栏显示“没有找到‘rotated’的可合法使用真人录音。”
- 播放状态为“无音频”，样式为错误状态。
- 来源和重播隐藏；`<audio>` 的 `src` 被清空。
- PDF 页面仍然可见，16 个单词点击框仍在，页面没有崩溃。

### 3.6 未缓存单词与加载状态

点击 `vocabulary`：

- 立即显示“正在查找 Wikimedia Commons 真人录音…”和“加载中…”。
- 第一次请求因上游连接重置返回 502；页面显示“下载发音失败”类错误，没有崩溃。
- 稍后重试/缓存写入成功后，再次点击立即从本地缓存播放，显示“本地缓存”，时长 1.403651s，作者 Neskaya。
- 在改用系统 curl 直连并增加重试后，未缓存的 `click` 首次 API 请求耗时约 1.4 秒并成功。

### 3.7 PDF 功能回归

- 点击 `sentence` 后音频播放，PDF 点击层正常。
- 翻到第 2 页，放大到 245%，滚动 700px：
  - 点击框相对 canvas 的 x = 0.121007，后端 bbox x0 = 0.121008。
  - y = 0.167043，后端 bbox y0 = 0.167043。
- 翻页后旧音频停止，结果栏重置。
- 结果栏底边仍为视口高度 720px，没有布局溢出。

## 4. 缓存验证

`data/audio_cache/` 中的实际文件：

```text
a839...cd8bc.mp3    9169 bytes   hello 美式
7d0c...a9aa.mp3    18500 bytes   hello 英式
cb4f...798be.mp3   21058 bytes   sentence 美式
3188...7e8eb.mp3   23558 bytes   vocabulary 美式
f158...8b1bd.mp3   40754 bytes   click 英式
```

每个音频旁边有同名 `.json`，包含：

- word / accent / available_accents
- provider / title
- source_page / audio_url / original_url
- license / license_url / attribution
- fetched_at（UTC）
- cache_file / mime

第二次请求同一单词返回 `cached=true`，不重复下载。

## 5. 发现并修复的问题

1. **httpx 被 Wikimedia 机器人策略拒绝**：改用系统 curl/urllib，遵守官方 API 和使用限制。
2. **系统代理出口被限流**：默认直连 Wikimedia，保留代理开关。
3. **媒体下载 429**：读取 `Retry-After`，等待后重试一次；缓存避免重复。
4. **连接重置**：curl 连接失败自动重试 4 次；错误信息改为可理解的中文。
5. **无音频时仍保留旧音频 src**：在 fetch 错误时调用停止逻辑并清空音频。
6. **Vite 代理在重启后端后短暂挂起**：干净重启前后端后恢复；不影响生产代码，但文档说明重启顺序。

## 6. 未解决 / 已知限制

- **首次未缓存请求依赖网络**：可能等待数秒；Wikimedia 限流/连接重置时会再次失败。页面有明确提示，重试或缓存后正常。
- **整句音频未实现**：点击句子只显示文本，不播放声音。
- **不是每个单词都有录音**：技术词、屈折形式、专有名词覆盖较低；没有时明确提示，没有 TTS 回退。
- **自动播放阻止分支未在本次浏览器中触发**：Chromium 允许点击后的播放；代码包含 `NotAllowedError` 分支，会提示点击“重播”。
- **浏览器兼容性**：当前在 Chromium 验证；优先 MP3，OGG/WAV 在 Safari 等浏览器上的支持需另行验证。
- **来源页/作者信息质量不一**：部分文件作者显示为“Own work”，实际署名依赖 Commons 文件页；前端保留来源链接。
- **缓存不会自动清理**：长期使用需要缓存上限/清理策略。
- **原生文件选择框未自动化**：测试使用文件输入 `change` 事件和拖放路径，仍需人工点击一次“打开 PDF”。
- **网络代理配置**：默认直连；需要代理的环境要手动设置 `VOCABULARY_AUDIO_USE_PROXY=1`。

## 7. 结论

Phase 2 的完成标准已满足：

- 点击单词能够播放真实真人录音。
- 有美式/英式两种时提供选择；只有一种时不伪造第二项。
- 来源、许可证、作者可追溯并在界面展示。
- 成功音频本地缓存，重复请求不再下载。
- 音频缺失、网络失败、播放失败有明确提示，页面不崩溃。
- PDF 点读主流程没有回归。

未完成项（整句音频、照片 OCR、原生文件框人工确认）已明确记录。
