import './styles/main.css';

import { uploadPdf } from './api/client.js';
import { playSimulatedTone } from './audio/simulatedAudio.js';
import { PdfViewer } from './pdf/viewer.js';

function byId(id) {
  const element = document.getElementById(id);
  if (!element) {
    throw new Error(`Missing element #${id}`);
  }
  return element;
}

const dom = {
  openFileButton: byId('open-file-button'),
  chooseFileButton: byId('choose-file-button'),
  fileInput: byId('file-input'),
  emptyState: byId('empty-state'),
  dropZone: byId('drop-zone'),
  viewer: byId('viewer'),
  bookName: byId('book-name'),
  bookPages: byId('book-pages'),
  prevPage: byId('prev-page'),
  nextPage: byId('next-page'),
  pageInput: byId('page-input'),
  pageCount: byId('page-count'),
  zoomOut: byId('zoom-out'),
  zoomIn: byId('zoom-in'),
  zoomLabel: byId('zoom-label'),
  fitWidth: byId('fit-width'),
  messageBar: byId('message-bar'),
  pageScroll: byId('page-scroll'),
  pageStage: byId('page-stage'),
  canvas: byId('pdf-canvas'),
  sentenceLayer: byId('sentence-layer'),
  wordLayer: byId('word-layer'),
  pageLoading: byId('page-loading'),
  resultPanel: byId('result-panel'),
  recognizedText: byId('recognized-text'),
  recognizedMeta: byId('recognized-meta'),
  playText: byId('play-text'),
  errorBanner: byId('error-banner'),
  errorText: byId('error-text'),
  errorClose: byId('error-close'),
};

let activeBook = null;
let fileBusy = false;
let feedbackTimer = 0;
let resizeTimer = 0;
let activeHitElement = null;
let renderedPage = 0;

const viewer = new PdfViewer(
  {
    canvas: dom.canvas,
    stage: dom.pageStage,
    scroll: dom.pageScroll,
    wordLayer: dom.wordLayer,
    sentenceLayer: dom.sentenceLayer,
    loading: dom.pageLoading,
  },
  {
    onWordClick: (word, element) => {
      showRecognition(word.text, '单词', element);
    },
    onSentenceClick: (sentence, element) => {
      showRecognition(sentence.text, '例句', element);
    },
    onPageLoading: (page, pageCount) => {
      updatePageControls(page, pageCount);
      hideMessage();
    },
    onPageReady: ({ page, pageCount, scale, pageData }) => {
      updatePageControls(page, pageCount);
      updateZoomLabel(scale);
      if (page !== renderedPage) {
        renderedPage = page;
        resetResult();
      }
      if (pageData.message) {
        showMessage(pageData.message);
      } else {
        hideMessage();
      }
    },
    onPageError: (message) => {
      showError(message);
    },
    onLoadingChange: (isLoading) => {
      dom.viewer.classList.toggle('is-loading', isLoading);
    },
  },
);

function requestFilePicker() {
  if (!fileBusy) {
    dom.fileInput.click();
  }
}

function setFileBusy(busy) {
  fileBusy = busy;
  dom.fileInput.disabled = busy;
  dom.openFileButton.disabled = busy;
  dom.chooseFileButton.disabled = busy;
  dom.openFileButton.textContent = busy ? '正在打开…' : '打开 PDF';
}

async function handleFile(file) {
  if (!file || fileBusy) {
    return;
  }

  const name = (file.name || '').toLowerCase();
  if (!name.endsWith('.pdf') && file.type !== 'application/pdf') {
    showError('请选择 PDF 文件。');
    return;
  }
  if (file.size === 0) {
    showError('这个文件是空的，请换一个 PDF。');
    return;
  }

  setFileBusy(true);
  hideError();

  try {
    const book = await uploadPdf(file);
    activeBook = book;
    dom.emptyState.hidden = true;
    dom.viewer.hidden = false;
    dom.bookName.textContent = book.filename;
    dom.bookPages.textContent = `${book.page_count} 页`;
    renderedPage = 0;
    resetResult('正在加载页面…');
    await viewer.load(book);
  } catch (error) {
    showError(requestErrorMessage(error));
    if (!viewer.hasDocument) {
      activeBook = null;
      dom.viewer.hidden = true;
      dom.emptyState.hidden = false;
    }
  } finally {
    setFileBusy(false);
    dom.fileInput.value = '';
  }
}

function requestErrorMessage(error) {
  if (error instanceof TypeError && /fetch|network/i.test(error.message)) {
    return '无法连接本地后端，请确认 uvicorn 已在 127.0.0.1:8000 启动。';
  }
  return error?.message || '发生未知错误。';
}

function showRecognition(text, type, element) {
  if (activeHitElement) {
    activeHitElement.classList.remove('is-active');
  }
  activeHitElement = element;
  element?.classList.add('is-active');

  dom.recognizedText.textContent = text;
  dom.recognizedMeta.textContent = type;
  dom.resultPanel.dataset.recognized = text;
  dom.resultPanel.dataset.type = type;

  dom.resultPanel.classList.remove('is-playing');
  void dom.resultPanel.offsetWidth;
  dom.resultPanel.classList.add('is-playing');
  dom.playText.textContent = '模拟播放中…';

  window.clearTimeout(feedbackTimer);
  feedbackTimer = window.setTimeout(() => {
    dom.resultPanel.classList.remove('is-playing');
    dom.playText.textContent = '模拟播放完成';
    activeHitElement?.classList.remove('is-active');
    activeHitElement = null;
  }, 1200);

  playSimulatedTone(type === '例句' ? 'sentence' : 'word');
}

function resetResult(text = '点击页面上的英文单词') {
  window.clearTimeout(feedbackTimer);
  if (activeHitElement) {
    activeHitElement.classList.remove('is-active');
    activeHitElement = null;
  }
  dom.recognizedText.textContent = text;
  dom.recognizedMeta.textContent = '点击单词读单词；点击句子内的空白处读整句';
  dom.playText.textContent = '模拟播放';
  dom.resultPanel.classList.remove('is-playing');
  delete dom.resultPanel.dataset.recognized;
  delete dom.resultPanel.dataset.type;
}

function updatePageControls(page, pageCount) {
  dom.pageInput.value = String(page);
  dom.pageInput.max = String(pageCount);
  dom.pageCount.textContent = String(pageCount);
  dom.bookPages.textContent = `${pageCount} 页`;
  dom.prevPage.disabled = page <= 1;
  dom.nextPage.disabled = page >= pageCount;
}

function updateZoomLabel(scale) {
  const percent = Math.round(scale * 100);
  dom.zoomLabel.textContent = `${percent}%`;
  dom.zoomOut.disabled = scale <= 0.401;
  dom.zoomIn.disabled = scale >= 2.999;
}

function showMessage(message) {
  dom.messageBar.textContent = message;
  dom.messageBar.hidden = false;
  dom.messageBar.classList.toggle('is-warning', message.includes('扫描'));
}

function hideMessage() {
  dom.messageBar.hidden = true;
  dom.messageBar.textContent = '';
  dom.messageBar.classList.remove('is-warning');
}

function showError(message) {
  dom.errorText.textContent = message;
  dom.errorBanner.hidden = false;
  console.error(message);
}

function hideError() {
  dom.errorBanner.hidden = true;
  dom.errorText.textContent = '';
}

dom.openFileButton.addEventListener('click', requestFilePicker);
dom.chooseFileButton.addEventListener('click', requestFilePicker);
dom.fileInput.addEventListener('change', () => {
  const file = dom.fileInput.files?.[0];
  if (file) {
    void handleFile(file);
  }
});

for (const eventName of ['dragenter', 'dragover']) {
  dom.dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dom.dropZone.classList.add('is-dragging');
  });
}
for (const eventName of ['dragleave', 'drop']) {
  dom.dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dom.dropZone.classList.remove('is-dragging');
  });
}
dom.dropZone.addEventListener('drop', (event) => {
  const file = event.dataTransfer?.files?.[0];
  if (file) {
    void handleFile(file);
  }
});
window.addEventListener('dragover', (event) => event.preventDefault());
window.addEventListener('drop', (event) => event.preventDefault());

dom.prevPage.addEventListener('click', () => {
  void viewer.goToPage(viewer.currentPage - 1);
});
dom.nextPage.addEventListener('click', () => {
  void viewer.goToPage(viewer.currentPage + 1);
});
dom.pageInput.addEventListener('change', () => {
  const page = Number(dom.pageInput.value);
  if (Number.isFinite(page)) {
    void viewer.goToPage(page);
  } else {
    updatePageControls(viewer.currentPage, viewer.pageCount);
  }
});
dom.pageInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    event.preventDefault();
    const page = Number(dom.pageInput.value);
    if (Number.isFinite(page)) {
      void viewer.goToPage(page);
    }
    dom.pageInput.blur();
  }
});

dom.zoomIn.addEventListener('click', () => {
  void viewer.zoomIn();
});
dom.zoomOut.addEventListener('click', () => {
  void viewer.zoomOut();
});
dom.fitWidth.addEventListener('click', () => {
  void viewer.fitToWidth();
});

dom.errorClose.addEventListener('click', hideError);

document.addEventListener('keydown', (event) => {
  if (!viewer.hasDocument) {
    return;
  }
  const tagName = event.target?.tagName;
  if (tagName === 'INPUT' || tagName === 'TEXTAREA' || tagName === 'BUTTON') {
    return;
  }
  if (event.key === 'ArrowLeft') {
    event.preventDefault();
    void viewer.goToPage(viewer.currentPage - 1);
  } else if (event.key === 'ArrowRight') {
    event.preventDefault();
    void viewer.goToPage(viewer.currentPage + 1);
  }
});

window.addEventListener('resize', () => {
  window.clearTimeout(resizeTimer);
  resizeTimer = window.setTimeout(() => {
    void viewer.handleResize();
  }, 180);
});

if (activeBook === null) {
  dom.viewer.hidden = true;
  dom.emptyState.hidden = false;
}
