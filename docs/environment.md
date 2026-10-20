# 环境检查报告

- 检查日期：2026-10-20
- 工作目录：`D:\app_github\vocabulary_audio`
- 系统：Windows（版本 10.0.26200，x64）
- 用途：确认当前电脑是否可以支撑 Vocabulary Audio 的第一阶段开发

## 结论

| 结论 | 内容 |
| --- | --- |
| 可以立即使用 | Node.js 24.18.0、npm 11.16.0、Git 2.55.0、npm 软件源 |
| 必须先升级 | Python 当前为 3.9.6，项目要求 **Python 3.12.x** |
| 已安装但项目不用 | 全局 PyMuPDF 1.26.5、Pillow 11.3.0；项目会使用独立 `.venv` |
| 尚未安装 | FastAPI、Uvicorn、RapidOCR、ONNX Runtime、python-multipart |
| 不需要安装 | Tesseract OCR（改用 RapidOCR）、Docker |
| 已验证 | 前端依赖安装成功，`npm run build` 构建成功，Vite 开发服务器返回 HTTP 200 |
| 尚未验证 | 后端实际启动和接口测试（被 Python 版本阻塞） |

**一句话总结：** 前端工具链已经就绪；安装 Python 3.12 并创建虚拟环境后，后端即可开始开发。

## 1. 工作区初始状态

- 检查开始时，工作区**没有任何文件**（只有 `.` 和 `..`）。
- 因此没有删除、覆盖或迁移任何已有文件。
- 本阶段新建了项目规则、目录、依赖清单、最小后端和前端占位页。

## 2. 系统与开发工具

| 工具 | 检查命令 | 结果 | 判断 |
| --- | --- | --- | --- |
| Python | `python --version` | 3.9.6 | 不满足（需要 3.12） |
| Python Launcher | `py -0p` | 3.9、3.7 | 有 launcher，但缺 3.12 |
| pip | `python -m pip --version` | 21.1.3 | 版本较旧；在新建 venv 内升级即可 |
| Node.js | `node --version` | v24.18.0 | 满足 |
| npm | `npm --version` | 11.16.0 | 满足 |
| Git | `git --version` | 2.55.0.windows.2 | 满足 |
| Git 身份 | `git config --global user.name/email` | 已配置 | 可用于提交（本阶段未提交） |
| winget | `winget --version` | 1.29.380 | 可用于安装 Python 3.12 |
| Docker | `docker --version` | 未安装 | 不需要 |
| Tesseract | `tesseract --version` | 未安装 | 不需要 |

Windows 命令行环境为 Git Bash；README 和 AGENTS 中的主要示例使用 PowerShell，二者都可以使用。

## 3. Python 环境

- 当前解释器：`C:\Users\12168\AppData\Local\Programs\Python\Python39\python.exe`
- 版本：Python 3.9.6
- `venv` 模块可用。
- `sqlite3` 可用，SQLite 版本 3.35.5（后续保存收藏/记录时使用）。
- 全局环境中已有的相关包：
  - PyMuPDF 1.26.5
  - Pillow 11.3.0
  - numpy 1.26.4
  - torch 2.8.0（本项目不使用）
- 全局环境缺少：
  - FastAPI
  - Uvicorn
  - RapidOCR
  - ONNX Runtime
  - python-multipart

### 为什么不能直接用 Python 3.9

- Python 3.9 已于 2025 年停止维护。
- 当前最新 FastAPI 要求 Python >= 3.10。
- 最新 ONNX Runtime 要求 Python >= 3.11。
- PyMuPDF 2.x 要求 Python >= 3.11。
- 若强行使用 3.9，需要锁定一组旧版本依赖，后续升级和排错成本更高，不适合初学者。

### 为什么选择 3.12，而不是 3.13

- RapidOCR 官方文档和示例主要基于 Python 3.12 验证。
- ONNX Runtime 1.31.0 提供 cp311、cp312、cp313、cp314 的 wheel，3.12 可用。
- Python 3.12 同时满足 FastAPI、PyMuPDF、ONNX Runtime 的要求，是兼容性最稳的折中。

### 待执行

```powershell
# 任选一种方式安装 Python 3.12
winget install -e --id Python.Python.3.12
# 或从 https://www.python.org/downloads/windows/ 下载安装包

# 在项目根目录创建虚拟环境
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

安装完成后用以下命令确认：

```powershell
python --version
python scripts/check_env.py
```

## 4. Node.js / npm / 前端

| 检查项 | 结果 |
| --- | --- |
| Node.js | v24.18.0，满足 Node >= 22.13 |
| npm | 11.16.0，满足 npm >= 10 |
| npm registry | 可访问（已成功下载依赖） |
| `pdfjs-dist` | 6.4.299 已安装 |
| `vite` | 8.3.4 已安装 |
| `npm install` | 成功，新增 18 个包，约 26 秒 |
| `npm run dev` | 启动成功（ready in 185ms），访问 `http://127.0.0.1:5173/` 返回 HTTP 200 |
| `npm run build` | 成功，54ms 完成构建 |

构建产物：

```text
dist/index.html                 1.55 kB
dist/assets/index-*.css         1.87 kB
dist/assets/index-*.js          0.72 kB
```

`frontend/dist/` 和 `frontend/node_modules/` 都已被 `.gitignore` 忽略。

### 版本约束说明

- `pdfjs-dist` 6.x 要求 Node >= 22.13；本机 Node 24.18 满足。
- Vite 8.x 要求 Node ^20.19 或 >= 22.12；本机满足。
- 这些 Node 版本要求主要影响构建工具；浏览器端仍使用现代浏览器的 ES modules。

## 5. 照片 OCR 方案检查

| 方案 | 状态 | 结论 |
| --- | --- | --- |
| RapidOCR + ONNX Runtime | 未安装，计划使用 | 纯 pip 安装、CPU 推理、模型随包提供、返回文字和坐标 |
| Tesseract | 未安装 | 不需要额外系统安装，作为备选方案保留 |
| PaddleOCR | 未采用 | 依赖重，Windows 安装复杂 |
| EasyOCR | 未采用 | 依赖 PyTorch，体积大、CPU 慢 |
| 云 OCR | 禁止 | 违反本地优先原则 |

选择 RapidOCR 的原因：

- 不需要单独安装系统程序，`pip install` 即可。
- 官方说明模型已打入 wheel 包，不依赖首次运行下载。
- 支持中英文，适合英文书页。
- `return_word_box=True` 时返回文字和四角坐标；英文可能按字符返回，服务层需要把字符框合并成单词框。
- 装完 Python 3.12 后，用真实书页照片做一次识别测试，确认词框精度；如果不满足，再评估 Tesseract 备选。

## 6. 依赖安装状态总表

### 已安装（可直接使用）

- Node.js 24.18.0
- npm 11.16.0
- Git 2.55.0
- 前端项目依赖：`pdfjs-dist@6.4.299`、`vite@8.3.4`
- 全局 Python 包：PyMuPDF 1.26.5、Pillow 11.3.0、numpy 1.26.4

### 尚未安装（需要执行）

- Python 3.12.x（系统级）
- 后端项目依赖（安装到 `.venv`）：
  - FastAPI 0.150.0
  - Uvicorn 0.54.0
  - PyMuPDF 1.26.5
  - RapidOCR 3.10.0
  - ONNX Runtime 1.31.0
  - Pillow 11.3.0
  - python-multipart 0.0.32
  - pytest 9.1.1、httpx 0.28.1、ruff 0.17.1（开发依赖）

### 不需要

- Tesseract OCR
- Docker
- 任何云端 OCR/TTS 账号或密钥

## 7. 已验证与未验证

已验证：

- Python 源码可以通过语法编译检查（`python -m compileall backend scripts`）。
- 环境检查脚本可运行，并正确报告缺失项。
- 前端依赖安装成功。
- Vite 开发服务器启动成功，页面返回 HTTP 200。
- 前端生产构建成功。
- `.gitignore` 覆盖 `.venv/`、`node_modules/`、`frontend/dist/`、`data/` 私人数据和环境变量。

未验证（明确留到下一阶段）：

- FastAPI 应用实际启动。
- `GET /api/health` 的真实 HTTP 响应。
- PyMuPDF 对真实 PDF 的单词坐标提取。
- RapidOCR 对真实书页照片的识别和词框精度。
- 浏览器 SpeechSynthesis 的英文语音可用性。

原因：当前 Python 3.9 无法安装项目锁定的最新依赖；这是环境问题，不是代码问题。安装 Python 3.12 后按 README 执行即可验证。

## 8. 下一步

1. 安装 Python 3.12。
2. 创建 `.venv` 并安装 `requirements-dev.txt`。
3. 启动后端，访问 <http://127.0.0.1:8000/api/health>。
4. 运行 `python -m pytest`，确认健康检查测试通过。
5. 开始 Phase 1：PDF 上传、PyMuPDF 单页单词/坐标提取、PDF.js 渲染和单词点击发音。
6. 用一个带旋转页的 PDF、一个普通文本 PDF 和几张真实书页照片建立测试素材（测试素材不要提交）。

## 9. 如何重新检查

任何阶段都可以执行：

```powershell
python scripts/check_env.py
```

脚本会检查：

- Python、Node.js、npm、Git 版本。
- 当前 Python 解释器中的后端依赖。
- 前端 `node_modules`、`package-lock.json`、PDF.js 和 Vite。
- `data/` 目录是否存在。
- Tesseract、Docker 是否安装（仅提示，不影响结论）。

退出码 `0` 表示必需检查全部通过，`1` 表示仍有缺失。当前预期退出码为 `1`，直到 Python 3.12 和后端依赖安装完成。
