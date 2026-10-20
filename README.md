# Vocabulary Audio

一个**本地优先**的英语点读工具：在电脑上打开 PDF，直接点击原始页面里的英文单词或例句就能听发音；在手机上拍下纸质书页面，也能点击照片里的单词和句子听发音。

> **当前状态：阶段 0（项目骨架）**
>
> 现在已经完成环境检查、项目规则、目录结构、依赖清单和一个最小的健康检查接口。
> **PDF 点读、照片 OCR、发音功能还没有实现**，前端目前只是占位页。
> 下一阶段从“普通文本 PDF 的单词点击发音”开始。

## 这个项目要解决什么问题

传统 PDF 阅读器只能选中文字或复制，不能像点读笔一样“点到哪里读哪里”。这个项目希望做到：

- **保留原始排版**：PDF 用 PDF.js 原样显示，不重新排版。
- **点击原文**：英文单词和例句都是点击热区，不需要先复制到别的软件。
- **手机也能用**：拍纸质书页面，OCR 后在照片上直接点读。
- **隐私优先**：书籍、照片、识别文本默认只在本机处理，不上传云端。
- **先能用，再变好**：先做最小可用版本，不一次性堆满功能。

## MVP 范围

第一版只做：

1. 电脑端打开普通文本 PDF，点击单词发音。
2. 点击例句播放整句。
3. 手机拍照/导入照片，OCR 后点击单词或句子发音。
4. 使用浏览器自带语音（SpeechSynthesis）发声，不依赖云端。

暂不实现：

- EPUB。
- 单词收藏、生词本、学习记录。
- 用户账号、云同步、分享。
- 扫描版 PDF 的 OCR。
- 词典释义、翻译、多语言 OCR。

## 技术栈

| 部分 | 选择 | 作用 |
| --- | --- | --- |
| 后端 | Python 3.12 + FastAPI + Uvicorn | 本地 API 服务 |
| PDF 解析 | PyMuPDF | 提取每页的单词、行、句子和坐标 |
| PDF 显示 | PDF.js (`pdfjs-dist`) | 在浏览器中保留原始排版 |
| 照片 OCR | RapidOCR + ONNX Runtime（CPU） | 返回文字和位置坐标，本地运行 |
| 前端 | Vite 8 + 原生 JavaScript | 无需先学 React/Vue，调试直观 |
| 音频（MVP） | 浏览器 SpeechSynthesis | 合法、离线可用、无需下载 |
| 数据 | 本地文件；后续用 SQLite | 书籍、照片、音频缓存和记录 |

更详细的选型理由、替代方案和规则见 [AGENTS.md](AGENTS.md)。

## 当前电脑环境检查结果

检查日期：**2026-10-20**。完整报告见 [docs/environment.md](docs/environment.md)。

| 项目 | 当前状态 | 结论 |
| --- | --- | --- |
| Python | 3.9.6 | **不满足**，需要安装 Python 3.12 |
| Node.js | 24.18.0 | 满足要求 |
| npm | 11.16.0 | 满足要求，npm 源可访问 |
| Git | 2.55.0 | 满足要求，已配置用户名/邮箱 |
| PyMuPDF | 全局已安装 1.26.5 | 项目仍会使用隔离的 `.venv`，不要依赖全局包 |
| FastAPI / Uvicorn | 未安装 | 安装 Python 3.12 后在虚拟环境中安装 |
| RapidOCR / ONNX Runtime | 未安装 | 随后端依赖一起安装 |
| Tesseract | 未安装 | **本方案不需要** |
| Docker | 未安装 | **本方案不需要** |

随时可以重新检查：

```powershell
python scripts/check_env.py
```

> 为什么必须用 Python 3.12？
> 当前最新版 FastAPI、PyMuPDF 2.x 和 ONNX Runtime 都要求 Python 3.10 或更高；Python 3.9 已经停止维护。RapidOCR 官方文档以 Python 3.12 验证最充分，所以选择 3.12，而不是更激进的 3.13。

## 快速开始（Windows / PowerShell）

### 0. 准备工具

需要：

- Windows 10 或 Windows 11。
- Python **3.12.x**。
- Node.js **22.13 或更高**（本机已是 24.18.0，满足）。
- Git（本机已有）。

### 1. 安装 Python 3.12

如果 `py -0p` 里还没有 3.12，任选一种方式：

**方式 A：winget（推荐，命令简单）**

```powershell
winget install -e --id Python.Python.3.12
```

**方式 B：官网安装包**

1. 打开 <https://www.python.org/downloads/windows/>。
2. 下载 Python 3.12 的 Windows installer (64-bit)。
3. 安装时勾选 **Add python.exe to PATH**。
4. 安装完成后关闭并重新打开终端。

验证：

```powershell
py -0p
py -3.12 --version
```

应看到 Python 3.12.x。

### 2. 安装后端依赖

在项目根目录（`D:\app_github\vocabulary_audio`）执行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

如果 PowerShell 提示“禁止运行脚本”，只需对当前用户放行一次：

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

然后重新执行激活命令。

> 使用 Git Bash 时，激活命令是：
> `source .venv/Scripts/activate`

验证依赖：

```powershell
python -c "import fastapi, pymupdf, rapidocr, onnxruntime; print('backend deps OK')"
```

### 3. 启动后端

在**已激活虚拟环境**的项目根目录执行：

```powershell
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

打开 <http://127.0.0.1:8000/api/health>，应看到类似：

```json
{ "status": "ok", "service": "vocabulary-audio", "version": "0.1.0" }
```

FastAPI 自动生成的接口文档：<http://127.0.0.1:8000/docs>。

### 4. 安装并启动前端

**另开一个终端**：

```powershell
cd frontend
npm install
npm run dev
```

打开 <http://127.0.0.1:5173>，应该能看到阶段 0 的占位页。

前端开发服务器会把 `/api` 请求代理到 `http://127.0.0.1:8000`，所以不需要手动配置跨域地址。

### 5. 构建前端（可选，用于检查生产构建是否正常）

```powershell
cd frontend
npm run build
```

产物在 `frontend/dist/`，已被 `.gitignore` 忽略。

### 6. 手机访问（后续功能实现后使用）

手机和电脑连接**同一个 Wi-Fi**：

1. Vite 已配置 `host: true`，启动时会显示 `Network:` 地址。
2. 在手机浏览器打开 `http://<电脑局域网IP>:5173`。
3. 手机上的 `/api` 请求会由 Vite 代理到电脑本机的 8000 端口。
4. Windows 防火墙首次询问时，只允许**专用网络**。

注意：

- 当前没有登录和权限控制，**只能在可信局域网使用**。
- 不要做路由器端口转发，不要把服务暴露到公网。
- 如果手机打不开，先检查两台设备是否在同一 Wi-Fi、防火墙是否放行 Node.js、电脑 IP 是否变化。

## 目录说明

```text
vocabulary_audio/
├── AGENTS.md              # 项目目标、技术选型、开发规则、验收标准
├── README.md              # 当前文件
├── requirements.txt       # 后端运行依赖
├── requirements-dev.txt   # 测试和代码检查依赖
├── pyproject.toml         # pytest / ruff 配置
├── backend/
│   ├── app/
│   │   ├── main.py        # FastAPI 入口（当前只有 /api/health）
│   │   ├── api/           # 路由（后续：books、photos、audio）
│   │   ├── services/      # PDF、OCR、音频逻辑（后续）
│   │   └── models/        # 请求/响应数据结构（后续）
│   └── tests/             # 后端测试
├── frontend/
│   ├── index.html         # 页面入口
│   ├── package.json       # 前端依赖和命令
│   ├── vite.config.js     # 开发服务器 + /api 代理
│   └── src/               # 前端源码（当前为占位页）
├── data/                  # 私人数据，全部被 Git 忽略
│   ├── books/             # 用户 PDF
│   ├── photos/            # 用户照片
│   └── audio_cache/       # 后续的合法音频缓存
├── docs/
│   └── environment.md     # 环境检查报告
└── scripts/
    └── check_env.py       # 环境检查脚本
```

## 隐私与数据

- 默认只监听 `127.0.0.1`，书籍和照片不上传云端。
- `data/` 下的 PDF、照片、音频缓存和数据库都被 `.gitignore` 忽略。
- `.env`、密钥、证书不会提交。
- 日志只记录 ID 和错误信息，不记录书籍内容或识别文本。
- 请只处理你有权使用的书籍和照片；不要把他人的受版权保护内容提交到仓库。

## 关于发音

MVP 使用浏览器内置的 SpeechSynthesis：

- 优点：合法、零成本、无网络请求、无需准备音频文件。
- 局限：不同系统的英文音色不同；部分环境可能没有英文语音；语速和自然度不如真人录音。

后续接入真人音频时，会：

- 只使用许可证明确的来源（例如 Wikimedia Commons / Wiktionary 的音频）。
- 缓存已获取的音频，并保存来源、许可证、署名和获取时间。
- 找不到合适音频时回退到浏览器 TTS。
- 不使用未授权的抓取接口或非官方 TTS 服务。

## 常见问题

**`py -3.12` 找不到？**
说明 Python 3.12 还没安装，或安装时没有注册 launcher。重新安装并勾选 PATH，或使用 Python 3.12 安装目录下的 `python.exe` 创建虚拟环境。

**`Activate.ps1` 无法运行？**
执行 `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`，然后重新激活。

**`npm install` 很慢？**
先确认网络正常。必要时可以临时换源（不要把换源配置写进项目文件）：

```powershell
npm install --registry=https://registry.npmmirror.com
```

**端口被占用？**
后端换 `--port 8001`，同时修改 `frontend/vite.config.js` 里的代理目标；前端换 `npm run dev -- --port 5174`。

**需要安装 Tesseract 吗？**
不需要。照片 OCR 使用 RapidOCR，安装 Python 包即可，模型随包提供。

**为什么不用 React？**
MVP 是单页阅读界面，原生 JavaScript + Vite 足够；少一层框架概念，坐标问题和事件问题更容易调试。以后功能复杂了再评估。

**为什么 PDF 不用 PDF.js 自己提取文字？**
PDF.js 负责“原样显示”；PyMuPDF 负责稳定地提取单词、行、句子和坐标。分工清晰，坐标也更容易测试。

**PyMuPDF 的许可证是什么？**
PyMuPDF 采用 AGPL-3.0 或商业许可。个人本地使用通常没有问题；如果将来要分发或公开托管，请先复核许可证要求。

## 开发命令

```powershell
# 后端测试
python -m pytest

# Python 代码检查
ruff check backend

# 前端开发
cd frontend
npm run dev

# 前端生产构建
npm run build

# 环境检查
python scripts/check_env.py
```

## 路线图

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| Phase 0 | 环境、规则、目录、README、健康检查 | 已完成 |
| Phase 1 | PDF 上传 + 文本/坐标提取 + PDF.js 渲染 + 单词点击发音 | 待开始 |
| Phase 2 | 例句切分、整句播放、翻页与缩放 | 待开始 |
| Phase 3 | 手机拍照/选图 + OCR + 照片点击层 | 待开始 |
| Phase 4 | 合法音频来源与缓存 | 后续 |
| Phase 5 | EPUB、收藏、学习记录 | 后续 |

## 相关文档

- [AGENTS.md](AGENTS.md)：完整的技术规则、坐标契约、隐私规则和验收标准。
- [docs/environment.md](docs/environment.md)：本次环境检查的详细结果和待办。

## 许可证

项目代码的许可证尚未确定。第三方依赖遵循各自许可证；仓库不包含任何书籍、照片或受版权保护的音频。
