# 环境检查报告

- 检查日期：2026-10-20
- 工作目录：`D:\app_github\vocabulary_audio`
- 系统：Windows（版本 10.0.26200，x64）
- 当前阶段：Phase 4（PDF 点读 + 音频 + 手机照片点读）已完成

## 结论

| 项目 | 状态 |
| --- | --- |
| Python | **3.12.10 已安装**，项目 `.venv` 已创建 |
| Node.js / npm | 24.18.0 / 11.16.0，满足要求 |
| Git | 2.55.0，满足要求 |
| 后端依赖 | **已安装到 `.venv`**（含 RapidOCR / ONNX Runtime） |
| 前端依赖 | **已安装到 `frontend/node_modules`** |
| 照片 OCR | RapidOCR 3.10.0 + ONNX Runtime 1.31.0，CPU 本地推理 |
| 单词音频网络 | 系统 `curl` 可访问 Wikimedia Commons；urllib 兜底 |
| 整句 TTS | Windows SAPI 可用：Microsoft Zira / David（en-US） |
| 后端测试 | **67 passed** |
| 前端测试 | **12 passed**（6 坐标 + 6 音频 UI） |
| 前端构建 | 成功 |
| 浏览器验收 | PDF、单词/整句音频、照片 OCR、点读、缩放拖动、清空均通过（移动尺寸 390×844） |

## 1. 工作区与私人数据

- 第一次检查时工作区为空，没有删除或覆盖任何用户文件。
- `data/books/` 的测试 PDF、`data/photos/` 的测试照片、`data/audio_cache/` 的测试音频都是运行产物，已被 `.gitignore` 忽略。
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
| Docker / Tesseract | 未安装 | 不需要 |

## 3. 后端依赖

### 已安装（`.venv` 内）

- FastAPI 0.150.0
- Uvicorn 0.54.0（standard extras）
- PyMuPDF 1.26.5
- python-multipart 0.0.32
- Pillow 11.3.0
- RapidOCR 3.10.0
- ONNX Runtime 1.31.0
- pytest 9.1.1
- httpx 0.28.1（测试）
- Ruff 0.17.1

RapidOCR 的检测/方向分类/识别模型随包提供在：
`.venv/Lib/site-packages/rapidocr/models/`，不需要额外下载系统 OCR 程序。

## 4. 前端依赖

| 包 | 版本 | 状态 |
| --- | --- | --- |
| `pdfjs-dist` | 6.4.299 | 已安装 |
| `vite` | 8.3.4 | 已安装 |
| Node 内置 test runner | Node 24.18 | 可运行 |

## 5. 照片 OCR 验证

- 使用 RapidOCR `return_word_box=True`。
- 实测英文直接返回**单词级框**，不是一个整行框；代码直接使用，不从行框推算单词。
- 1200×1600 英文页面图片：
  - OCR 约 1.3 秒；
  - 49 个单词、7 行、6 个句子；
  - 图片上传 + OCR API 总耗时约 2.5 秒（首次加载模型）。
- 倾斜 7° 英文图片：17 个单词、2 个句子。
- 空白图片：0 单词，明确提示。
- 中文图片：0 英文单词，明确提示只支持英文。
- EXIF Orientation=6 的 JPEG：上传后宽高正确交换。
- 图片最大 25 MB；显示长边最多 3000px，OCR 长边最多 2000px；坐标归一化，与显示像素无关。

详见 [photo-ocr.md](photo-ocr.md)。

## 6. Phase 4 验证结果

### 自动化测试

```text
python -m pytest
67 passed

ruff check backend scripts
All checks passed

npm --prefix frontend test
12 passed

npm --prefix frontend run build
built successfully
```

### 移动尺寸浏览器

视口 390×844：

- 照片原图显示（非 OCR 重排文字），49 个单词框、7 个句子片段。
- 点击 `Vocabulary` 播放真人单词录音；来源/许可证显示。
- 整句模式点击例句播放整句 TTS（合成语音标记）。
- 156% 缩放、180% 双指缩放、拖动后点击框仍与图片对齐；156% 下点击 `brown` 结果正确。
- 空白/中文/倾斜照片均有明确处理。
- 清空照片后视图和结果栏隐藏，当前照片文件删除。
- 共享结果栏重构后，PDF 正常显示/点击/播放，结果栏不溢出。

详见 [phase4-acceptance.md](phase4-acceptance.md)。

## 7. 未验证 / 未解决

- 真实手机相机、原生文件选择框：自动化无法操作，需人工验收。
- 真实手机多点触控手感：使用移动尺寸视口和 PointerEvent 验证，未真机人工测试。
- 模糊、反光、透视、手写、多栏页面 OCR 效果有限；没有去倾斜/去模糊/版面分析。
- OCR 阅读顺序可能与多栏页面的自然顺序不同。
- 部分图片若只返回字符/行级结果，不会伪造单词框，只保留句子点击并提示。
- 缓存没有自动清理策略；清空照片只删除当前照片。
- 当前只支持英文点读。
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

照片 OCR 需要表单上传图片：

```powershell
curl -F "file=@path\to\page.jpg;type=image/jpeg" http://127.0.0.1:8000/api/photos
```

如果单词音频网络必须走系统代理：

```powershell
$env:VOCABULARY_AUDIO_USE_PROXY = "1"
```

然后重启后端。
