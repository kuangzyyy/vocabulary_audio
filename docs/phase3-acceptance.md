# Phase 3 验收记录：整句点读

- 日期：2026-10-20
- 环境：Windows 11，Python 3.12.10，Node 24.18.0
- 浏览器：ZCode In-app Browser（Chromium）
- 后端：<http://127.0.0.1:8000>
- 前端：<http://127.0.0.1:5173>

## 1. 自动化测试

```text
python -m pytest
55 passed

ruff check backend scripts
All checks passed

npm --prefix frontend test
12 passed（6 坐标 + 6 音频 UI）

npm --prefix frontend run build
built successfully
```

新增测试覆盖：

- 整句文本规范化、空句子/非英文/超长句子拒绝。
- 本机 TTS WAV 生成（使用 fake provider 的协议测试，真实 SAPI 在浏览器验收中验证）。
- 整句 WAV 缓存、重复请求 `cached=true`。
- TTS 失败清理临时文件、无效 WAV 拒绝。
- 整句 API 响应字段 `synthetic/engine/voice/locale/note`。
- 整句缓存文件通过 `/api/audio/cache/{cache_id}` 返回 `audio/wav`。
- 整句 API 400/503 错误路径。
- 原有单词真人录音、PDF 坐标和 API 测试全部保留。

## 2. 点词 / 点句优先级

实现方式：工具栏显式“单词 / 整句”模式，模式保存在 localStorage。

- **单词模式**：单词层在上，单词点击播单词；句子空白处播整句。
- **整句模式**：句子层在上，单词层 `pointer-events: none`，点击句子任意位置（包括单词位置）播整句。
- 句子点击框按**每行片段**（`segments`）渲染，不使用覆盖整个多行句子的联合大框；每个片段点击都播放同一整句，减少与其他句子/内容的重叠误触。
- 模式切换不依赖猜测：用户能看到当前模式，误触明显减少。

浏览器中验证：

- 在整句模式下，将点击坐标放在单词 `sentence` 的中心：
  - `document.elementFromPoint` 返回 `sentence-hit`，不是 `word-hit`。
  - 点击后结果栏显示完整句子 `This is a sentence for audio.`，播放整句。
- 切回单词模式后点击同一位置：结果栏显示 `sentence`，播放单词真人录音。
- 单词模式点击句子空白处仍可播整句，作为快捷方式。

## 3. 整句音频来源与标记

- 没有可靠的合法真人整句通用来源；**没有把单词录音拼接成整句**。
- 使用本机 Windows `System.Speech`：
  - Microsoft Zira Desktop，en-US
  - Microsoft David Desktop，en-US
- 生成的 WAV 示例：101878 bytes（约 2.3 秒）。
- 接口返回：

```json
{
  "synthetic": true,
  "engine": "Windows SAPI (System.Speech)",
  "voice": "Microsoft Zira Desktop",
  "locale": "en-US",
  "note": "由本机 Windows 系统语音合成生成，不是真人录音。"
}
```

- UI 同时显示：
  - “合成语音”徽标；
  - “本机 Windows 系统语音合成生成，不是真人录音”说明；
  - 结果元信息中的 engine 和 voice。
- 没有提供伪造的英式/美式整句选择；当前系统只有 en-US 英文语音。

## 4. 浏览器端到端验证

### 4.1 整句模式

点击 `This is a sentence for audio.`：

- 结果栏显示完整句子。
- 整句音频状态 `合成语音播放中…`，`duration = 2.309116s`。
- `sentence-audio` 使用本地缓存 `/api/audio/cache/...`。
- 单词音频暂停。
- 口音按钮隐藏（整句没有口音切换）。
- “合成语音”徽标和“不是真人录音”说明可见。
- 重播按钮可见。

### 4.2 重复点击整句

再次点击同一句：

- `/api/audio/sentence` 网络请求数仍为 **1**。
- 音频从 0 重新播放。
- 仍显示“本地缓存”。

### 4.3 切回单词模式

切回“单词”后点击同一个 `sentence` 单词：

- 结果栏显示 `sentence`，不是整句。
- 播放 Wikimedia Commons 单词真人录音（1.266939s）。
- 合成语音徽标和说明隐藏。
- 显示“美式发音”静态标签。

### 4.4 多页 PDF 与布局

使用 4 页测试 PDF：

- 第 1 页点击 `This is the first sentence on page one.`，整句 TTS 播放（2.938912s）。
- 翻到第 2 页：旧整句音频停止，结果重置。
- 第 2 页点击 `Navigation should keep the click regions aligned.`，整句 TTS 播放（3.353787s）。
- 放大到 245%、滚动 700px 后：
  - 句子点击框相对 canvas 的位置与后端 bbox 一致：
    - x = 0.1210072166，bbox x0 = 0.121008
    - y = 0.1670428041，bbox y0 = 0.167043
  - 再次点击句子仍能播放整句。
- PDF 页面仍由 PDF.js 渲染，原始排版没有改成重排文章。
- 结果栏底边保持在视口内（720px）。

### 4.5 多行句子片段

真实 arXiv 论文第 2 页的句子：

```text
The fundamental constraint of sequential computation, however, remains.
```

- 接口返回 2 个 `segments`（按行拆分的点击框）。
- 点击第一个片段后，结果栏显示完整整句，播放整句 TTS（5.678549s）。
- 不再使用覆盖整个多行句子的联合大矩形，减少与相邻内容的重叠误触。

## 5. 缓存

`data/audio_cache/` 中新增：

- 单词真人录音 `.mp3`；
- 整句 TTS `.wav`，例如 `101878 bytes`；
- 每份音频旁的同名 `.json` 元数据。

整句元数据包含：

```json
{
  "kind": "sentence",
  "synthetic": true,
  "text": "...",
  "engine": "Windows SAPI (System.Speech)",
  "voice": "Microsoft Zira Desktop",
  "locale": "en-US",
  "cache_file": "<cache_id>.wav",
  "mime": "audio/wav",
  "generated_at": "..."
}
```

第二次请求同一句返回 `cached=true`；前端重复点击直接重播，不重复调用 API。

## 6. 已知限制

- **整句是合成语音**：Windows Zira，不是真人录音；当前不提供真实英式/美式整句选择。
- **真人整句录音缺失**：没有可靠合法通用来源；不拼接单词录音。
- **平台限制**：TTS 依赖 Windows `System.Speech` 和英文语音；其他平台返回 503。单词真人录音不受影响。
- **长度限制**：整句最多 500 字符；超过时提示用户点击更短句子。
- **模式切换**：整句模式会把单词点击也解释为整句，这是有意设计；要点单词需切回单词模式。
- **自动播放阻止分支未在本次浏览器触发**：代码包含 `NotAllowedError` 处理和重播按钮。
- **原生文件选择框未自动化**：测试使用文件输入 `change` 和拖放路径。
- **缓存清理未实现**：长期使用需要缓存上限/清理策略。
- **TTS 语音许可**：Windows 系统语音生成音频仅在本机个人使用；分发前需复核许可。
- **复杂句子切分**：跨页、脚注、表格中的句子范围仍依赖启发式规则，需要更多真实书籍验证。

## 7. 结论

Phase 3 完成标准已满足：

- 点击单词播放单词音频。
- 整句模式点击例句播放整句音频。
- 点词/点句是显式模式，不会频繁误触。
- 整句音频明确标记为“合成语音（非真人录音）”，没有冒充真人。
- 整句音频有本地缓存、失败提示和重复点击处理。
- 翻页、缩放、滚动后点击框仍准确。
- PDF 原版页面布局保持不变。

未完成项（真人整句录音、手机 OCR、原生文件框人工确认）已明确记录。
