# 环境检查报告

- 检查日期：2026-10-20
- 工作目录：`D:\app_github\vocabulary_audio`
- 系统：Windows（版本 10.0.26200，x64）
- 当前阶段：Phase 1（PDF 原版页面点读）已完成

## 结论

| 项目 | 状态 |
| --- | --- |
| Python | **3.12.10 已安装**，项目 `.venv` 已创建 |
| Node.js / npm | 24.18.0 / 11.16.0，满足要求 |
| Git | 2.55.0，满足要求 |
| Phase 1 后端依赖 | **已安装到 `.venv`** |
| 前端依赖 | **已安装到 `frontend/node_modules`** |
| 照片 OCR 依赖 | **未安装**（Phase 3 才需要） |
| Tesseract / Docker | 不需要 |
| 后端测试 | **23 passed** |
| 前端坐标测试 | **6 passed** |
| 前端构建 | 成功 |
| 浏览器验收 | 真实 PDF、翻页、缩放、滚动、旋转页、扫描页均通过 |

**一句话总结：** Phase 1 的开发、测试和运行环境已经就绪；下一阶段实现照片 OCR 时再安装 `requirements-ocr.txt`。

## 1. 工作区初始状态

- 第一次检查时工作区为空，只有 `.` 和 `..`。
- 没有删除、覆盖或迁移任何用户文件。
- 当前 `data/books/` 中有测试 PDF，它们是运行产物，已被 `.gitignore` 忽略，不会进入 Git。

## 2. 系统与开发工具

| 工具 | 结果 | 判断 |
| --- | --- | --- |
| Python | 3.12.10 | 满足 |
| Python Launcher | 3.12 + 3.9 + 3.7 | 项目使用 3.12 |
| pip（venv 内） | 26.2.1 | 满足 |
| Node.js | v24.18.0 | 满足 PDF.js 6 / Vite 8 |
| npm | 11.16.0 | 满足 |
| Git | 2.55.0.windows.2 | 满足 |
| winget | 1.29.380 | 用于安装 Python 3.12 |
| Docker | 未安装 | 不需要 |
| Tesseract | 未安装 | 不需要 |

### Python 3.12 的安装

最初的默认 Python 是 3.9.6，已停止维护，且最新 FastAPI / ONNX Runtime / PyMuPDF 版本要求更高版本。已通过 winget 安装 3.12.10：

```powershell
winget install -e --id Python.Python.3.12
py -3.12 -m venv .venv
```

`.venv` 的解释器：

```text
D:\app_github\vocabulary_audio\.venv\Scripts\python.exe
```

## 3. 后端依赖

### 已安装（`.venv` 内）

- FastAPI 0.150.0
- Uvicorn 0.54.0（含 standard extras）
- PyMuPDF 1.26.5
- python-multipart 0.0.32
- Pillow 11.3.0（测试生成扫描页图片）
- pytest 9.1.1
- httpx 0.28.1
- Ruff 0.17.1

### 尚未安装

- RapidOCR 3.10.0
- ONNX Runtime 1.31.0

它们属于 Phase 3 照片 OCR，不影响 PDF 点读。需要时执行：

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements-ocr.txt
```

### 安装说明

- 直连 PyPI 下载较慢，本次使用清华镜像完成了 Phase 1 依赖安装；`requirements*.txt` 中的版本没有改变。
- 早期尝试时 PyPI 大包下载卡住，已停止该进程；没有残留安装错误。
- 项目不使用全局 Python 包，所有后端依赖都在 `.venv` 中。

## 4. 前端依赖

| 包 | 版本 | 状态 |
| --- | --- | --- |
| `pdfjs-dist` | 6.4.299 | 已安装 |
| `vite` | 8.3.4 | 已安装 |
| Node 内置 test runner | Node 24.18 | 可运行 |

验证结果：

- `npm install` 成功。
- `npm test`：6 个坐标测试全部通过。
- `npm run build`：成功，包含 PDF.js worker 资源。
- `npm run dev`：在 <http://127.0.0.1:5173> 启动成功。

## 5. Phase 1 验证结果

### 自动化测试

```text
python -m pytest
23 passed

ruff check backend scripts
All checks passed

npm --prefix frontend test
6 passed

npm --prefix frontend run build
built successfully
```

### 浏览器端到端验证

使用生成的 4 页测试 PDF（正常文字页、扫描页、90° 旋转页）和真实的 15 页 arXiv 论文：

- 原版页面由 PDF.js 渲染，排版保留。
- 点击单词 `sentence`、`Navigation`、`attribution`、`Rotated`，结果文本均正确。
- 点击句子内空白处，结果显示完整例句。
- 翻页、页码输入（Enter）、放大（205% → 245%）、滚动 700px 后，点击框相对 canvas 的位置与后端归一化 bbox 一致。
- 90° 旋转页保持横向显示，点击框位于右上角正确位置。
- 扫描页返回“可能是扫描版 PDF，当前版本暂不支持 OCR”，且单词框数量为 0。
- 损坏 PDF 返回错误提示，旧页面保持可用。
- 真实 PDF：15 页、第 1 页 381 个可点击英文单词。

详细记录见 [phase1-acceptance.md](phase1-acceptance.md)。

## 6. 未验证 / 未解决

- 真人音频：当前只有本地模拟提示音，不能验证真实发音。
- 手机照片 OCR：依赖未安装，功能未实现。
- 原生文件选择对话框：浏览器自动化无法操作系统对话框；已通过文件输入的 `change` 事件和拖放路径验证同一处理逻辑，仍需人工点击一次确认。
- 复杂书籍版式：多栏论文第 1 页已验证，复杂表格、脚注、跨栏句子的句子切分仍需更多真实书籍样本。
- 扫描版 PDF：只提示，不 OCR。
- PyMuPDF 许可证：AGPL-3.0 或商业许可，分发前需复核。

## 7. 如何重新检查

```powershell
.\.venv\Scripts\Activate.ps1
python scripts\check_env.py
```

脚本会检查 Python、Node、npm、Git、必需后端包、可选 OCR 包和前端依赖。退出码 `0` 表示必需检查全部通过。

如果只想验证服务是否在运行：

```powershell
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:5173/
```
