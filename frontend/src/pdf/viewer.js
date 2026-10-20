import * as pdfjsLib from 'pdfjs-dist';
import pdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

import { bookFileUrl, fetchPage } from '../api/client.js';
import { clampScale, toPercentBox } from './coordinates.js';

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

const SCALE_STEP = 1.2;
const MIN_FIT_SCALE = 0.4;
const MAX_FIT_SCALE = 2.2;

export class PdfViewer {
  constructor(elements, callbacks = {}) {
    this.canvas = elements.canvas;
    this.stage = elements.stage;
    this.scroll = elements.scroll;
    this.wordLayer = elements.wordLayer;
    this.sentenceLayer = elements.sentenceLayer;
    this.loading = elements.loading;
    this.callbacks = callbacks;

    this.book = null;
    this.pdfDocument = null;
    this.loadingTask = null;
    this.renderTask = null;
    this.pageDataCache = new Map();
    this.currentPage = 0;
    this.pageCount = 0;
    this.currentPageData = null;
    this.scale = 1;
    this.autoFit = true;
    this.renderToken = 0;
    this.destroyed = false;
    this.isShowing = false;
    this.pendingResize = false;
    this.setClickMode('word');
  }

  setClickMode(mode) {
    const sentenceMode = mode === 'sentence';
    this.stage.classList.toggle('mode-sentence', sentenceMode);
    this.stage.classList.toggle('mode-word', !sentenceMode);
  }

  get hasDocument() {
    return Boolean(this.pdfDocument);
  }

  async load(book) {
    await this.destroy();
    this.book = book;
    this.pageDataCache.clear();
    this.autoFit = true;
    this.scale = 1;
    this.destroyed = false;
    this.callbacks.onLoadingChange?.(true);

    try {
      const loadingTask = pdfjsLib.getDocument({
        url: bookFileUrl(book.book_id),
      });
      this.loadingTask = loadingTask;
      const doc = await loadingTask.promise;

      if (this.destroyed) {
        await doc.destroy();
        return;
      }

      this.pdfDocument = doc;
      this.pageCount = doc.numPages;
      if (book.page_count && book.page_count !== doc.numPages) {
        console.warn(
          `Backend reports ${book.page_count} pages, PDF.js reports ${doc.numPages}.`,
        );
      }

      await this.showPage(1, { resetScroll: true });
    } catch (error) {
      this.callbacks.onLoadingChange?.(false);
      throw toFriendlyError(error);
    }
  }

  async destroy() {
    this.destroyed = true;
    this.renderToken += 1;

    try {
      this.renderTask?.cancel();
    } catch {
      // A cancelled render is expected when switching pages or documents.
    }
    this.renderTask = null;

    const loadingTask = this.loadingTask;
    this.loadingTask = null;
    this.pdfDocument = null;

    if (loadingTask) {
      try {
        await loadingTask.destroy();
      } catch (error) {
        console.warn('PDF cleanup failed:', error);
      }
    }

    this.pageDataCache.clear();
    this.currentPage = 0;
    this.currentPageData = null;
    this.pageCount = 0;
    this.isShowing = false;
    this.pendingResize = false;
    this.clearLayers();
    this.resetStage();
  }

  async goToPage(pageNumber) {
    if (!this.pdfDocument) {
      return;
    }
    const target = Math.min(
      Math.max(1, Math.round(Number(pageNumber) || 1)),
      this.pageCount,
    );
    if (target === this.currentPage && this.currentPageData) {
      return;
    }
    await this.showPage(target, { resetScroll: true });
  }

  async showPage(pageNumber, { resetScroll = true } = {}) {
    if (!this.pdfDocument) {
      return;
    }

    const target = Math.min(
      Math.max(1, Math.round(Number(pageNumber) || 1)),
      this.pageCount,
    );
    const token = ++this.renderToken;
    this.currentPage = target;
    this.isShowing = true;
    this.loading.textContent = `正在加载第 ${target} 页…`;
    this.loading.hidden = false;
    this.callbacks.onPageLoading?.(target, this.pageCount);
    this.callbacks.onLoadingChange?.(true);

    try {
      const [page, pageData] = await Promise.all([
        this.pdfDocument.getPage(target),
        this.fetchPageData(target),
      ]);
      if (token !== this.renderToken) {
        return;
      }

      const baseViewport = page.getViewport({ scale: 1 });
      if (this.autoFit) {
        this.scale = this.fitScale(baseViewport.width);
      }
      this.scale = clampScale(this.scale);
      const viewport = page.getViewport({ scale: this.scale });

      this.currentPageData = pageData;
      this.setStageSize(viewport.width, viewport.height);
      this.loading.textContent = '正在渲染页面…';

      await this.renderCanvas(page, viewport);
      if (token !== this.renderToken) {
        return;
      }

      this.renderHitLayers(pageData);
      if (resetScroll) {
        this.scroll.scrollTop = 0;
        this.scroll.scrollLeft = 0;
      }
      this.loading.hidden = true;
      this.callbacks.onPageReady?.({
        page: target,
        pageCount: this.pageCount,
        scale: this.scale,
        pageData,
      });
    } catch (error) {
      if (token !== this.renderToken) {
        return;
      }
      console.error('PDF page failed to render:', error);
      this.loading.hidden = true;
      this.clearLayers();
      this.resetStage();
      this.callbacks.onPageError?.(toFriendlyError(error).message);
    } finally {
      if (token === this.renderToken) {
        this.isShowing = false;
        this.callbacks.onLoadingChange?.(false);
        if (this.pendingResize && this.autoFit && this.currentPage) {
          this.pendingResize = false;
          queueMicrotask(() => {
            void this.showPage(this.currentPage, { resetScroll: false });
          });
        }
      }
    }
  }

  async zoomIn() {
    if (!this.pdfDocument) {
      return;
    }
    this.autoFit = false;
    this.scale = clampScale(this.scale * SCALE_STEP);
    await this.showPage(this.currentPage, { resetScroll: false });
  }

  async zoomOut() {
    if (!this.pdfDocument) {
      return;
    }
    this.autoFit = false;
    this.scale = clampScale(this.scale / SCALE_STEP);
    await this.showPage(this.currentPage, { resetScroll: false });
  }

  async fitToWidth() {
    if (!this.pdfDocument) {
      return;
    }
    this.autoFit = true;
    await this.showPage(this.currentPage, { resetScroll: false });
  }

  async handleResize() {
    if (!this.autoFit || !this.pdfDocument || !this.currentPage) {
      return;
    }
    if (this.isShowing) {
      this.pendingResize = true;
      return;
    }
    await this.showPage(this.currentPage, { resetScroll: false });
  }

  fetchPageData(pageNumber) {
    if (!this.pageDataCache.has(pageNumber)) {
      const promise = fetchPage(this.book.book_id, pageNumber);
      this.pageDataCache.set(pageNumber, promise);
      promise.catch(() => this.pageDataCache.delete(pageNumber));
    }
    return this.pageDataCache.get(pageNumber);
  }

  fitScale(baseWidth) {
    const available = Math.max(this.scroll.clientWidth - 48, 320);
    return Math.min(
      MAX_FIT_SCALE,
      Math.max(MIN_FIT_SCALE, available / baseWidth),
    );
  }

  setStageSize(width, height) {
    this.stage.classList.remove('is-empty');
    this.stage.style.width = `${width}px`;
    this.stage.style.height = `${height}px`;
  }

  resetStage() {
    this.stage.classList.add('is-empty');
    this.stage.style.width = '';
    this.stage.style.height = '';
    this.canvas.width = 0;
    this.canvas.height = 0;
    this.canvas.style.width = '0px';
    this.canvas.style.height = '0px';
  }

  async renderCanvas(page, viewport) {
    try {
      this.renderTask?.cancel();
    } catch {
      // Ignore a render task that already finished.
    }

    const outputScale = Math.min(window.devicePixelRatio || 1, 2);
    const canvas = this.canvas;
    canvas.width = Math.floor(viewport.width * outputScale);
    canvas.height = Math.floor(viewport.height * outputScale);
    canvas.style.width = `${viewport.width}px`;
    canvas.style.height = `${viewport.height}px`;

    const context = canvas.getContext('2d', { alpha: false });
    context.setTransform(1, 0, 0, 1, 0, 0);
    context.fillStyle = '#ffffff';
    context.fillRect(0, 0, canvas.width, canvas.height);

    const task = page.render({
      canvas,
      viewport,
      background: '#ffffff',
      transform:
        outputScale === 1
          ? undefined
          : [outputScale, 0, 0, outputScale, 0, 0],
    });
    this.renderTask = task;

    let timedOut = false;
    let watchdog = 0;
    try {
      await Promise.race([
        task.promise,
        new Promise((_, reject) => {
          watchdog = window.setTimeout(() => {
            timedOut = true;
            try {
              task.cancel();
            } catch {
              // Ignore a task that finished while the watchdog fired.
            }
            reject(new Error('页面渲染超时，请重试。'));
          }, 15000);
        }),
      ]);
    } catch (error) {
      if (timedOut && error?.name === 'RenderingCancelledException') {
        throw new Error('页面渲染超时，请重试。');
      }
      throw error;
    } finally {
      window.clearTimeout(watchdog);
      if (this.renderTask === task) {
        this.renderTask = null;
      }
    }
  }

  renderHitLayers(pageData) {
    this.clearLayers();

    const sentenceFragment = document.createDocumentFragment();
    for (const sentence of pageData.sentences ?? []) {
      const segments =
        Array.isArray(sentence.segments) && sentence.segments.length > 0
          ? sentence.segments
          : [{ bbox: sentence.bbox, line_id: '' }];

      for (const segment of segments) {
        const element = document.createElement('button');
        element.type = 'button';
        element.className = 'sentence-hit';
        element.dataset.sentenceId = sentence.id;
        element.dataset.sentenceText = sentence.text;
        element.dataset.segmentLineId = segment.line_id || '';
        element.dataset.bbox = JSON.stringify(segment.bbox);
        element.setAttribute(
          'aria-label',
          `播放整句合成语音：${sentence.text}`,
        );
        element.title =
          `点击播放整句（本机合成语音，非真人录音）：${sentence.text}`;

        if (!applyBox(element, segment.bbox)) {
          continue;
        }
        element.addEventListener('click', (event) => {
          event.stopPropagation();
          this.callbacks.onSentenceClick?.(sentence, element);
        });
        sentenceFragment.append(element);
      }
    }
    this.sentenceLayer.append(sentenceFragment);

    const wordFragment = document.createDocumentFragment();
    for (const word of pageData.words ?? []) {
      const element = document.createElement('button');
      element.type = 'button';
      element.className = 'word-hit';
      element.dataset.wordId = word.id;
      element.dataset.word = word.text;
      element.dataset.lineId = word.line_id;
      element.dataset.sentenceId = word.sentence_id ?? '';
      element.dataset.bbox = JSON.stringify(word.bbox);
      element.setAttribute('aria-label', `播放单词：${word.text}`);
      element.title = `${word.text}（点击播放真人发音）`;

      if (!applyBox(element, word.bbox)) {
        continue;
      }
      element.addEventListener('click', (event) => {
        event.stopPropagation();
        this.callbacks.onWordClick?.(word, element);
      });
      wordFragment.append(element);
    }
    this.wordLayer.append(wordFragment);
  }

  clearLayers() {
    this.wordLayer.replaceChildren();
    this.sentenceLayer.replaceChildren();
  }
}

function applyBox(element, bbox) {
  try {
    const box = toPercentBox(bbox);
    element.style.left = box.left;
    element.style.top = box.top;
    element.style.width = box.width;
    element.style.height = box.height;
    return true;
  } catch (error) {
    console.warn('Skipped an invalid text box:', bbox, error);
    return false;
  }
}

function toFriendlyError(error) {
  if (!error) {
    return new Error('发生未知错误。');
  }
  switch (error.name) {
    case 'InvalidPDFException':
      return new Error('PDF.js 无法解析这个 PDF，文件可能已损坏。');
    case 'MissingPDFException':
      return new Error('找不到 PDF 文件，请重新上传。');
    case 'PasswordException':
      return new Error('PDF 已加密，当前版本暂不支持需要密码的文件。');
    case 'UnexpectedResponseException':
      return new Error('读取 PDF 失败，请确认本地后端已启动。');
    case 'RenderingCancelledException':
      return new Error('页面渲染已取消。');
    default:
      return new Error(error.message || 'PDF 加载失败。');
  }
}
