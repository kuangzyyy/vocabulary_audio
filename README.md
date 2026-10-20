# Vocabulary Audio

一个**本地优先**的英语点读工具：在电脑上打开 PDF，直接点击原始页面里的英文单词就能听到反馈；在手机上拍下纸质书页面后，也能点击照片里的单词或句子（照片 OCR 在 Phase 3 实现）。

> **当前状态：Phase 1 已完成（2026-10-20）**
>
> 已实现：打开 PDF、PDF.js 原版页面渲染、PyMuPDF 单词/句子坐标提取、
> 透明点击层、点击单词显示识别结果、模拟发音反馈、翻页、缩放、滚动、
> 扫描页提示和错误处理。
>
> 尚未实现：真人发音、照片 OCR、EPUB、收藏和学习记录。

## 现在能做什么

- 用“打开 PDF”按钮、拖放或文件选择打开普通文本 PDF。
- PDF.js 按原始排版显示页面，不会用重排的纯文本替代原书。
- 点击页面上的英文单词，底部会显示准确识别出的单词，并播放一声本地模拟提示音。
- 点击句子内部的空白处（单词之间的空隙），会显示整句并模拟播放整句。
- 支持上一页/下一页、页码输入、放大/缩小、“适合宽度”和页面滚动。
- 缩放或滚动后，透明点击区域仍然跟随原页面文字。
- 打开扫描版页面时明确提示“暂不支持 OCR”，不会假装识别成功。
- 文件为空、不是 PDF、加密 PDF、页码越界、页面提取失败都有中文错误提示。
- 所有 PDF 只保存在本机，不上传云端。

## 暂不实现

- 真人单词/句子音频（当前只有模拟提示音）。
- 手机照片 OCR（RapidOCR 依赖已拆分到后续阶段）。
- EPUB、单词收藏、生词本、学习记录。
- 用户账号、云同步、分享、公开部署。
- 扫描版 PDF 的 OCR。

## 技术栈

| 部分 | 选择 | 作用 |
| --- | --- | --- |
| 后端 | Python 3.12 + FastAPI + Uvicorn | 本地 API 服务 |
| PDF 解析 | PyMuPDF 1.26.5 | 提取单词、行、句子和坐标 |
| PDF 显示 | PDF.js 6.4.299 | 保留原始排版渲染 |
| 前端 | Vite 8 + 原生 JavaScript | 无需先学 React/Vue |
| 音频（Phase 1） | Web Audio 模拟提示音 | 不依赖网络；真人音频后续接入 |
| 照片 OCR（Phase 3） | RapidOCR + ONNX Runtime | 本地运行、返回文字坐标 |
| 测试 | pytest + Node 内置 test runner | 后端 API/坐标测试、前端坐标测试 |

更详细的选型理由、坐标契约和开发规则见 [AGENTS.md](AGENTS.md)。

## 当前环境状态

检查日期：**2026-10-20**。详细记录见 [docs/environment.md](docs/environment.md)。

| 项目 | 状态 |
| --- | --- |
| Python | **3.12.10 已安装**，项目 `.venv` 已创建 |
| Node.js | 24.18.0，满足要求 |
| npm | 11.16.0，满足要求 |
| Git | 2.55.0，满足要求 |
| FastAPI / Uvicorn / PyMuPDF | 已安装到 `.venv` |
| Pillow / pytest / httpx / Ruff | 已安装到 `.venv`（开发与测试用） |
| PDF.js / Vite | 已安装到 `frontend/node_modules` |
| RapidOCR / ONNX Runtime | **未安装**；Phase 3 需要时执行 `pip install -r requirements-ocr.txt` |
| Tesseract / Docker | 不需要 |

一键复查：

```powershell
.\.venv\Scripts\python.exe scripts\check_env.py
```

## 快速开始（Windows / PowerShell）

### 1. 激活虚拟环境

在项目根目录执行：

```powershell
.\.venv\Scripts\Activate.ps1
```

如果 PowerShell 禁止运行脚本，只需对当前用户放行一次：

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

> Phase 1 不需要 OCR。等实现照片点读时再执行
> `pip install -r requirements-ocr.txt`。

### 3. 启动后端

在项目根目录、已激活虚拟环境的终端中：

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

前端开发服务器会把 `/api` 请求代理到本机的 `http://127.0.0.1:8000`。

### 5. 使用

1. 点击“打开 PDF”或把 PDF 拖入页面。
2. 点击页面中的英文单词，底部“当前识别”会显示单词，并播放模拟提示音。
3. 点击句子中单词之间的空白处，会显示并模拟播放整句。
4. 用工具栏翻页、输入页码（按 Enter 跳转）、放大/缩小或“适合宽度”。
5. 页面较长时在阅读区内滚动；点击区域会和原页面一起移动。

### 6. 手机访问（PDF 当前也可用）

手机和电脑连接同一个 Wi-Fi：

1. Vite 已配置 `host: true`，启动时会显示 `Network:` 地址。
2. 在手机浏览器打开 `http://<电脑局域网IP>:5173`。
3. `/api` 请求由 Vite 代理到电脑本机后端，后端不需要直接暴露。
4. Windows 防火墙首次询问时只允许“专用网络”。

注意：当前没有登录鉴权，**只能在可信局域网使用**，不要做端口转发。

## 测试

```powershell
# 后端：坐标、PDF 提取、API、错误处理
python -m pytest

# Python 代码检查
ruff check backend scripts

# 前端坐标映射测试
npm --prefix frontend test

# 前端生产构建
npm --prefix frontend run build
```

当前结果：

- 后端：**23 passed**。
- 前端坐标测试：**6 passed**。
- 前端生产构建：成功。
- Ruff：通过。
- 浏览器端到端验证：真实 15 页论文和 4 页测试 PDF 均验证通过。

详细的浏览器验收记录和未解决问题见 [docs/phase1-acceptance.md](docs/phase1-acceptance.md)。

## 目录结构

```text
vocabulary_audio/
├── AGENTS.md                     # 协作规则、技术选型、坐标契约、验收标准
├── README.md
├── requirements.txt              # Phase 1 后端依赖
├── requirements-dev.txt          # 测试/检查依赖
├── requirements-ocr.txt          # Phase 3 OCR 依赖（当前不需要安装）
├── pyproject.toml                # pytest / ruff 配置
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI 入口、错误映射
│   │   ├── config.py             # 数据目录和上传限制
│   │   ├── api/
│   │   │   ├── health.py         # GET /api/health
│   │   │   └── books.py          # 上传、文件、页面数据接口
│   │   ├── services/
│   │   │   ├── books.py          # 本地存储、上传校验、页面编排
│   │   │   ├── pdf_extractor.py  # PyMuPDF 单词/句子/坐标提取
│   │   │   └── errors.py         # 用户可见错误
│   │   └── models/schemas.py     # API 响应模型
│   └── tests/                    # 23 个后端测试
├── frontend/
│   ├── index.html                # 阅读界面
│   ├── package.json
│   ├── vite.config.js            # 端口和 /api 代理
│   ├── src/
│   │   ├── main.js               # 文件选择、结果栏、工具栏
│   │   ├── api/client.js         # 后端请求
│   │   ├── pdf/viewer.js         # PDF.js 渲染和透明点击层
│   │   ├── pdf/coordinates.js    # 归一化坐标 -> 百分比的纯函数
│   │   ├── audio/simulatedAudio.js
│   │   └── styles/main.css
│   └── tests/coordinates.test.js # Node 内置测试
├── data/                         # 私人数据，全部被 Git 忽略
│   ├── books/
│   ├── photos/
│   └── audio_cache/
├── docs/
│   ├── environment.md
│   └── phase1-acceptance.md
└── scripts/check_env.py
```

## 坐标是怎么对齐的

1. PyMuPDF 返回的是**未旋转页面坐标**。
2. 后端用 `page.rotation_matrix` 转成实际显示方向，再除以页面宽高，得到 `0..1` 的归一化坐标。
3. 前端把每个框的 `x0/y0/x1/y1` 转成相对页面容器的百分比。
4. 页面 canvas、句子层和单词层在同一个定位容器中，一起缩放和滚动。
5. 因此翻页、缩放、滚动都不需要写死屏幕坐标。

后端有旋转 0/90/180/270 的坐标测试；前端有“页面尺寸变化后框仍按比例缩放”的测试；浏览器验证还对比了每个框在 canvas 中的相对位置与后端 bbox。

## 隐私与数据

- 默认只监听 `127.0.0.1`，书籍、照片和识别文本不上传云端。
- PDF 保存在 `data/books/`，照片将来保存在 `data/photos/`，都已被 `.gitignore` 忽略。
- 日志只记录 ID、页码和错误信息，不记录书籍正文。
- 请只处理你有权使用的书籍和照片；不要把受版权保护的文件提交到仓库。
- PyMuPDF 采用 AGPL-3.0 或商业许可；个人本地使用没问题，将来分发或公开托管前需要复核。

## 已知限制

- 句子播放目前需要点击句子内**单词之间的空白处**；直接点单词会播放单词。
- 只有模拟提示音，没有真人发音。
- 扫描版 PDF 会明确提示，但暂不支持 OCR。
- RapidOCR/ONNX Runtime 尚未安装，照片功能留到 Phase 3。
- PDF 文本提取和句子切分是启发式规则；复杂多栏、表格、跨行句子的效果还需要更多真实书籍验证。
- 损坏或下载不完整的 PDF 会被拒绝；PDF.js 与 PyMuPDF 对异常文件的宽容度可能不同。
- 浏览器自动化无法操作系统原生文件选择框；本次端到端测试通过文件输入的 `change` 事件和拖放路径验证，真实点击按钮选文件需要人工再确认一次。
- 当前没有鉴权，不能公开部署。

## 路线图

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| Phase 0 | 环境、规则、目录、README、健康检查 | 已完成 |
| Phase 1 | PDF 上传 + 文本/坐标 + PDF.js 渲染 + 单词点击 + 模拟播放 + 翻页缩放滚动 | 已完成 |
| Phase 2 | 例句切分/整句播放、阅读体验打磨 | 基础版已包含，继续打磨 |
| Phase 3 | 手机拍照/选图 + RapidOCR + 照片点击层 | 待开始 |
| Phase 4 | 合法音频来源与缓存 | 后续 |
| Phase 5 | EPUB、收藏、学习记录（SQLite） | 后续 |

## 相关文档

- [AGENTS.md](AGENTS.md)：技术规则、坐标契约、隐私规则、验收标准。
- [docs/environment.md](docs/environment.md)：当前环境和依赖状态。
- [docs/phase1-acceptance.md](docs/phase1-acceptance.md)：本次测试结果、浏览器验收和未解决问题。

## 许可证

项目代码的许可证尚未确定。第三方依赖遵循各自许可证；仓库不包含书籍、照片或受版权保护的音频。
