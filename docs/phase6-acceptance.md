# Phase 6 验收记录：EPUB 阅读与点读

- 日期：2026-10-20
- 环境：Windows 11，Python 3.12.10，Node 24.18.0
- EPUB：EPUB.js 0.3.93（BSD-2-Clause）
- 浏览器：ZCode In-app Browser（Chromium），桌面 1280×720 / 移动 390×844
- 后端：<http://127.0.0.1:8000>
- 前端：<http://127.0.0.1:5173>

## 1. 自动化测试

```text
python -m pytest
83 passed

ruff check backend scripts
All checks passed

npm --prefix frontend test
24 passed（6 坐标 + 6 音频 UI + 12 EPUB 文本/目录）

npm --prefix frontend run build
built successfully
```

生产构建主包约 855.44 kB（gzip 256.10 kB）。EPUB.js 使包体积增加；Vite 的 >500 kB 提示是信息性警告，构建成功。

新增后端测试（`backend/tests/test_epubs_api.py`，12 个）：

- 上传/下载/元数据（标题、作者、语言、章节数、大小）正确。
- 标题缺失时使用文件名。
- 空文件、非 ZIP、缺少 mimetype、错误 mimetype、缺少 container、路径穿越、无 spine 章节、超大文件被拒绝。
- 失败上传不留下 `.part`、`.epub` 或 `.json` 残留。
- 未知/非法 EPUB ID 返回 404。

新增前端测试（`frontend/tests/epubText.test.js`，12 个）：

- 取词：普通单词、单词边界、空格/标点、撇号、连字符、弯引号。
- 句子切分：多句、缩写（Dr./Prof./U.S.）、小数、引号、无标点。
- 按偏移找句子；空白折叠。
- 目录 href 规范化、带片段/OPF 相对路径匹配。
- 嵌套 TOC 展平并保留层级。

## 2. 浏览器验收（已通过）

### 2.1 打开和章节

- 生成并上传 3 章测试 EPUB（`Phase 6 EPUB Test`，作者 `Local Test`，3 章）。
- 打开后显示原书正文，不重排为纯文本页；书名/作者/语言/章节数正确。
- 目录显示 `Chapter 1/2/3`；当前章节高亮。
- “下一章”切到 `Chapter 2`，正文和章节标签更新；“下一章”在最后一章禁用。
- 目录点击 `Chapter 3` 切换成功，目录自动关闭，当前项高亮。
- 章节切换会停止旧单词/整句音频并把底部结果栏重置为点击提示。

### 2.2 字号和重排

- 初始 100%，正文 `font-size: 16px`。
- 点击两次“+”到 120%，正文变为 `19.2px`，文字重新排版，iframe 仍在原章节。
- 在 120% 字号下点击 `brown` 仍能正确识别并播放 0.608 s 真人录音。
- “重置字号”回到 100%（16px）。
- 长章节（30 段）在阅读区可滚动，内部滚动容器 `scrollTop` 可到 500；滚动后点击正文仍能识别单词。

### 2.3 单词和整句点读

- 单词模式点击 `brown`：识别为 `brown`，播放 Wikimedia Commons 缓存真人录音 0.608 s，显示美式/来源/许可证。
- 整句模式点击 `fox` 所在句子：识别为 `The quick brown fox jumps over the lazy dog.`，播放本机 TTS 3.329 s，显示“合成语音（非真人录音）”和 Zira 说明。
- 切回单词模式点击同一位置：识别为 `fox`，单词和句子点击不会互相误触。
- 点击 EPUB 正文中的链接不会被点读拦截，仍按 EPUB 链接行为处理。

### 2.4 移动尺寸

- 390×844 下工具栏换行，EPUB 阅读区、目录和底部结果栏都在视口内，无横向/纵向溢出。
- iframe 宽度随容器从 1280 重排到 390；正文重新换行。
- 目录面板宽 330px（`min(330px, 86vw)`），在手机宽度内；选中章节后自动关闭。
- 手机宽度下单词/整句点读与桌面一致。

### 2.5 来源切换和错误恢复

- EPUB → PDF：EPUB iframe 被销毁，PDF 显示原始页面、381 个单词框、70 个句子片段。
- PDF → EPUB：PDF canvas 归零并隐藏，EPUB 重新加载第一章。
- EPUB → 照片：EPUB 销毁，照片 OCR 显示 49 个单词框/7 个句子片段，`brown` 单词点读正常。
- 照片 → 损坏 EPUB：显示“文件不是有效的 EPUB（不是 ZIP 容器）”，原照片、标题、尺寸和点击框保持可用。
- EPUB → 损坏 EPUB：显示错误，并重新加载之前的 EPUB（章节和目录恢复）。
- PDF 回归：第 1 页点击 `sentence` 播放真人录音；整句模式点击第一句播放 2.939 s 合成语音；下一页显示 20 个单词框/3 个句子片段。

## 3. 实现要点

- 后端只做 EPUB 容器安全校验和原文件服务；不解析/改写书正文，也不记录正文。
- 前端 `ePub(url, { openAs: 'epub' })` 读取 `/api/epubs/{id}/file`；文件接口没有 `.epub` 后缀，必须显式指定 `openAs`，否则 EPUB.js 会按目录请求 `META-INF/container.xml`。
- `flow: "scrolled-doc"` 保留可重排正文和章节结构；不修改原书 HTML。
- 点击通过 iframe 内 `caretRangeFromPoint`/`caretPositionFromPoint` 取文本节点，再用纯函数扩展单词和切分句子。
- iframe 在阅读区**宽度**变化时通过 `ResizeObserver` 调用 `rendition.resize(width, height)`；仅依赖 EPUB.js 的 window resize 不足以保证手机宽度重排。结果栏高度变化不会触发重排，避免点击单词后 iframe 被重建。
- 字号通过 `rendition.themes.fontSize` 设置；100% 时移除覆盖。
- 章节切换通过 `relocated` 事件更新标签/目录高亮，并重置旧音频。
- 打开 EPUB 成功后释放 PDF；切到 PDF/照片时调用 `book.destroy()` 释放 EPUB rendition。

## 4. 2026-10-20 修复记录

- 点击 EPUB 单词后，结果栏高度变化会触发整章 `rendition.resize`，清空 iframe 并丢失单词高亮；已改为只在阅读区宽度变化时重排。
- 点击单词/整句时自动关闭之前的错误横幅，避免恢复旧内容后错误提示一直残留。
- 增加“首次 location 未知时不 resize”的保护，避免极早期 resize 清空视图但没有 CFI 可恢复，留下空白 EPUB 面板。
- 浏览器复测：单词高亮在 500 ms 后仍存在；结果栏展开后 iframe 不重建；390×844 宽度变化仍能重排。

## 5. 未验证

- 真实手机相机、原生文件选择框、真实多点触控。
- iOS Safari / Android 浏览器；当前仅 Chromium。
- 受 DRM/内容加密的 EPUB（当前会拒绝）。
- 固定版式（pre-paginated）、竖排/RTL、MathML/SVG 封面、脚本化内容、脚注弹窗等复杂 EPUB。
- 接近 100 MB 的合法 EPUB 完整处理性能和内存峰值；当前验证了上限拒绝和小文件打开。
- 真实商业 EPUB 的排版差异和字体缩放行为。
- 屏幕阅读器、键盘无障碍；EPUB 内容在 iframe 内，键盘导航需要进一步检查。
- EPUB 阅读进度、收藏、生词本尚未实现。
