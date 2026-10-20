# Vocabulary Audio

一个**本地优先**的英语点读工具：在电脑上打开 PDF，点击原始页面里的英文单词听真人录音，或切换到整句模式点击例句听整句；后续会支持手机拍摄纸质书页面后点读。

> **当前状态：Phase 3 已完成（2026-10-20）**
>
> 已实现：PDF 原版页面渲染、单词/句子坐标、透明点击层、翻页/缩放/滚动、
> **真人单词发音、美式/英式选择、来源与许可、本地缓存**、
> **整句点读（点词/点句模式、本机 Windows TTS、合成语音标记、缓存）**。
>
> 尚未实现：手机照片 OCR、真人整句录音、EPUB、收藏和学习记录。

## 现在能做什么

- 用“打开 PDF”按钮、拖放或文件选择打开普通文本 PDF。
- PDF.js 按原始排版显示页面，不用重排文本替代原书。
- **单词模式**：点击英文单词，显示识别结果并播放 Wikimedia Commons 真人录音。
- 如果该单词同时有美式/英式录音，页面会显示两个可点击的口音选项；只有一种时只显示该口音，不伪造另一种。
- **整句模式**：点击例句区域任意位置，播放整句。整句使用本机 Windows 语音合成，界面明确标记“合成语音（非真人录音）”。
- 点词/点句是显式模式，避免单词点击和句子点击互相误触；单词模式仍可点击句子空白处播整句。
- 录音和合成语音都会缓存到本机，重复点击优先复用；加载、失败、重播都有明确反馈。
- 支持上一页/下一页、页码输入、放大/缩小、“适合宽度”和页面滚动；点击区域始终与原文对齐。
- 扫描版页面明确提示“暂不支持 OCR”，不伪造识别结果。
- 音频缺失、网络失败、TTS 不可用、播放失败都有明确提示；页面不会崩溃。

## 暂不实现

- **真人整句录音**：没有可靠、合法、可覆盖任意 PDF 句子的通用来源；当前使用本机 TTS 并明确标注，不把多个单词录音拼接后称为真人整句。
- 云端 TTS、edge-tts 或其他非官方语音接口。
- 手机照片 OCR（RapidOCR 依赖尚未安装）。
- EPUB、单词收藏、生词本、学习记录。
- 用户账号、云同步、分享、公开部署。
- 扫描版 PDF 的 OCR。

## 音频来源与许可

### 单词真人录音

**来源：Wikimedia Commons 官方 MediaWiki API。**

- 只接受明确允许复用的许可证：Public domain、CC0、CC BY、CC BY-SA。
- 拒绝 CC BY-NC、CC BY-ND、GFDL-only、许可证不明或内容含合成语音标记的文件。
- 只使用已知为社区真人录制的文件命名系列：`En-us-*`、`En-uk-*`、`En-gb-*`、`LL-Q1860 (eng)-*`。
- 美式/英式标签来自文件名；无法确定口音时显示“口音未标注”，不会假装成美式或英式。
- 每个缓存文件旁保存来源页面、原始文件地址、许可证、作者、获取时间等元数据。
- 页面会显示来源链接和许可证，满足署名要求。

### 整句语音（合成）

- 没有使用真人整句录音，也没有把单词录音拼接成整句。
- 使用本机 **Windows SAPI / System.Speech** 英文语音（本机为 Microsoft Zira Desktop，en-US），生成 WAV 并缓存。
- 界面会持续显示“合成语音（非真人录音）”标签和说明，不会把它称为真人录音。
- 语音选择取决于系统已安装的英文语音；当前不提供伪造的英式/美式整句选项。
- TTS 完全在本机运行，不把句子文本发送到云端；生成结果只保存在 `data/audio_cache/`。
- Windows 系统语音仅用于本机个人使用；分发合成音频前需复核 Windows 语音的许可条款。

**隐私边界：** 点击一个**尚未缓存**的单词时，只有该单词文本会发送到 Wikimedia Commons API；不会发送 PDF、整页文字、照片、书籍内容或用户身份。整句 TTS 的句子文本只发送到本机后端，由本机语音引擎处理。已缓存的单词/整句完全在本机播放。

更详细的来源评估、API 访问方式、限流策略和替代方案见 [docs/audio-source.md](docs/audio-source.md)。

## 技术栈

| 部分 | 选择 | 作用 |
| --- | --- | --- |
| 后端 | Python 3.12 + FastAPI + Uvicorn | 本地 API 服务 |
| PDF 解析 | PyMuPDF 1.26.5 | 提取单词、行、句子和坐标 |
| PDF 显示 | PDF.js 6.4.299 | 保留原始排版渲染 |
| 前端 | Vite 8 + 原生 JavaScript | 无需先学 React/Vue |
| 单词音频 | Wikimedia Commons 官方 API | 逐文件许可、作者和录音地址 |
| 整句音频 | Windows SAPI / System.Speech | 本机合成、明确标记、WAV 缓存 |
| 音频播放 | HTMLAudioElement | 播放 MP3/OGG/WAV |
| 音频缓存 | 本地文件 + JSON 元数据 | 避免重复请求/合成，保留来源和许可 |
| 照片 OCR（Phase 4） | RapidOCR + ONNX Runtime | 本地运行、返回文字坐标 |
| 测试 | pytest + Node 内置 test runner | 后端 API/缓存/坐标测试、前端 UI 单元测试 |

后端使用标准库 `urllib` 作为兜底传输，并优先使用系统 `curl` 直接访问 Wikimedia。Windows 10/11 自带 `curl.exe`。如果网络必须走系统代理，可以设置：

```powershell
$env:VOCABULARY_AUDIO_USE_PROXY = "1"
```

## 当前环境状态

检查日期：**2026-10-20**。详细记录见 [docs/environment.md](docs/environment.md)。

| 项目 | 状态 |
| --- | --- |
| Python | **3.12.10 已安装**，项目 `.venv` 已创建 |
| Node.js / npm | 24.18.0 / 11.16.0，满足要求 |
| Git | 2.55.0，满足要求 |
| FastAPI / Uvicorn / PyMuPDF | 已安装到 `.venv` |
| Pillow / pytest / httpx / Ruff | 已安装到 `.venv`（开发与测试用） |
| PDF.js / Vite | 已安装到 `frontend/node_modules` |
| 系统 curl | Windows 自带，可访问 Wikimedia |
| Windows SAPI | 已启用 Microsoft Zira / David（en-US） |
| RapidOCR / ONNX Runtime | **未安装**；Phase 4 需要时执行 `pip install -r requirements-ocr.txt` |
| Tesseract / Docker | 不需要 |

单词真人录音和整句 TTS 都不需要额外的 Python 包或 API Key。

一键复查：

```powershell
.\.venv\Scripts\python.exe scripts\check_env.py
```

## 快速开始（Windows / PowerShell）

### 1. 激活虚拟环境

```powershell
.\.venv\Scripts\Activate.ps1
```

如果 PowerShell 禁止运行脚本：

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Git Bash 使用：

```bash
source .venv/Scripts/activate
```

### 2. 安装依赖（新环境才需要）

```powershell
python -m pip install --upgrade pip
pip install -r requirements-dev.txt

cd frontend
npm install
cd ..
```

> Phase 1/2 不需要 OCR。实现照片点读时再执行
> `pip install -r requirements-ocr.txt`。

### 3. 启动后端

```powershell
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

健康检查：<http://127.0.0.1:8000/api/health>
接口文档：<http://127.0.0.1:8000/docs>

### 4. 启动前端

另开一个终端：

```powershell
cd frontend
npm run dev
```

打开 <http://127.0.0.1:5173>。

前端开发服务器会把 `/api` 请求代理到本机 `http://127.0.0.1:8000`。

### 5. 使用

1. 点击“打开 PDF”或把 PDF 拖入页面。
2. 选择工具栏的 **单词** 模式（默认）：
   - 点击英文单词，显示识别结果并播放 Wikimedia Commons 真人录音；
   - 有美式/英式两种录音时，可以点击“美式”“英式”切换；
   - 只有一种录音时显示该口音，不会出现伪造的第二个选项；
   - 没有录音时显示“没有找到可合法使用真人录音”。
3. 选择工具栏的 **整句** 模式：
   - 点击例句区域任意位置（包括单词位置）都会播放整句；
   - 整句由本机 Windows 语音合成，界面显示“合成语音（非真人录音）”；
   - 第一次生成本地 WAV，后续重复点击直接复用缓存。
4. 在单词模式下，点击句子内单词之间的空白处也可以播整句；整句模式是更明确、避免误触的方式。
5. 用工具栏翻页、输入页码（Enter 跳转）、缩放或“适合宽度”。
6. 页面较长时在阅读区内滚动；点击区域与页面一起移动。

### 6. 手机访问（当前 PDF 和音频也可用）

手机和电脑连接同一个 Wi-Fi：

1. Vite 已配置 `host: true`，启动后显示 Network 地址。
2. 手机浏览器打开 `http://<电脑局域网IP>:5173`。
3. `/api` 请求由 Vite 代理到电脑本机后端。
4. Windows 防火墙首次询问时只允许“专用网络”。

注意：当前没有登录鉴权，**只能在可信局域网使用**，不要做端口转发。

## 测试

```powershell
# 后端：坐标、PDF 提取、书籍 API、单词音频、整句 TTS、缓存
python -m pytest

# Python 代码检查
ruff check backend scripts

# 前端坐标和口音选项测试
npm --prefix frontend test

# 前端生产构建
npm --prefix frontend run build
```

当前结果：

- 后端：**55 passed**。
- 前端：**12 passed**（6 个坐标测试 + 6 个音频 UI 测试）。
- 前端生产构建：成功。
- Ruff：通过。
- 浏览器端到端：单词真人录音、点词/点句模式、整句 TTS、缓存和 PDF 对齐均验证通过。

详细记录见 [docs/phase2-acceptance.md](docs/phase2-acceptance.md)。

## 目录结构

```text
vocabulary_audio/
├── AGENTS.md                     # 协作规则、技术选型、坐标契约、验收标准
├── README.md
├── requirements.txt              # Phase 1/2 后端依赖
├── requirements-dev.txt          # 测试/检查依赖
├── requirements-ocr.txt          # Phase 4 OCR 依赖（当前不需要安装）
├── pyproject.toml
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI 入口、统一错误映射
│   │   ├── config.py             # 数据目录、上传限制、音频 User-Agent/代理设置
│   │   ├── api/
│   │   │   ├── health.py
│   │   │   ├── books.py          # PDF 上传、文件、页面数据
│   │   │   └── audio.py          # 单词音频、整句 TTS、缓存文件
│   │   ├── services/
│   │   │   ├── books.py
│   │   │   ├── pdf_extractor.py
│   │   │   ├── audio_provider.py # Wikimedia Commons 候选/许可过滤
│   │   │   ├── audio_service.py  # 单词选择、下载、缓存、并发锁
│   │   │   ├── sentence_audio.py # 本机 Windows TTS、WAV 缓存
│   │   │   ├── wikimedia_http.py # curl/urllib 传输、限流和重试
│   │   │   └── errors.py
│   │   └── models/schemas.py
│   └── tests/                    # 55 个后端测试
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── src/
│   │   ├── main.js               # 文件选择、PDF 工具栏、点词/点句、音频结果栏
│   │   ├── api/client.js
│   │   ├── pdf/viewer.js
│   │   ├── pdf/coordinates.js
│   │   ├── audio/audioPlayback.js # 音频元素、重复点击/取消/重播
│   │   ├── audio/audioMeta.js    # 口音选项和来源文本
│   │   └── styles/main.css
│   └── tests/                    # 坐标 + 音频 UI 单元测试
├── data/                         # 私人数据，全部被 Git 忽略
│   ├── books/
│   ├── photos/
│   └── audio_cache/              # 真人录音和 TTS WAV 缓存 + 元数据
├── docs/
│   ├── environment.md
│   ├── audio-source.md           # 音频来源评估与合规说明
│   ├── phase1-acceptance.md
│   ├── phase2-acceptance.md
│   └── phase3-acceptance.md
└── scripts/
    ├── check_env.py
    └── tts_sapi.ps1              # Windows SAPI 本机语音合成
```

## 坐标是怎么对齐的

1. PyMuPDF 返回未旋转页面坐标。
2. 后端用 `page.rotation_matrix` 转成实际显示方向，再归一化到 `0..1`。
3. 前端把归一化 bbox 转成相对页面容器的百分比。
4. canvas、句子层、单词层在同一个定位容器中，一起缩放和滚动。
5. 后端测试覆盖 0/90/180/270 度旋转；前端测试覆盖页面尺寸变化；浏览器验证对比了覆盖框与 canvas 的相对位置。

## 隐私与数据

- 默认只监听 `127.0.0.1`，PDF、照片和整页/整本内容不上传云端。
- 为获取真人录音，只有**被点击的单词文本**会发送到 Wikimedia Commons API；整句文本只发送到本机后端，由本机 TTS 处理。已缓存单词/整句不再发起外部请求。
- PDF 保存在 `data/books/`，照片将来保存在 `data/photos/`，音频缓存保存在 `data/audio_cache/`；这些目录都被 `.gitignore` 忽略。
- 缓存 JSON 包含来源 URL、许可证、作者、获取时间，便于审计和署名。
- 日志只记录 ID、页码和错误信息，不记录书籍正文。
- 请只处理你有权使用的书籍和照片；不要把受版权保护的文件提交到仓库。
- PyMuPDF 采用 AGPL-3.0 或商业许可；个人本地使用通常没问题，分发或公开托管前需要复核。

## 已知限制

- 不是每个英文单词都有 Wikimedia Commons 录音；没有时只显示明确提示，不回退到 TTS。
- 第一次获取某个词（或某个口音）需要联网；Wikimedia 可能限流，后端会按 `Retry-After` 等待并重试一次，页面显示“加载中”。成功后会缓存，之后立即播放。
- 整句使用本机 Windows TTS，**是合成语音，不是真人录音**；当前语音为系统英文语音（本机 Zira，en-US），不伪造英式/美式整句选项。
- 整句最长 500 个字符；更长的句子会提示“句子过长”，需要点击更短的句子。
- TTS 依赖 Windows `System.Speech` 和已安装英文语音；其他操作系统会返回明确的“语音合成不可用”错误，单词真人录音不受影响。
- 录音口音来自文件名，无法确定时显示“口音未标注”。
- 当前开发环境曾出现 Python 系统代理出口被 Wikimedia 限流；默认用系统 `curl` 直连，必要时可用 `VOCABULARY_AUDIO_USE_PROXY=1` 切回系统代理。
- 扫描版 PDF 只提示，不做 OCR。
- 复杂多栏、表格、脚注、跨页句子的切分仍是启发式规则，需要更多真实书籍验证。
- 原生文件选择框无法由自动化环境操作；已用文件输入 `change` 和拖放路径验证，仍建议人工点一次。
- 音频缓存目前不会自动清理；长期使用可增加清理策略。
- 当前没有鉴权，不能公开部署。

## 路线图

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| Phase 0 | 环境、规则、目录、README、健康检查 | 已完成 |
| Phase 1 | PDF 上传、坐标提取、PDF.js 渲染、单词点击、翻页/缩放/滚动 | 已完成 |
| Phase 2 | 合法真人单词录音、来源/许可、口音选择、本地缓存 | 已完成 |
| Phase 3 | 整句点读：点词/点句模式、本机 TTS、合成语音标记、WAV 缓存 | 已完成 |
| Phase 4 | 手机拍照/选图 + RapidOCR + 照片点击层 | 待开始 |
| Phase 5 | 合法真人整句音频评估、EPUB、收藏、学习记录 | 后续 |

## 相关文档

- [AGENTS.md](AGENTS.md)：技术规则、坐标契约、隐私规则、验收标准。
- [docs/audio-source.md](docs/audio-source.md)：单词录音、整句 TTS、许可、API 礼仪和替代方案。
- [docs/environment.md](docs/environment.md)：环境和依赖状态。
- [docs/phase1-acceptance.md](docs/phase1-acceptance.md)：PDF 点读验收。
- [docs/phase2-acceptance.md](docs/phase2-acceptance.md)：真人单词发音与缓存验收。
- [docs/phase3-acceptance.md](docs/phase3-acceptance.md)：整句点读、点词/点句模式和 TTS 缓存验收。
- [docs/phase2-acceptance.md](docs/phase2-acceptance.md)：真人发音与缓存验收。

## 许可证

项目代码的许可证尚未确定。第三方依赖遵循各自许可证；仓库不包含书籍、照片或音频文件。缓存的录音只存在于本机 `data/audio_cache/`，并保留来源和许可信息。
