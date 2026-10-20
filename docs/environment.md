# 环境检查报告

- 检查日期：2026-10-20
- 工作目录：`D:\app_github\vocabulary_audio`
- 系统：Windows（版本 10.0.26200，x64）
- 当前阶段：Phase 3（PDF 点读 + 真人单词发音 + 整句点读）已完成

## 结论

| 项目 | 状态 |
| --- | --- |
| Python | **3.12.10 已安装**，项目 `.venv` 已创建 |
| Node.js / npm | 24.18.0 / 11.16.0，满足要求 |
| Git | 2.55.0，满足要求 |
| Phase 1–3 后端依赖 | **已安装到 `.venv`** |
| 前端依赖 | **已安装到 `frontend/node_modules`** |
| 单词音频网络 | 系统 `curl` 可访问 Wikimedia Commons；urllib 兜底 |
| 整句 TTS | Windows SAPI 可用：Microsoft Zira / David（en-US） |
| 照片 OCR 依赖 | **未安装**（Phase 4 才需要） |
| Tesseract / Docker | 不需要 |
| 后端测试 | **55 passed** |
| 前端测试 | **12 passed**（6 坐标 + 6 音频 UI） |
| 前端构建 | 成功 |
| 浏览器验收 | 单词真人录音、点词/点句模式、整句 TTS、缓存、PDF 对齐均通过 |

## 1. 工作区与私人数据

- 第一次检查时工作区为空，没有删除或覆盖任何用户文件。
- `data/books/` 的测试 PDF、`data/audio_cache/` 的测试录音/TTS WAV 都是运行产物，已被 `.gitignore` 忽略。
- 仓库不包含书籍、照片或音频文件。

## 2. 系统与开发工具

| 工具 | 结果 | 判断 |
| --- | --- | --- |
| Python | 3.12.10 | 满足 |
| pip（venv 内） | 26.2.1 | 满足 |
| Node.js | v24.18.0 | 满足 PDF.js 6 / Vite 8 |
| npm | 11.16.0 | 满足 |
| Git | 2.55.0.windows.2 | 满足 |
| curl | 系统自带（Windows 11） | 单词音频访问 Wikimedia |
| Windows PowerShell | 系统自带 | 整句 TTS 调用 System.Speech |
| Docker | 未安装 | 不需要 |
| Tesseract | 未安装 | 不需要 |

## 3. 后端依赖

### 已安装（`.venv` 内）

- FastAPI 0.150.0
- Uvicorn 0.54.0（standard extras）
- PyMuPDF 1.26.5
- python-multipart 0.0.32
- Pillow 11.3.0（测试生成扫描页）
- pytest 9.1.1
- httpx 0.28.1（仅测试）
- Ruff 0.17.1

**单词音频和整句 TTS 没有新增 Python 包或 API Key。**

- 单词音频 HTTP：标准库 `urllib` + 系统 `curl`。
- 整句 TTS：PowerShell + .NET `System.Speech`，生成 WAV。

### 尚未安装

- RapidOCR 3.10.0
- ONNX Runtime 1.31.0

它们属于 Phase 4 照片 OCR。需要时：

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements-ocr.txt
```

## 4. 前端依赖

| 包 | 版本 | 状态 |
| --- | --- | --- |
| `pdfjs-dist` | 6.4.299 | 已安装 |
| `vite` | 8.3.4 | 已安装 |
| Node 内置 test runner | Node 24.18 | 可运行 |

## 5. 音频源与 TTS 验证

### 单词真人录音

选择的来源：Wikimedia Commons 官方 MediaWiki API。

| 客户端 | 结果 |
| --- | --- |
| Python `httpx` | Commons API 返回 HTTP 403（机器人策略） |
| Python `urllib` + 系统代理 | API 正常，但媒体下载被代理出口限流（HTTP 429） |
| 系统 `curl` 直连 | API 200，MP3 转码 200 |
| 后端当前实现 | 默认系统 curl 直连；无 curl 时 urllib；可设置代理开关 |

- 只接受 Public domain、CC0、CC BY、CC BY-SA；拒绝 NC/ND、许可不明和合成语音标记。
- 只发送被点击的单词文本，不发送书籍、照片或整页内容。
- 成功音频缓存到 `data/audio_cache/`，重复请求不访问网络。

### 整句 TTS

- 使用本机 `scripts/tts_sapi.ps1` 调用 Windows `System.Speech`。
- 已安装英文语音：Microsoft Zira Desktop、Microsoft David Desktop（en-US）。
- 实测生成 WAV 成功，约 100 KB/short sentence；缓存后第二次直接复用。
- 接口返回 `synthetic: true`、engine、voice、locale、note；UI 显示“合成语音（非真人录音）”。
- 不拼接单词录音；没有真人整句录音来源。
- 句子文本只在本机后端处理，不发送到云端。

详见 [audio-source.md](audio-source.md)。

## 6. Phase 3 验证结果

### 自动化测试

```text
python -m pytest
55 passed

ruff check backend scripts
All checks passed

npm --prefix frontend test
12 passed

npm --prefix frontend run build
built successfully
```

### 浏览器端到端

- 默认单词模式：`Hello` 播放 Wikimedia Commons 美式真人录音，时长 0.53551s。
- 切换到整句模式：点击句子（即使点击位置在单词上）播放整句，结果文本为完整句子。
- 整句音频：Microsoft Zira，2.309116s，显示“合成语音（非真人录音）”徽标和说明。
- 重复点击整句：`/api/audio/sentence` 请求数不增加，直接重播。
- 切回单词模式：同一位置播放 `sentence` 单词真人录音，合成标记隐藏。
- 第 2 页例句：翻页停止旧音频；整句 TTS 正常；245% 缩放、滚动 700px 后句子框与 bbox 对齐。
- 结果栏保持可见，PDF 原版页面未改成重排文章。

详见 [phase3-acceptance.md](phase3-acceptance.md)。

## 7. 未验证 / 未解决

- 真人整句录音：没有可靠合法通用来源；当前 TTS 是合成语音。
- 手机照片 OCR：依赖未安装，功能未实现。
- 原生文件选择对话框：自动化无法操作系统对话框；已通过文件输入 `change` 和拖放路径验证，仍需人工点击一次确认。
- 自动播放阻止分支：Chromium 允许点击后播放，未实际触发 `NotAllowedError`。
- 浏览器兼容性：当前在 Chromium 验证；Safari 等对 OGG/WAV 的支持需另行验证。
- 首次未缓存单词可能等待或失败：Wikimedia 限流/网络问题；页面有提示，重试或缓存后正常。
- 整句超过 500 字符会报错；TTS 依赖 Windows 语音。
- 缓存没有自动清理策略。
- 复杂书籍版式、整句切分仍需更多真实样本验证。
- PyMuPDF 许可证：AGPL-3.0 或商业许可，分发前需复核。

## 8. 如何重新检查

```powershell
.\.venv\Scripts\Activate.ps1
python scripts\check_env.py
```

服务运行检查：

```powershell
curl http://127.0.0.1:8000/api/health
curl "http://127.0.0.1:8000/api/audio/word?text=hello&accent=auto"
curl "http://127.0.0.1:8000/api/audio/sentence?text=This%20is%20a%20sentence."
curl http://127.0.0.1:5173/
```

如果单词音频网络必须走系统代理：

```powershell
$env:VOCABULARY_AUDIO_USE_PROXY = "1"
```

然后重启后端。
