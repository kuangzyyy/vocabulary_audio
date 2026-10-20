# 环境检查报告

- 检查日期：2026-10-20
- 工作目录：`D:\app_github\vocabulary_audio`
- 系统：Windows（版本 10.0.26200，x64）
- 当前阶段：Phase 2（PDF 点读 + 真实单词发音）已完成

## 结论

| 项目 | 状态 |
| --- | --- |
| Python | **3.12.10 已安装**，项目 `.venv` 已创建 |
| Node.js / npm | 24.18.0 / 11.16.0，满足要求 |
| Git | 2.55.0，满足要求 |
| Phase 1/2 后端依赖 | **已安装到 `.venv`** |
| 前端依赖 | **已安装到 `frontend/node_modules`** |
| 音频网络访问 | 系统 `curl` 可访问 Wikimedia Commons；urllib 兜底 |
| 照片 OCR 依赖 | **未安装**（Phase 3 才需要） |
| Tesseract / Docker | 不需要 |
| 后端测试 | **48 passed** |
| 前端测试 | **12 passed**（6 坐标 + 6 音频 UI） |
| 前端构建 | 成功 |
| 浏览器验收 | PDF 点读、真人美式/英式音频、缓存、无音频提示均通过 |

## 1. 工作区与私人数据

- 第一次检查时工作区为空，没有删除或覆盖任何用户文件。
- `data/books/` 中的测试 PDF、`data/audio_cache/` 中的测试录音都是运行产物，已被 `.gitignore` 忽略。
- 仓库不包含书籍、照片或音频文件。

## 2. 系统与开发工具

| 工具 | 结果 | 判断 |
| --- | --- | --- |
| Python | 3.12.10 | 满足 |
| pip（venv 内） | 26.2.1 | 满足 |
| Node.js | v24.18.0 | 满足 PDF.js 6 / Vite 8 |
| npm | 11.16.0 | 满足 |
| Git | 2.55.0.windows.2 | 满足 |
| curl | 系统自带（Windows 11） | 用于访问 Wikimedia |
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

**音频功能没有新增 Python 包或 API Key。** HTTP 访问使用标准库 `urllib` 和系统 curl。

### 尚未安装

- RapidOCR 3.10.0
- ONNX Runtime 1.31.0

它们属于 Phase 3 照片 OCR。需要时：

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

## 5. 音频源访问验证

选择的来源：Wikimedia Commons 官方 MediaWiki API。

实际测试：

| 客户端 | 结果 |
| --- | --- |
| Python `httpx` | Commons API 返回 HTTP 403（机器人策略） |
| Python `urllib` + 系统代理 | API 正常，但媒体下载被代理出口限流（HTTP 429） |
| 系统 `curl` 直连 | API 200，MP3 转码 200 |
| 后端当前实现 | 默认系统 curl 直连；无 curl 时 urllib；可设置代理开关 |

- API 查询带项目 User-Agent，查询间隔至少 0.5 秒。
- 媒体 429 按 `Retry-After` 等待并重试一次。
- 连接重置自动重试最多 4 次。
- 成功音频缓存到 `data/audio_cache/`，重复请求不访问网络。
- 只接受 Public domain、CC0、CC BY、CC BY-SA；拒绝 NC/ND、许可不明和合成语音标记。
- 只发送被点击的单词文本，不发送书籍、照片或整页内容。

详见 [audio-source.md](audio-source.md)。

## 6. Phase 2 验证结果

### 自动化测试

```text
python -m pytest
48 passed

ruff check backend scripts
All checks passed

npm --prefix frontend test
12 passed

npm --prefix frontend run build
built successfully
```

### 浏览器端到端

- `Hello`：美式真人录音，时长 0.53551s，Public domain，作者 Dvortygirl；可切换英式。
- 英式 `Hello`：时长 1.121814s，CC BY 3.0 us，Association Shtooka / Judith Franck。
- 重复点击 `Hello`：音频 API 请求数不增加，直接重播。
- `sentence`：只有美式，显示静态“美式发音”，没有伪造英式按钮。
- `Click`：只有英式，显示静态“英式发音”，没有伪造美式按钮。
- `Rotated`：无录音，显示明确提示，PDF 页面和点击层保持可用。
- `vocabulary`：首次加载显示“加载中”；上游一次失败后重试/缓存成功；之后再点击立即从本地缓存播放。
- PDF 回归：第 2 页、245% 缩放、滚动 700px 后点击框仍与 bbox 对齐；翻页停止音频。

详见 [phase2-acceptance.md](phase2-acceptance.md)。

## 7. 未验证 / 未解决

- 整句真人音频：未实现；点击句子只显示文本。
- 手机照片 OCR：依赖未安装，功能未实现。
- 原生文件选择对话框：自动化无法操作系统对话框；已通过文件输入 `change` 和拖放路径验证，仍需人工点击一次确认。
- 自动播放阻止分支：Chromium 允许点击后播放，未实际触发 `NotAllowedError` 分支。
- 浏览器兼容性：当前在 Chromium 验证；Safari 等对 OGG/WAV 的支持需另行验证。
- 首次未缓存单词可能等待或失败：Wikimedia 限流/网络问题；页面有提示，重试或缓存后正常。
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
curl http://127.0.0.1:5173/
```

如果网络必须走系统代理：

```powershell
$env:VOCABULARY_AUDIO_USE_PROXY = "1"
```

然后重启后端。
