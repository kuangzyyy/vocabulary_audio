# AGENTS.md — 项目协作与开发规则

> 本文件是项目的协作契约。任何人（包括 AI 编程助手）在修改代码前都要先读它。
> 如果用户当次指令与本文件冲突，以用户当次指令为准，并在回复中说明差异和影响。

## 1. 项目目标

**Vocabulary Audio** 是一个本地优先的英语点读工具，核心体验是：**不改变原始版面，直接点击原文即可听发音。**

### MVP（第一版）只做三件事

1. **电脑端 PDF 点读**
   - 打开一本普通文本 PDF。
   - 用 PDF.js 按原始排版显示页面。
   - 点击页面中的英文单词，播放单词发音。
   - 点击例句，播放整句发音。
2. **手机端照片点读**
   - 拍照或从相册导入纸质书页面照片。
   - 对照片做 OCR，得到文字和坐标。
   - 在照片上点击单词或句子，播放发音。
3. **本地优先的音频**
   - Phase 2 使用 Wikimedia Commons 的合法真人单词录音，并缓存到本机。
   - 为获取未缓存录音，只发送被点击的单词文本；不发送 PDF、照片、整页/整本内容或用户身份。
   - 没有录音时明确提示，不使用 TTS 或其他合成语音冒充真人录音。

### 后续阶段才考虑

- EPUB 阅读。
- 单词收藏、生词本、学习记录。
- 下载并缓存来自合法来源的真人发音。
- 扫描版 PDF 的 OCR。
- 更好的例句切分、词典释义、翻译。

### 明确不在 MVP 内

- 用户账号、云同步、分享、公开部署。
- 批量处理整个书库、自动翻页。
- 原生手机 App（先使用移动浏览器）。
- 多语言 OCR（当前以英文点读为目标，中文界面）。
- 任何需要把私人书籍或照片上传到第三方云端的方案。

## 2. 当前阶段与状态

**阶段 2：真实单词发音（2026-10-20 完成）**

已完成：

- Phase 1 的 PDF 上传、原版渲染、单词/句子坐标、点击层、翻页/缩放/滚动全部保留。
- Wikimedia Commons 官方 MediaWiki API 音频查询；逐文件许可证、作者、来源页面。
- 只接受 Public domain、CC0、CC BY、CC BY-SA；拒绝 NC/ND、GFDL-only、许可不明和合成语音标记。
- 只接受 `En-us-*`、`En-uk-*`、`En-gb-*`、`LL-Q1860 (eng)-*` 等社区真人录音系列。
- 美式/英式选择：两种都存在时显示按钮；只有一种时只显示该口音；无法确定时显示“口音未标注”。
- 音频下载到 `data/audio_cache/`，旁边保存 JSON 元数据；重复请求直接命中缓存。
- 前端处理加载、播放、重复点击、切换单词、取消旧请求、播放失败、自动播放阻止和重播。
- 页面显示来源链接、许可证和作者；没有录音时显示明确提示，不使用 TTS 冒充。
- 后端 48 个测试、前端 12 个测试、生产构建和真实浏览器端到端验收通过。

尚未实现：

- 整句真人音频（当前点击句子只显示文本）。
- 手机照片 OCR 和照片点击层（RapidOCR 依赖未安装）。
- EPUB、收藏、学习记录。
- 扫描版 PDF 的 OCR。

阶段 2 完成标准：

- [x] 点击单词能播放真实真人录音。
- [x] 美式/英式都可用时提供选择；只有一种时不伪造第二个选项。
- [x] 音频来源和许可证有明确记录并在界面展示。
- [x] 成功获取的音频本地缓存，重复点击不重复下载。
- [x] 音频缺失、网络失败、播放失败有明确提示，页面不崩溃。
- [x] 重复点击、加载中切换单词、播放中断和重播行为已处理。
- [x] PDF 点读、翻页、缩放、滚动功能不回归。
- [ ] 原生文件选择框人工确认（自动化环境限制）。

阶段 1/0 的历史完成标准仍成立：

- [x] 打开真实 PDF，点击单词结果正确；翻页、缩放、滚动、旋转页对齐。
- [x] 扫描页明确提示；错误路径有测试；测试、构建、运行方式写入 README。
- [x] 环境、规则、目录、`.gitignore` 已建立。

## 3. 技术选型（2026-10-20 确定）

| 层次 | 选择 | 版本 / 要求 | 选择理由 |
| --- | --- | --- | --- |
| 操作系统 | Windows 10/11 | 当前机器 Win11 | 先服务当前开发环境，代码保持跨平台 |
| 后端语言 | Python | **3.12.x** | FastAPI、PyMuPDF、ONNX Runtime 新版本都要求 3.10+；3.9 已停止维护 |
| Web 框架 | FastAPI + Uvicorn | FastAPI 0.150.x / Uvicorn 0.54.x | 类型提示友好、自动生成接口文档、调试直观 |
| PDF 解析 | PyMuPDF | 1.26.x | 能直接拿到单词级 bbox、行和块结构，速度快 |
| 照片 OCR | RapidOCR + ONNX Runtime CPU | rapidocr 3.10.x / onnxruntime 1.31.x | 纯 pip 安装、模型随包提供、有文字坐标、支持中英文、无需 Tesseract |
| 前端构建 | Vite + 原生 JavaScript | Vite 8.x | 无需先学 React/Vue；热更新快，配置少 |
| PDF 显示 | PDF.js (`pdfjs-dist`) | 6.4.x | 保留原始排版，开源、浏览器兼容性好 |
| 音频（Phase 2） | Wikimedia Commons + 本地缓存 | 官方 API / HTMLAudioElement | 逐文件许可、真人录音、来源可追溯；缓存避免重复下载；不用 TTS 冒充 |
| 数据存储 | 文件系统 + SQLite（后续） | Python 内置 sqlite3 | Phase 2 只需要文件；收藏/记录阶段再引入 SQLite |
| 测试 | pytest + FastAPI TestClient + Node test runner | pytest 9.x / Node 24 | 后端 API/缓存/坐标测试、前端坐标与音频 UI 测试 |
| 代码检查 | Ruff | 0.17.x | 一个工具完成格式与基础 lint，初学者易用 |

### 3.1 当前机器环境基线

- Python：**3.12.10**，项目 `.venv` 已创建。
- Node.js：24.18.0（满足 PDF.js / Vite 要求）。
- npm：11.16.0（可用；npm registry 可访问）。
- Git：2.55.0（已配置用户名和邮箱）。
- `.venv` 已安装：FastAPI 0.150.0、Uvicorn 0.54.0、PyMuPDF 1.26.5、python-multipart 0.0.32、Pillow 11.3.0、pytest 9.1.1、httpx 0.28.1、Ruff 0.17.1。
- 前端已安装：`pdfjs-dist` 6.4.299、Vite 8.3.4。
- 音频功能不需要新增 Python 包或 API Key；优先使用系统 `curl` 访问 Wikimedia，`urllib` 作为兜底。
- 默认对 Wikimedia 直连（`VOCABULARY_AUDIO_USE_PROXY=0`）；如网络必须走系统代理，可设置 `VOCABULARY_AUDIO_USE_PROXY=1`。
- **未安装** RapidOCR 和 ONNX Runtime；Phase 3 实现照片 OCR 时执行 `pip install -r requirements-ocr.txt`。
- 未安装 Tesseract（本方案不需要）、Docker（本方案不需要）。
- PyPI 直连较慢，安装时使用了清华镜像；依赖版本仍以 requirements 文件为准。

### 3.2 为什么不用其他方案

- **Python 3.9**：已 EOL；最新 FastAPI 要求 3.10+，PyMuPDF 2.x 和 ONNX Runtime 最新版要求 3.11+。继续用 3.9 只能锁一堆旧版本，调试成本更高。
- **Python 3.13**：RapidOCR 官方文档以 3.12 验证为主；3.12 是兼容性最稳的折中。
- **PaddleOCR**：依赖 PaddlePaddle，Windows 安装和模型管理对初学者偏重。
- **EasyOCR**：需要 PyTorch，安装体积大、CPU 推理慢。
- **Tesseract**：需要额外安装系统程序；虽然词框直接，但多一个环境步骤。RapidOCR 已满足坐标需求，保留为备选而不是默认。
- **React/Vue**：MVP 是单页阅读器，原生 JavaScript 足够；少一层框架概念，问题更容易定位。
- **Electron / 原生 App**：当前目标是浏览器可用，前后端本地运行，暂不引入打包链。
- **云 OCR / 云 TTS**：违反本地优先原则，也会产生费用和隐私风险。
- **edge-tts 等非官方接口**：服务条款和稳定性都不可靠，禁止用于本项目。

### 3.3 许可证提醒

- PyMuPDF 采用 **AGPL-3.0 或商业许可**。个人本地使用没有问题；如果将来要分发或公开托管，必须重新评估许可证，或替换为许可证更宽松的方案。
- PDF.js 为 Apache-2.0；FastAPI、ONNX Runtime 等为宽松许可证。
- 用户提供的 PDF、照片只用于本地处理，不得提交到仓库。
- 后续接入真人音频时，必须逐条记录来源、许可证和署名信息。

## 4. 目录结构与职责

```text
vocabulary_audio/
├── AGENTS.md                 # 本文件：协作规则、技术选型、验收标准
├── README.md                 # 面向初学者的安装、启动和使用说明
├── .gitignore                # 阻止环境、缓存、私人数据和密钥入库
├── requirements.txt          # Phase 1/2 后端运行依赖
├── requirements-dev.txt      # 测试与代码检查依赖
├── requirements-ocr.txt      # Phase 3 OCR 依赖（当前未安装）
├── pyproject.toml            # pytest / ruff 配置
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI 入口、统一错误映射
│   │   ├── config.py         # 数据目录、上传限制、音频 User-Agent/代理
│   │   ├── api/              # health.py + books.py + audio.py
│   │   ├── services/         # books、pdf_extractor、audio_provider、audio_service、wikimedia_http
│   │   └── models/           # Pydantic 请求/响应模型
│   └── tests/                # 坐标、提取、音频、API 测试
├── frontend/
│   ├── index.html            # 阅读界面
│   ├── package.json          # 前端依赖与脚本
│   ├── vite.config.js        # 开发服务器和 /api 代理
│   ├── tests/                # 坐标和音频 UI 单元测试
│   └── src/
│       ├── main.js           # 文件选择、结果栏、工具栏、音频状态
│       ├── api/              # 后端请求封装
│       ├── pdf/              # PDF.js 渲染、点击层、坐标函数
│       ├── photo/            # 照片显示与点击层（Phase 3）
│       ├── audio/            # 真人音频控制、口音和来源展示
│       └── styles/           # 样式
├── data/                     # 运行时私人数据，全部被 git 忽略
│   ├── books/                # 用户 PDF
│   ├── photos/               # 用户照片
│   └── audio_cache/          # 真人录音缓存 + JSON 许可元数据
├── docs/
│   ├── environment.md        # 环境检查报告
│   ├── audio-source.md       # 音频来源、许可、API 礼仪和替代方案
│   ├── phase1-acceptance.md  # Phase 1 测试与浏览器验收记录
│   └── phase2-acceptance.md  # Phase 2 真人发音与缓存验收记录
└── scripts/
    └── check_env.py          # 随时重新检查本机环境
```

规则：

- `data/` 下是用户数据，**任何测试、脚本、清理命令都不能删除它**。
- 测试必须使用临时目录，不得读取或修改 `data/` 中的真实书籍和照片。
- 新增模块先放到对应目录；不要把所有逻辑堆进 `main.py` 或 `main.js`。

## 5. 核心数据流

### 5.1 电脑端 PDF

1. 用户选择 PDF，上传到**本机** FastAPI，保存为 `data/books/{uuid}.pdf`。
2. 后端用 PyMuPDF 按页提取单词、行、句子及 bbox。
3. 前端用 PDF.js 渲染原始页面 canvas。
4. 在 canvas 上方叠一层透明定位框：
   - 单词框：点击加载/播放真人录音。
   - 句子框/句末按钮：点击显示整句；整句音频尚未接入。
5. 页面缩放或窗口变化时，按归一化坐标重新计算像素位置。
6. 如果某页没有文本层（扫描页），返回明确的“未检测到可点击文字”，不要显示空白层。

### 5.2 手机端照片

1. 手机浏览器用 `<input type="file" accept="image/*" capture="environment">` 拍照或选图。
2. 图片上传到本机后端，保存到 `data/photos/`。
3. 后端先做 EXIF 方向校正，再缩小到适合 OCR 的尺寸（长边约 2000px）。
4. RapidOCR 返回文字行和字符/单词坐标。
5. 服务层把字符框合并成单词框，并按图片宽高归一化。
6. 前端显示图片和透明点击层，单词/句子播放发音。
7. 原始照片和识别文本只留在本机。

### 5.3 音频

Phase 2（当前实现）：

1. 点击单词后，前端请求 `GET /api/audio/word?text=<word>&accent=auto`。
2. 后端规范化单词，通过 Wikimedia Commons 官方 API 查询 `En-us-*`、`En-uk-*`、`En-gb-*` 和 Lingua Libre 录音候选。
3. 只保留许可证明确（Public domain、CC0、CC BY、CC BY-SA）且不含合成语音标记的社区真人录音。
4. `auto` 优先美式，其次英式，再其次未标注口音；返回全部可用口音，前端只在确实存在两种时显示美式/英式按钮。
5. 下载 MP3 转码（没有时用原始 OGG/WAV），保存到 `data/audio_cache/<sha256><ext>`，并写同名 `.json` 元数据：单词、口音、来源页、许可证、作者、获取时间等。
6. 前端使用一个 `HTMLAudioElement`：重复点击同一个词/口音直接重播；切换单词取消旧请求并暂停旧音频；翻页/换书停止播放；加载、播放、失败、自动播放阻止都有明确状态。
7. 没有录音时不回退到 TTS，只显示“没有找到可合法使用真人录音”。

访问与合规规则：

- 只使用官方 API，不抓取网页、不绕过服务条款、不使用 API Key。
- 默认直连 Wikimedia；系统代理出口可能被限流。代理只影响 Wikimedia 请求，不影响本地 API。
- 请求带明确 User-Agent，API 查询之间至少间隔 0.5 秒；媒体下载失败按 `Retry-After` 重试一次。
- 缓存键：`sha256("wikimedia-commons|v1|word|accent")`。
- 缓存元数据必须保留来源、许可证、作者；前端必须显示来源链接和许可证。
- 只发送被点击的单词文本；**不发送 PDF、照片、整页/整本识别文本或用户身份**。

整句音频尚未实现；点击句子目前只显示文本，不播放声音。

后续（Phase 4）：

- 评估整句音频的合法来源和更细的音频 Provider 接口。
- 下载失败或没有音频时，如果将来引入 TTS，必须在界面明确标注为合成语音，不能称为真人录音。
- 禁止抓取未授权接口或绕过服务条款。

## 6. 坐标契约（最容易出错，必须遵守）

前后端只交换**归一化视觉坐标**：

```text
原点：页面/图片左上角
x 轴：向右
y 轴：向下
范围：0.0 ~ 1.0
矩形：[x0, y0, x1, y1]，且 x1 > x0，y1 > y0
```

具体规则：

1. PDF 后端拿到的 PyMuPDF 文本坐标是**未旋转页面坐标**。必须先用 `page.rotation_matrix` 转成页面实际显示方向，再除以 `page.rect` 的宽高。不要直接把 PyMuPDF 坐标当屏幕坐标。
2. 前端 PDF.js 默认按页面 rotation 渲染；它只需要把归一化坐标乘以当前 viewport 的宽高，不要再做翻转或旋转。
3. 照片 OCR 必须先做 EXIF 方向校正；OCR 用缩放图时，坐标要除以缩放图的宽高，得到与显示图无关的归一化值。
4. 不要把 PDF point、图片像素、CSS 像素、设备像素混在同一个字段里。
5. API 同时返回页面/图片的原始宽高和 rotation，便于调试；前端布局只依赖归一化坐标。
6. 任何涉及坐标的新功能，都必须补一个单元测试，至少覆盖：普通页面、缩放比例变化、旋转页面（PDF）、横竖照片（OCR）。
7. 点击层必须和 canvas/图片使用同一个容器尺寸；缩放时一起重算。

## 7. API 实现状态

| 方法 | 路径 | 状态 | 作用 |
| --- | --- | --- | --- |
| GET | `/api/health` | 已实现 | 返回服务状态，用于确认环境 |
| POST | `/api/books` | 已实现 | 上传 PDF，返回 book_id、页数、标题和大小 |
| GET | `/api/books/{book_id}/file` | 已实现 | 返回原 PDF 给 PDF.js 渲染 |
| GET | `/api/books/{book_id}/pages/{page}` | 已实现 | 返回该页单词、行、句子和归一化坐标 |
| POST | `/api/photos` | Phase 3 | 上传照片并执行 OCR |
| GET | `/api/photos/{photo_id}/file` | Phase 3 | 返回校正方向后的照片 |
| GET | `/api/audio/word?text=...&accent=auto` | 已实现 | 查询/下载真人单词录音，返回口音、可用口音、来源和许可 |
| GET | `/api/audio/cache/{cache_id}` | 已实现 | 返回本地缓存的音频文件 |
| POST | `/api/audio/speak` | 后续 | 整句音频（尚未设计） |

实现约定：

- `POST /api/books` 使用 multipart 上传，默认最大 100 MB；文件用 UUID 重命名，元数据写入 `data/books/{book_id}.json`。
- 上传会校验文件头、能否打开、是否加密、是否至少有一页；错误通过统一 JSON `{"detail": "中文说明"}` 返回。
- `pages/{page}` 的页码从 1 开始；页码越界返回 404，提取异常返回 422。
- 扫描页不是错误：返回 `has_text=false`、`is_scanned=true` 和明确 `message`。
- `GET /api/audio/word` 的 `accent` 只接受 `auto`、`us`、`uk`；没有合适录音返回 404，上游网络失败返回 502，限流返回 503。
- 音频响应必须包含 `source_page`、`provider`、`license`、`attribution` 和 `audio_url`；前端必须展示来源和许可证。
- 音频缓存文件与 JSON 元数据只能位于 `data/audio_cache/`；`cache_id` 必须是 64 位十六进制 SHA-256。

页面数据示例（当前返回格式）：

```json
{
  "book_id": "0123456789abcdef0123456789abcdef",
  "page": 1,
  "page_count": 10,
  "width": 612,
  "height": 792,
  "rotation": 0,
  "has_text": true,
  "is_scanned": false,
  "message": null,
  "words": [
    {
      "id": "w-1-0-0",
      "text": "example",
      "bbox": [0.12, 0.24, 0.2, 0.26],
      "line_id": "l-1-0",
      "sentence_id": "s-1-0"
    }
  ],
  "lines": [
    { "id": "l-1-0", "text": "This is an example sentence.", "bbox": [0.1, 0.24, 0.6, 0.26] }
  ],
  "sentences": [
    { "id": "s-1-0", "text": "This is an example sentence.", "bbox": [0.1, 0.24, 0.6, 0.26] }
  ]
}
```

照片 OCR 返回结构保持同样的 `words` / `lines` / `sentences` 字段，另加 `photo_url` 和图片尺寸，方便前端复用点击层。

## 8. 隐私与安全规则（不可妥协）

1. **默认只监听 `127.0.0.1`。** 手机测试时通过 Vite 的局域网地址访问，由 Vite 代理转发到本机后端；不要把服务直接暴露到公网。
2. 不接入云端 OCR、云端 TTS、统计 SDK、错误上报 SDK。
3. 不上传用户的 PDF、照片、整页/整本识别文本到任何第三方。**唯一例外**：为获取未缓存真人录音，只向 Wikimedia Commons API 发送被点击的单词文本；不得附带书名、页面文字、文件或身份信息。
4. 上传文件必须：校验类型和大小、使用 UUID 文件名、限制在 `data/` 内、防止路径穿越。
5. 日志只记录 ID、耗时和错误码；**不要打印识别文本、书籍内容或图片路径中的私人信息**。
6. `.env`、密钥、证书、令牌不得提交；只允许提交 `.env.example`（如果以后需要）。
7. 用户必须自己拥有所处理书籍和照片的使用权；仓库里不得提交受版权保护的书籍或私人照片。
8. 音频只使用合法来源，并保存许可证和署名元数据；找到但不合规的录音必须丢弃，不得静默使用。
9. 不把 TTS 或任何机器合成语音标记为真人录音；没有真人录音时明确提示。

## 9. 开发规则

### Python

- 目标版本 Python 3.12；使用类型提示和 `pathlib.Path`。
- 公共函数写简短 docstring，说明输入、输出和副作用。
- 用 Ruff 检查，行宽 100。
- 路由层只做参数校验和调用 service；业务逻辑放 `services/`。
- 时间使用带时区的 UTC；用户可见文本用中文。
- 不把大文件读进内存后再无限制处理；上传和 OCR 都要有大小上限。

### JavaScript

- 使用 ES modules，不引入前端框架。
- 网络请求统一放到 `src/api/`，不要在 UI 模块里散落 `fetch`。
- 函数保持短小；坐标计算单独成函数并写测试或浏览器手工验证步骤。
- 使用 `const`/`let`，避免全局变量。
- CSS 放在 `src/styles/`，使用响应式布局，先保证桌面和手机竖屏可用。

### 依赖与变更

- 优先使用标准库和已有依赖。
- 新增依赖前说明用途、体积、许可证和维护状态；重型依赖（>100MB）必须先征得用户同意。
- 不擅自更换本文件第 3 节的技术栈；确需调整时，先说明原因和替代方案，再更新本文件。
- 一次只做一个小目标，不顺手重构无关代码。
- **禁止删除或覆盖 `data/` 中的用户文件。** 覆盖代码前先确认没有未提交的用户改动。
- 不运行 `git reset --hard`、`git clean -fdx` 等可能丢失数据的命令。

### 文档

- README 面向初学者：每一步都能复制执行，解释“为什么”。
- 技术决策和限制写进本文件或 `docs/`，不要只留在聊天记录里。
- 完成一个阶段后更新“当前阶段与状态”和验收清单。

## 10. 常用命令（目标环境：Python 3.12）

```powershell
# 1. 创建并激活虚拟环境（在项目根目录）
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. 安装后端依赖
python -m pip install --upgrade pip
pip install -r requirements-dev.txt

# 3. 启动后端
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000

# 4. 运行后端测试与代码检查
python -m pytest
ruff check backend scripts

# 5. 安装并启动前端（另开一个终端）
cd frontend
npm install
npm test
npm run dev

# 6. 构建前端
npm run build

# 7. 重新检查本机环境
python scripts/check_env.py

# 8. Phase 3 才需要：安装照片 OCR 依赖
pip install -r requirements-ocr.txt
```

启动后：

- 前端：<http://127.0.0.1:5173>
- 后端健康检查：<http://127.0.0.1:8000/api/health>
- FastAPI 接口文档：<http://127.0.0.1:8000/docs>

手机访问（仅可信局域网）：

- Vite 已配置 `host: true`，启动后会显示 Network 地址。
- 手机和电脑连同一个 Wi-Fi，访问 `http://<电脑局域网IP>:5173`。
- `/api` 请求由 Vite 代理到电脑上的 `127.0.0.1:8000`，后端不需要暴露到局域网。
- Windows 防火墙首次询问时只允许“专用网络”。
- 当前没有登录鉴权，绝不能做端口转发或公网映射。

## 11. 测试与验收

### 阶段 0 验收（历史，已完成）

- [x] `python scripts/check_env.py` 能清楚列出已安装/缺失项。
- [x] Python 版本不足、需要安装 3.12 的事实已写入 README 和环境报告。
- [x] 目录结构、AGENTS.md、README.md、`.gitignore` 已创建。
- [x] 后端健康检查代码存在。
- [x] 前端占位页能通过 `npm run build`。
- [x] 工作区原有文件未被删除（检查时工作区为空）。

### 阶段 1 验收（历史，已完成）

- [x] 打开自建的 4 页测试 PDF（含扫描页和 90° 旋转页）。
- [x] 打开真实的 15 页 arXiv PDF，页面和文字层正常。
- [x] 原版页面由 PDF.js 渲染，没有用重排文本替代。
- [x] 点击单词后，识别结果与页面文字一致。
- [x] 点击句子内空白处，显示整句（当时使用模拟提示音）。
- [x] 翻页、页码输入（Enter）正常。
- [x] 缩放（205% → 245%）后，点击框相对 canvas 的位置与后端 bbox 一致。
- [x] 滚动 700px 后，点击框相对 canvas 的位置仍一致。
- [x] 90° 旋转页保持横向显示，点击框仍在正确位置。
- [x] 扫描页返回明确提示，且没有生成假单词框。
- [x] 损坏 PDF 显示错误，不崩溃；旧页面保持可用。
- [x] 当时后端 23 个测试、前端 6 个坐标测试通过。
- [x] `ruff check backend scripts` 和 `npm run build` 通过。
- [ ] 真实点击“打开 PDF”按钮后的系统文件对话框人工确认（自动化环境限制）。

### 阶段 2 验收（已完成）

- [x] 点击 `Hello` 播放 Wikimedia Commons 美式真人录音；可切换到英式录音。
- [x] 两种口音都存在时显示“美式/英式”按钮；只有一种时只显示该口音。
- [x] 页面显示来源页面、许可证和作者（例如 Dvortygirl、Shtooka/Judith Franck）。
- [x] 重复点击同一单词直接重播，不重复请求音频 API。
- [x] 缓存命中时返回 `cached=true`；浏览器播放缓存的 MP3。
- [x] 只有美式录音的 `sentence` 不显示伪造的英式选项。
- [x] 只有英式录音的 `Click` 不显示伪造的美式选项。
- [x] 无录音的 `Rotated` 显示明确提示，页面和 PDF 点击层保持可用。
- [x] 加载中、播放中、播放完成、失败状态有界面反馈。
- [x] 翻页会停止当前音频；切换单词会取消旧请求并暂停旧音频。
- [x] PDF 翻页、缩放 245%、滚动 700px 后点击框仍对齐。
- [x] 后端 48 个测试、前端 12 个测试通过；Ruff 和前端构建通过。
- [ ] 原生文件选择框人工确认（自动化环境限制）。

### MVP 验收（Phase 1–3）

电脑端：

- [x] 能选择一个普通文本 PDF 并显示原始页面。
- [x] 单词位置与原文对齐，缩放、滚动、旋转后仍对齐。
- [x] 点击英文单词能显示准确结果并播放真人录音。
- [ ] 点击例句能播放整句真人音频（当前只显示整句文本）。
- [x] 没有真人录音、网络失败或播放失败时有明确提示。
- [x] 扫描页能被识别为“无文本层”，有明确提示。

手机端：

- [ ] 能拍照或从相册导入照片。
- [ ] 横拍、竖拍照片方向正确。
- [ ] OCR 后能在照片上点单词和句子。
- [ ] 照片放大/缩小后点击框仍对齐。
- [ ] 处理过程中没有数据发往外部网络（音频例外：未缓存单词文本会发送到 Wikimedia Commons）。

隐私与工程：

- [x] 默认监听 `127.0.0.1`；手机测试仅通过可信局域网。
- [x] `data/`、`.venv/`、`node_modules/`、`.env` 未进入 Git。
- [x] 音频只发送被点击的单词文本，不发送书籍/照片/整页内容。
- [x] 音频来源、许可证、作者保存在缓存元数据并在界面展示。
- [x] `python -m pytest` 全部通过。
- [x] `ruff check backend scripts` 通过。
- [x] `npm run build` 通过。
- [x] `npm test` 通过。
- [x] README 提供完整的安装、启动和测试步骤。

性能目标（普通笔记本，CPU）：

- 单页 PDF 文本提取 < 1 秒。
- 长边 2000px 的照片 OCR < 10 秒。
- 页面/照片切换后点击层在 300ms 内可用。

### 完成定义

一个功能只有同时满足以下条件才算完成：

1. 行为符合本文件的 MVP 范围。
2. 有必要的自动化测试或可重复的手工验收步骤。
3. 不引入隐私、许可证或数据安全问题。
4. README / AGENTS 中的说明已同步更新。
5. 用户能在真实浏览器中完成操作，而不只是接口返回 200。

## 12. 已知风险与限制

- **PDF 旋转**：PyMuPDF 文本坐标是未旋转坐标，PDF.js 默认旋转渲染；当前已按第 6 节转换，并用 90° 页面验证；其他旋转角度有单元测试但还没有真实书籍样本。
- **整句点击**：当前点击句子只显示文本，不播放音频；后续可增加明确的整句播放按钮和合法音频来源。
- **音频覆盖**：不是每个单词都有 Wikimedia Commons 录音；没有时只提示，不回退到 TTS。
- **首次获取延迟**：未缓存单词需要联网查询/下载；Wikimedia 可能限流，后端按 `Retry-After` 等待并重试一次，成功后会缓存。
- **网络与代理**：默认对 Wikimedia 直连；如果网络必须走系统代理，可设置 `VOCABULARY_AUDIO_USE_PROXY=1`。curl 缺失时使用 urllib；两者都可能受网络影响。
- **音频格式**：优先使用 Wikimedia 的 MP3 转码；没有转码时使用 OGG/WAV。当前浏览器验证基于 Chromium；其他浏览器对 OGG 的支持需另行验证。
- **缓存增长**：缓存不会自动清理；移除缓存会丢失来源和许可元数据，清理策略尚未实现。
- **来源变化**：Wikimedia 文件可能被重命名或删除；已缓存音频仍可播放，但来源页可能失效。
- **扫描版 PDF**：没有文本层，当前只提示、不 OCR；后续可把页面渲染成图片后复用照片 OCR。
- **OCR 依赖尚未安装**：RapidOCR/ONNX Runtime 未进入 `.venv`，Phase 3 前需执行 `pip install -r requirements-ocr.txt`。
- **OCR 词框**：RapidOCR 的词级结果可能是字符级框，需要按空格和标点合并成英文单词；必须用真实书页照片验证。
- **OCR 准确率**：低清晰度、倾斜、反光、手写批注都会降低效果；MVP 先接受并展示识别结果，不做自动纠错。
- **PDF 兼容性**：损坏、下载不完整或异常结构的 PDF 可能被 PDF.js 拒绝；当前会显示错误。PyMuPDF 和 PDF.js 对异常文件的宽容度不同。
- **原生文件选择框**：自动化环境无法操作系统文件对话框；已通过文件输入 `change` 事件和拖放路径验证同一处理逻辑，仍需人工点击一次确认。
- **移动端网络**：手机访问依赖同一 Wi-Fi 和防火墙放行；Vite 开发服务器不适合长期公开运行。
- **PyMuPDF 许可证**：AGPL-3.0 或商业许可；分发前必须复核。
- **大文件**：大 PDF 和高分辨率照片要限制大小，按页/按需处理，避免一次读入全部内容。
- **隐私例外**：未缓存单词的文本会发送到 Wikimedia Commons；不得把书籍/照片/整页内容或身份信息附带发送。

## 13. 路线图

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| Phase 0 | 环境、规则、目录、README、健康检查 | 已完成 |
| Phase 1 | PDF 上传 + PyMuPDF 文字/坐标 + PDF.js 渲染 + 单词点击 + 翻页/缩放/滚动 | 已完成 |
| Phase 2 | Wikimedia Commons 真人单词录音 + 来源/许可 + 口音选择 + 本地缓存 | 已完成 |
| Phase 3 | 手机拍照/选图 + RapidOCR + 照片点击层 | 待开始 |
| Phase 4 | 整句音频、更多合法音频来源、缓存清理策略 | 后续 |
| Phase 5 | EPUB、收藏、学习记录（SQLite） | 后续 |

**下一阶段默认 Phase 3 手机照片 OCR；不要提前实现 Phase 4–5。整句音频仍待后续阶段。**

## 14. 变更记录

- **2026-10-20**：完成阶段 0；确定 Python 3.12 + FastAPI + PyMuPDF + RapidOCR + Vite/PDF.js 技术栈；创建项目骨架。
- **2026-10-20**：完成 Phase 1；实现 PDF 上传、逐页单词/句子/坐标提取、PDF.js 原版渲染、透明点击层、翻页/缩放/滚动、模拟反馈、错误处理；后端 23 个测试、前端 6 个测试和真实 PDF 浏览器验收通过。
- **2026-10-20**：完成 Phase 2；接入 Wikimedia Commons 合法真人单词录音，加入逐文件许可/作者校验、美式/英式选择、本地缓存和来源展示；后端 48 个测试、前端 12 个测试、真实浏览器音频验收通过。整句音频仍未实现。
