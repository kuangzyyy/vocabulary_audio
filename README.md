# Vocabulary Audio

一个**本地优先**的英语点读工具：在电脑上打开 PDF 或 EPUB，点击原文单词听真人录音、切换整句模式听整句；手机可以拍摄或选择纸质书照片，本机 OCR 后在原照片上点读。

> **当前状态：Phase 6 已完成（EPUB 点读，2026-10-20）**
>
> 已实现：PDF 原版页面点读、EPUB 章节阅读与点读、真人单词发音、点词/点句模式、本机整句 TTS、
> 手机照片导入/拍照、本机 RapidOCR、照片单词/整句点击、缩放拖动、缓存和错误处理。
> Phase 5 对 PDF、照片、音频、布局、异常文件、网络失败和日志隐私做了回归与修复；
> Phase 6 增加 EPUB.js 阅读、目录/翻章、字号重排和正文单词/整句点读。
>
> 尚未实现：真人整句录音、收藏和学习记录。真实手机相机、原生文件选择框和真实多点触控仍需人工验收。

## 一键启动（Windows）

完成一次依赖安装后，**双击项目根目录的 `start-vocabulary-audio.bat`** 即可：

1. 检查 `.venv`、前端依赖和端口占用。
2. 在后台启动本机后端和 Vite。
3. 等待服务就绪，自动用 Edge/Chrome 的应用窗口打开 <http://127.0.0.1:5173/>。
4. 日志写入 `logs/backend.*.log` 和 `logs/frontend.*.log`。

停止服务：双击 `stop-vocabulary-audio.bat`。它只停止本项目的 Uvicorn/Vite 进程，不会删除 `data/` 中的书籍、EPUB、照片或音频缓存。

想从桌面启动，可以右键 `start-vocabulary-audio.bat` →“发送到”→“桌面快捷方式”，以后双击桌面图标即可。

一键启动默认只监听本机 `127.0.0.1`，适合桌面使用。如果要用手机访问，请按下面“手机访问”一节手动启动 Vite（`host: true`）。如果脚本提示依赖缺失，先按“安装”一节完成 `.venv` 和 `npm install`。

## 现在能做什么

### EPUB
- 用顶栏“EPUB”按钮、首页“选择 EPUB”或拖放打开普通 EPUB（EPUB 2/3，非 DRM）。
- 使用 EPUB.js 显示原书可重排内容，保留章节顺序和 EPUB 自带排版。
- 目录面板跳转章节；“上一章 / 下一章”按 spine 切换。
- 支持字号缩放（70%–180%），文字会自动重新排版；长章节可在阅读区滚动。
- 单词/整句模式与 PDF 相同：单词模式点击正文单词播放真人录音，整句模式点击句子播放标记为本机合成的整句。
- EPUB 只上传到本机后端，不上传第三方云端；不支持受 DRM 保护的 EPUB。

### PDF
- 用“打开 PDF”按钮、拖放或文件选择打开普通文本 PDF。
- PDF.js 按原始排版显示页面，不用重排文本替代原书。
- 单词模式播放 Wikimedia Commons 真人录音；两种口音时提供美式/英式选择。
- 整句模式点击例句播放本机合成语音，界面明确标记“合成语音（非真人录音）”。
- 点词/点句是显式模式，避免误触；缩放、滚动、翻页后点击框仍对齐。

### 手机照片
- 从相册选择照片，或用 `capture="environment"` 的拍照入口打开手机相机。
- 照片只在本机上传、校正 EXIF 方向、做 OCR；不上传第三方云端。
- 原照片显示在页面上，不显示“重排后的 OCR 文字”。
- RapidOCR 返回**单词级坐标**；点击照片中的单词播放单词真人录音。
- 切换到整句模式后点击照片中的句子，播放整句 TTS。
- 支持双指缩放、拖动、鼠标滚轮缩放和工具栏缩放按钮；点击框与照片使用同一个变换容器，缩放拖动后仍对齐。
- 支持重新拍摄、替换照片、清空照片。
- 空白/模糊照片、倾斜照片、中文等非英文内容、OCR 失败都有明确提示；不会伪造单词框。

## 暂不实现

- **真人整句录音**：没有可靠、合法、可覆盖任意 PDF 句子或照片句子的通用来源；当前使用本机 TTS 并明确标注，不把多个单词录音拼接后称为真人整句。
- 云端 TTS、edge-tts 或其他非官方语音接口。
- 单词收藏、生词本、学习记录。
- 用户账号、云同步、分享、公开部署。
- 扫描版 PDF 的自动 OCR（照片 OCR 已实现；PDF 扫描页仍只提示）。

## 照片 OCR 方法与坐标

- 使用 **RapidOCR 3.10.0 + ONNX Runtime CPU**，模型随 Python 包提供，本地推理。
- 调用 `return_word_box=True`。实测英文会直接返回**单词框**，本项目直接使用这些框，**不从整行框推算或伪造单词框**。
- 如果 OCR 只返回行级/字符级结果，单词点击不会生成假框；会显示“没有返回单词级坐标”的提示，句子仍可按行点击。
- 上传后先用 Pillow 做 EXIF 方向校正，再生成显示图和 OCR 缩放图；所有坐标按显示图宽高归一化为 `0..1`，与屏幕像素无关。
- 句子按 OCR 单词/行顺序和标点切分，每个句子有一组**按行片段**的点击框，避免多行句子的联合大框覆盖其他内容。
- 多栏、倾斜、低清晰度、手写批注会影响 OCR 识别顺序和准确率；当前没有自动去倾斜/去模糊。

详细方法和限制见 [docs/photo-ocr.md](docs/photo-ocr.md)。

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
| EPUB 显示 | EPUB.js 0.3.93 | 解析 EPUB、章节导航、可重排阅读 |
| 前端 | Vite 8 + 原生 JavaScript | 无需先学 React/Vue |
| 单词音频 | Wikimedia Commons 官方 API | 逐文件许可、作者和录音地址 |
| 整句音频 | Windows SAPI / System.Speech | 本机合成、明确标记、WAV 缓存 |
| 音频播放 | HTMLAudioElement | 播放 MP3/OGG/WAV |
| 音频缓存 | 本地文件 + JSON 元数据 | 避免重复请求/合成，保留来源和许可 |
| 照片 OCR | RapidOCR 3.10.0 + ONNX Runtime CPU | 本地运行、直接返回英文单词框 |
| 照片显示 | 原生图片 + 百分比点击层 | 原图显示、触摸缩放拖动 |
| 测试 | pytest + Node 内置 test runner | 后端 API/缓存/坐标/OCR 测试、前端 UI 单元测试 |

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
| PDF.js / EPUB.js / Vite | 已安装到 `frontend/node_modules`（EPUB.js 0.3.93） |
| 系统 curl | Windows 自带，可访问 Wikimedia |
| Windows SAPI | 已启用 Microsoft Zira / David（en-US） |
| RapidOCR / ONNX Runtime | **已安装**到 `.venv`，模型随包提供 |
| Tesseract / Docker | 不需要 |

单词真人录音、整句 TTS 和照片 OCR 都在本地处理；不需要 API Key。

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
pip install -r requirements-ocr.txt

cd frontend
npm install
cd ..
```

> `requirements-ocr.txt` 安装 RapidOCR、ONNX Runtime 和 Pillow；模型随 `rapidocr` 包提供，不需要额外下载系统 OCR 程序。

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

#### PDF
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
4. 用工具栏翻页、输入页码（Enter 跳转）、缩放或“适合宽度”。
5. 页面较长时在阅读区内滚动；点击区域与页面一起移动。

#### EPUB
1. 点击顶栏“EPUB”或首页“选择 EPUB”，也可以把 `.epub` 文件拖到首页。
2. EPUB.js 显示原书可重排内容；工具栏显示书名、作者、语言和章节数。
3. 点击“目录”打开章节列表，或使用“上一章 / 下一章”按 spine 切换。
4. 使用字号“− / + / 重置字号”调整正文大小（70%–180%）；文字会自动重排，长章节可滚动阅读。
5. **单词** 模式点击正文单词播放真人录音；**整句** 模式点击正文句子播放整句 TTS（明确标记合成语音）。
6. 章节切换会停止旧音频并重置结果；“点击模式”在 PDF、EPUB 和照片之间共用。

#### 手机照片
1. 在首页点击“拍照点读”打开手机相机，或点击“从相册选择”。
2. 上传后，原照片会显示在阅读区；底部工具栏显示照片尺寸。
3. 等待本机 OCR 完成。识别到英文后，单词和句子会有透明点击框。
4. 点词/点句模式与 PDF 相同：
   - 单词模式点击照片中的单词播放单词真人录音；
   - 整句模式点击句子播放整句 TTS（合成语音）。
5. 用双指缩放、拖动照片，或使用“− / + / 重置”；点击框与照片一起变换。
6. “重新拍摄”“替换照片”“清空”分别用于换一张或结束当前照片。

> 手机相机实际打开需要真实手机浏览器；桌面浏览器会退化为文件选择。自动化环境无法操作原生相机/文件对话框，因此相机入口仍需人工验收。

### 6. 手机访问（PDF、EPUB 和照片）

手机和电脑连接同一个 Wi-Fi：

1. Vite 已配置 `host: true`，启动后显示 Network 地址。
2. 手机浏览器打开 `http://<电脑局域网IP>:5173`。
3. `/api` 请求由 Vite 代理到电脑本机后端。
4. Windows 防火墙首次询问时只允许“专用网络”。

注意：当前没有登录鉴权，**只能在可信局域网使用**，不要做端口转发。

### 7. 停止服务

在两个终端分别按 `Ctrl+C`：

- 后端终端：停止 Uvicorn。
- 前端终端：停止 Vite。

停止服务不会删除 `data/` 中的书籍、照片或音频缓存。若终端已关闭但端口仍被占用：

```powershell
netstat -ano | findstr :8000
netstat -ano | findstr :5173

# 用上一步显示的 PID 结束残留进程（只结束你确认的本地开发进程）
taskkill /PID <PID> /F
```

## 排错

| 现象 | 检查 / 处理 |
| --- | --- |
| `py -3.12` 找不到 | 安装 Python 3.12，或用 `py -0p` 查看已注册版本 |
| `Activate.ps1` 被拒绝 | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` |
| 前端提示无法连接后端 | 确认 Uvicorn 在 `127.0.0.1:8000` 运行；访问 `/api/health` |
| 端口被占用 | 后端换端口并修改 `vite.config.js` 代理目标；前端换端口 |
| 照片 OCR 报依赖缺失 | `pip install -r requirements-ocr.txt`，确认在 `.venv` 中执行 |
| 照片没有识别文字 | 尽量正对书页、光线均匀、提高清晰度；查看照片下方提示 |
| 照片只显示提示但没有单词框 | OCR 没有返回单词级坐标，或页面不是英文；不会伪造单词框 |
| EPUB 打不开 | 确认文件未受 DRM/内容加密、是有效 EPUB 2/3；查看错误提示 |
| EPUB 没有可点击文字 | 图片页、固定版式或脚本化内容可能没有可点正文；先换一章确认 |
| EPUB 字号变化不明显 | 原书可能使用固定像素字号；正文继承字号会随按钮变化 |
| 手机打不开前端 | 同一 Wi-Fi、使用手机访问电脑局域网 IP、防火墙只放行专用网络 |
| 手机相机没有打开 | 真实手机浏览器才支持 `capture`；桌面浏览器会打开文件选择 |
| 没有单词录音 | 该词没有合适 Wikimedia 录音；换词或检查网络/代理设置 |
| 整句没有声音 | 确认 Windows 英文语音已安装；查看“合成语音不可用”提示 |
| 修改依赖后行为异常 | 重新激活 `.venv`，运行 `python scripts/check_env.py`，重启前后端 |

## 测试

```powershell
# 后端：坐标、PDF/EPUB 提取与 API、单词音频、整句 TTS、缓存
python -m pytest

# Python 代码检查
ruff check backend scripts

# 前端坐标、口音选项和 EPUB 文本切分测试
npm --prefix frontend test

# 前端生产构建
npm --prefix frontend run build
```

当前结果：

- 后端：**83 passed**（Phase 6 新增 12 个 EPUB API 测试）。
- 前端：**24 passed**（6 坐标 + 6 音频 UI + 12 EPUB 文本/目录）。
- 前端生产构建：成功（EPUB.js 使主包约 855 KB，gzip 约 256 KB）。
- Ruff：通过。
- 浏览器端到端：PDF 点读、EPUB 打开/目录/翻章/字号/点词/整句、真单词发音、整句 TTS、照片 OCR、缩放拖动和缓存均验证通过。

详细记录见 [docs/phase6-acceptance.md](docs/phase6-acceptance.md)；Phase 5 整合回归见 [docs/phase5-test-report.md](docs/phase5-test-report.md)，各阶段历史验收见 [docs/phase4-acceptance.md](docs/phase4-acceptance.md) 等文件。

## 目录结构

```text
vocabulary_audio/
├── AGENTS.md                     # 协作规则、技术选型、坐标契约、验收标准
├── README.md
├── start-vocabulary-audio.bat    # Windows 一键启动
├── stop-vocabulary-audio.bat     # Windows 一键停止
├── requirements.txt              # 后端运行依赖
├── requirements-dev.txt          # 测试/检查依赖
├── requirements-ocr.txt          # 照片 OCR 依赖（已安装）
├── pyproject.toml
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI 入口、统一错误映射
│   │   ├── config.py             # 数据目录、上传限制、音频/照片设置
│   │   ├── api/
│   │   │   ├── health.py
│   │   │   ├── books.py          # PDF 上传、文件、页面数据
│   │   │   ├── epubs.py          # EPUB 上传、容器校验、文件
│   │   │   ├── audio.py          # 单词音频、整句 TTS、缓存文件
│   │   │   └── photos.py         # 照片上传、OCR 数据、文件、删除
│   │   ├── services/
│   │   │   ├── books.py
│   │   │   ├── pdf_extractor.py
│   │   │   ├── epubs.py          # EPUB mimetype/container/OPF/spine 校验
│   │   │   ├── photo_ocr.py      # EXIF 校正、RapidOCR、单词/句子坐标
│   │   │   ├── audio_provider.py # Wikimedia Commons 候选/许可过滤
│   │   │   ├── audio_service.py  # 单词选择、下载、缓存、并发锁
│   │   │   ├── sentence_audio.py # 本机 Windows TTS、WAV 缓存
│   │   │   ├── wikimedia_http.py # curl/urllib 传输、限流和重试
│   │   │   └── errors.py
│   │   └── models/schemas.py
│   └── tests/                    # 83 个后端测试
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── src/
│   │   ├── main.js               # PDF/EPUB/照片切换、音频状态与工具栏
│   │   ├── api/client.js
│   │   ├── pdf/viewer.js
│   │   ├── pdf/coordinates.js
│   │   ├── epub/viewer.js        # EPUB.js 阅读、目录、翻章、字号、正文点读
│   │   ├── epub/text.js          # 取词、句子切分、目录 href 匹配
│   │   ├── photo/viewer.js       # 照片显示、缩放、拖动、点击层
│   │   ├── audio/audioPlayback.js # 音频元素、重复点击/取消/重播
│   │   ├── audio/audioMeta.js    # 口音选项和来源文本
│   │   └── styles/main.css
│   └── tests/                    # 坐标、音频 UI、EPUB 文本测试
├── data/                         # 私人数据，全部被 Git 忽略
│   ├── books/
│   ├── epubs/                    # 用户 EPUB + 元数据
│   ├── photos/                   # 校正后的照片 + 元数据
│   └── audio_cache/              # 真人录音和 TTS WAV 缓存 + 元数据
├── docs/
│   ├── environment.md
│   ├── audio-source.md           # 音频来源评估与合规说明
│   ├── photo-ocr.md              # OCR 方法、词框和限制
│   ├── phase1-acceptance.md
│   ├── phase2-acceptance.md
│   ├── phase3-acceptance.md
│   ├── phase4-acceptance.md
│   ├── phase5-test-report.md
│   └── phase6-acceptance.md
└── scripts/
    ├── check_env.py
    ├── start_vocabulary_audio.ps1 # 一键启动实现
    ├── stop_vocabulary_audio.ps1  # 一键停止实现
    └── tts_sapi.ps1              # Windows SAPI 本机语音合成
```

## 坐标是怎么对齐的

### PDF
1. PyMuPDF 返回未旋转页面坐标。
2. 后端用 `page.rotation_matrix` 转成实际显示方向，再归一化到 `0..1`。
3. 前端把归一化 bbox 转成相对页面容器的百分比。
4. canvas、句子层、单词层在同一个定位容器中，一起缩放和滚动。

### 照片
1. 上传后先用 EXIF 方向校正，再生成显示图和 OCR 缩放图。
2. RapidOCR 单词框按 OCR 缩放图宽高归一化；显示图和 OCR 图保持同一宽高比。
3. 图片、句子层、单词层在同一个 `photo-stage` 内；缩放/拖动只变换这个容器。
4. 因此点击框随图片一起缩放和移动，不需要重算屏幕坐标。

### EPUB
1. EPUB 是流式排版，没有固定页面坐标。
2. 点击时在 EPUB.js 的 iframe 内用 `caretRangeFromPoint` 找到文本节点和偏移，再按英文单词字符边界扩展。
3. 整句模式从最近的块级元素取文本，按标点切分后找到包含点击偏移的句子。
4. 不往原书 HTML 中插入单词框；字号、窗口或章节变化后，文字自动重排，点击逻辑仍然有效。

后端测试覆盖 PDF 旋转和照片 EXIF 方向；前端坐标测试覆盖归一化到像素/百分比的映射；EPUB 文本测试覆盖取词、句子切分和目录 href；浏览器验证对比了图片/点击框相对位置，并验证了 EPUB 翻章和字号变化后的点读。

## 隐私与数据

- 默认只监听 `127.0.0.1`，PDF、EPUB、照片和整页/整本内容不上传云端。
- 照片只上传到**本机** FastAPI，在本机用 RapidOCR 处理；不接入云端 OCR。
- EPUB 只上传到本机后端，由浏览器端 EPUB.js 解析；不调用第三方阅读或 DRM 服务。
- 为获取真人录音，只有**被点击的单词文本**会发送到 Wikimedia Commons API；整句文本只发送到本机后端，由本机 TTS 处理。
- 照片保存为 `data/photos/{uuid}.jpg`（去除 EXIF 方向后重新编码），旁边保存最小元数据；清空照片会删除当前文件。
- PDF 保存在 `data/books/`，EPUB 保存在 `data/epubs/`，音频缓存保存在 `data/audio_cache/`；这些目录都被 `.gitignore` 忽略。
- 缓存 JSON 包含来源 URL、许可证、作者、获取时间，便于审计和署名。
- 日志只记录 ID、页码和错误信息，不记录书籍正文或 OCR 文本。
- 请只处理你有权使用的书籍和照片；不要把受版权保护的文件提交到仓库。
- PyMuPDF 采用 AGPL-3.0 或商业许可；个人本地使用通常没问题，分发或公开托管前需要复核。

## 已知限制

- EPUB 只支持未加密、未受 DRM 保护的 EPUB 2/3；受 DRM 或内容加密的文件会被拒绝。
- EPUB 点读按正文点击位置取词/取句，不修改原 HTML；图片、表格中的非连续文本和脚本化内容可能无法点读。点击链接仍按 EPUB 自身链接行为处理。
- EPUB 字号缩放主要影响正文继承字号；原书用固定像素字号或复杂版式时，变化可能不完全一致。固定版式（pre-paginated）EPUB 的可重排效果取决于原书。
- EPUB 句子切分使用前端标点启发式，缩写、分号和异常标点可能导致句子边界不完美。
- EPUB.js 会增加前端包体积；生产构建约 855 KB（gzip 约 256 KB）。
- 不是每个英文单词都有 Wikimedia Commons 录音；没有时只显示明确提示，不回退到 TTS。
- 第一次获取某个词（或某个口音）需要联网；Wikimedia 可能限流，后端会按 `Retry-After` 等待并重试一次，页面显示“加载中”。成功后会缓存，之后立即播放。
- 整句使用本机 Windows TTS，**是合成语音，不是真人录音**；当前语音为系统英文语音（本机 Zira，en-US），不伪造英式/美式整句选项。
- 整句最长 500 个字符；更长的句子会提示“句子过长”，需要点击更短的句子。
- TTS 依赖 Windows `System.Speech` 和已安装英文语音；其他操作系统会返回明确的“语音合成不可用”错误，单词真人录音不受影响。
- 照片 OCR 依赖 RapidOCR/ONNX Runtime；模型对清晰、正对、单栏书页效果最好。
- OCR 英文实测能直接返回单词框；如果某些图片/语言只返回行级或字符级结果，本项目**不会**从行框推算假单词框，会显示提示并只保留句子点击。
- 倾斜、模糊、弱光、反光、手写批注、多栏排版会影响 OCR 和阅读顺序；当前没有自动去倾斜/去模糊/版面分析。
- 照片显示/OCR 会缩小超大图片：显示长边最多 3000px、OCR 长边最多 2000px；坐标仍归一化，因此不影响点击对齐。
- 手机真实相机入口依赖浏览器 `capture` 支持；自动化环境无法打开原生相机或文件对话框，需人工验收。桌面浏览器会退化为文件选择。
- 双指缩放/拖动已用指针事件和移动尺寸视口验证，但没有在真实手机上做多点触控人工验收。
- 原生文件选择框无法由自动化环境操作；已用文件输入 `change` 和拖放路径验证，仍建议人工点一次。
- 复杂多栏、表格、脚注、跨页句子的切分仍是启发式规则，需要更多真实书籍验证。
- 音频/照片/EPUB 缓存目前不会自动清理；清空照片会删除当前照片文件。
- 当前没有鉴权，不能公开部署。

## 路线图

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| Phase 0 | 环境、规则、目录、README、健康检查 | 已完成 |
| Phase 1 | PDF 上传、坐标提取、PDF.js 渲染、单词点击、翻页/缩放/滚动 | 已完成 |
| Phase 2 | 合法真人单词录音、来源/许可、口音选择、本地缓存 | 已完成 |
| Phase 3 | 整句点读：点词/点句模式、本机 TTS、合成语音标记、WAV 缓存 | 已完成 |
| Phase 4 | 手机拍照/选图 + 本机 RapidOCR + 照片点击层 + 缩放拖动 | 已完成 |
| Phase 5 | 整合、全面回归、边界/失败测试、日志脱敏、测试报告 | 已完成 |
| Phase 6 | EPUB 上传/解析 + EPUB.js 阅读 + 目录/翻章 + 字号重排 + 正文点读 | 已完成 |
| Phase 7 | 真人整句音频评估、收藏、学习记录 | 后续 |

## 相关文档

- [AGENTS.md](AGENTS.md)：技术规则、坐标契约、隐私规则、验收标准。
- [docs/audio-source.md](docs/audio-source.md)：单词录音、整句 TTS、许可、API 礼仪和替代方案。
- [docs/photo-ocr.md](docs/photo-ocr.md)：RapidOCR 方法、单词框、句子切分和限制。
- [docs/environment.md](docs/environment.md)：环境和依赖状态。
- [docs/phase1-acceptance.md](docs/phase1-acceptance.md)：PDF 点读验收。
- [docs/phase2-acceptance.md](docs/phase2-acceptance.md)：真人单词发音与缓存验收。
- [docs/phase3-acceptance.md](docs/phase3-acceptance.md)：整句点读、点词/点句模式和 TTS 缓存验收。
- [docs/phase4-acceptance.md](docs/phase4-acceptance.md)：手机照片导入、OCR、点读、缩放拖动验收。
- [docs/phase6-acceptance.md](docs/phase6-acceptance.md)：EPUB 打开、目录/翻章、字号重排、正文点读验收。
- [docs/phase5-test-report.md](docs/phase5-test-report.md)：Phase 5 整合回归、边界测试和已通过/未测试清单。

## 许可证

项目代码的许可证尚未确定。第三方依赖遵循各自许可证；仓库不包含书籍、照片或音频文件。缓存的录音只存在于本机 `data/audio_cache/`，并保留来源和许可信息。
