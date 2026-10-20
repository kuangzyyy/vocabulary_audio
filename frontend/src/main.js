import './styles/main.css';

import { fetchSentenceAudio, fetchWordAudio, uploadPdf } from './api/client.js';
import { accentLabel, accentOptions } from './audio/audioMeta.js';
import { AudioPlaybackController } from './audio/audioPlayback.js';
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
  modeWord: byId('mode-word'),
  modeSentence: byId('mode-sentence'),
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
  accentControls: byId('accent-controls'),
  audioSource: byId('audio-source'),
  audioSourceLink: byId('audio-source-link'),
  audioLicenseLink: byId('audio-license-link'),
  audioAttribution: byId('audio-attribution'),
  syntheticBadge: byId('synthetic-badge'),
  syntheticNote: byId('synthetic-note'),
  playIndicator: byId('play-indicator'),
  playText: byId('play-text'),
  replayButton: byId('replay-button'),
  wordAudio: byId('word-audio'),
  sentenceAudio: byId('sentence-audio'),
  errorBanner: byId('error-banner'),
  errorText: byId('error-text'),
  errorClose: byId('error-close'),
};

let activeBook = null;
let fileBusy = false;
let resizeTimer = 0;
let activeHitElement = null;
let renderedPage = 0;
let currentWordText = '';
let currentAudioMeta = null;
let currentAudioKind = null;
let clickMode = readClickMode();

const wordAudioController = new AudioPlaybackController(
  dom.wordAudio,
  {
    onLoading: ({ accent }) => {
      dom.recognizedMeta.textContent =
        accent === 'auto'
          ? '正在查找 Wikimedia Commons 真人录音…'
          : `正在加载${accentLabel(accent)}真人录音…`;
      setPlayState('loading', '加载中…');
      disableAccentButtons(true);
    },
    onMeta: (metadata) => {
      currentAudioKind = 'word';
      currentAudioMeta = metadata;
      renderAudioMetadata(metadata);
      dom.replayButton.hidden = false;
      setPlayState('ready', metadata.cached ? '本地缓存' : '准备播放');
    },
    onPlaying: () => {
      setPlayState('playing', '播放中…');
    },
    onEnded: () => {
      setPlayState('ready', '播放完成');
    },
    onAutoplayBlocked: () => {
      dom.recognizedMeta.textContent = '浏览器阻止了自动播放，请点击“重播”。';
      setPlayState('ready', '点击重播');
      dom.replayButton.hidden = false;
    },
    onFetchError: (error) => {
      wordAudioController.stop();
      currentAudioMeta = null;
      currentAudioKind = null;
      clearAudioDetails();
      dom.recognizedMeta.textContent = audioErrorMessage(error);
      setPlayState('error', '无音频');
    },
    onPlaybackError: (error) => {
      dom.recognizedMeta.textContent = audioErrorMessage(error);
      setPlayState('error', '播放失败');
      dom.replayButton.hidden = !currentAudioMeta;
    },
  },
  { fetcher: fetchWordAudio },
);

const sentenceAudioController = new AudioPlaybackController(
  dom.sentenceAudio,
  {
    onLoading: () => {
      showSyntheticNotice();
      dom.recognizedMeta.textContent = '正在生成本机合成语音…';
      setPlayState('loading', '合成中…');
    },
    onMeta: (metadata) => {
      currentAudioKind = 'sentence';
      currentAudioMeta = metadata;
      renderSentenceAudioMetadata(metadata);
      dom.replayButton.hidden = false;
      setPlayState(
        'ready',
        metadata.cached ? '合成语音 · 本地缓存' : '合成语音',
      );
    },
    onPlaying: () => {
      showSyntheticNotice();
      setPlayState('playing', '合成语音播放中…');
    },
    onEnded: () => {
      setPlayState('ready', '合成语音播放完成');
    },
    onAutoplayBlocked: () => {
      dom.recognizedMeta.textContent =
        '浏览器阻止了自动播放，请点击“重播”（本机合成语音）。';
      setPlayState('ready', '点击重播');
      dom.replayButton.hidden = false;
    },
    onFetchError: (error) => {
      sentenceAudioController.stop();
      currentAudioMeta = null;
      currentAudioKind = null;
      clearAudioDetails();
      dom.recognizedMeta.textContent = audioErrorMessage(error);
      setPlayState('error', '合成失败');
    },
    onPlaybackError: () => {
      dom.recognizedMeta.textContent =
        '合成语音播放失败，请点击“重播”再试。';
      setPlayState('error', '播放失败');
      dom.replayButton.hidden = !currentAudioMeta;
    },
  },
  { fetcher: (text) => fetchSentenceAudio(text) },
);

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
      handleWordClick(word, element);
    },
    onSentenceClick: (sentence, element) => {
      handleSentenceClick(sentence, element);
    },
    onPageLoading: (page, pageCount) => {
      if (page !== renderedPage) {
        resetResult('正在加载页面…');
      }
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
      wordAudioController.stop();
      sentenceAudioController.stop();
      showError(message);
    },
    onLoadingChange: (isLoading) => {
      dom.viewer.classList.toggle('is-loading', isLoading);
    },
  },
);

setClickMode(clickMode);

function readClickMode() {
  try {
    return localStorage.getItem('vocabulary-audio-click-mode') === 'sentence'
      ? 'sentence'
      : 'word';
  } catch {
    return 'word';
  }
}

function setClickMode(mode) {
  clickMode = mode === 'sentence' ? 'sentence' : 'word';
  const sentenceMode = clickMode === 'sentence';
  dom.modeWord.setAttribute('aria-pressed', String(!sentenceMode));
  dom.modeSentence.setAttribute('aria-pressed', String(sentenceMode));
  viewer.setClickMode(clickMode);
  try {
    localStorage.setItem('vocabulary-audio-click-mode', clickMode);
  } catch {
    // Private browsing may reject localStorage; the mode still works.
  }
  if (!activeHitElement) {
    dom.recognizedMeta.textContent = clickModeHint();
  }
}

function clickModeHint() {
  return clickMode === 'sentence'
    ? '整句模式：点句子播放本机合成语音（非真人录音）'
    : '单词模式：点单词播放真人录音；点句子空白处可播整句';
}

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
      wordAudioController.stop();
      sentenceAudioController.stop();
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

function audioErrorMessage(error) {
  if (error instanceof TypeError && /fetch|network/i.test(error.message)) {
    return '无法连接本地后端，请确认服务已启动。';
  }
  return error?.message || '音频加载失败。';
}

function setActiveHit(element) {
  document
    .querySelectorAll('.sentence-hit.is-active, .word-hit.is-active')
    .forEach((node) => node.classList.remove('is-active'));
  activeHitElement = element;
  if (!element) {
    return;
  }
  if (element.classList.contains('sentence-hit')) {
    const sentenceId = element.dataset.sentenceId;
    document.querySelectorAll('.sentence-hit').forEach((node) => {
      if (node.dataset.sentenceId === sentenceId) {
        node.classList.add('is-active');
      }
    });
  } else {
    element.classList.add('is-active');
  }
}

function handleWordClick(word, element) {
  sentenceAudioController.stop();
  setActiveHit(element);
  currentWordText = word.text;
  currentAudioMeta = null;
  currentAudioKind = null;
  dom.recognizedText.textContent = word.text;
  dom.recognizedMeta.textContent = '正在查找 Wikimedia Commons 真人录音…';
  dom.resultPanel.dataset.recognized = word.text;
  dom.resultPanel.dataset.type = '单词';
  clearAudioDetails();
  setPlayState('loading', '加载中…');
  void wordAudioController.play(word.text, 'auto');
}

function handleSentenceClick(sentence, element) {
  wordAudioController.stop();
  setActiveHit(element);
  currentWordText = '';
  currentAudioMeta = null;
  currentAudioKind = 'sentence';
  dom.recognizedText.textContent = sentence.text;
  dom.recognizedMeta.textContent = '正在生成本机合成语音…';
  dom.resultPanel.dataset.recognized = sentence.text;
  dom.resultPanel.dataset.type = '例句';
  clearAudioDetails();
  showSyntheticNotice();
  setPlayState('loading', '合成中…');
  void sentenceAudioController.play(sentence.text, 'auto');
}

function renderAudioMetadata(metadata) {
  hideSyntheticNotice();
  const accent = metadata.accent;
  dom.recognizedMeta.textContent =
    `${accentLabel(accent)} · Wikimedia Commons 真人录音` +
    (metadata.cached ? ' · 本地缓存' : '');
  dom.resultPanel.dataset.audioKind = 'word';
  dom.resultPanel.dataset.audioAccent = accent;
  dom.resultPanel.dataset.audioCached = metadata.cached ? 'true' : 'false';
  dom.resultPanel.dataset.synthetic = 'false';

  const { available, canChoose } = accentOptions(metadata);
  dom.accentControls.replaceChildren();
  if (canChoose) {
    for (const option of ['us', 'uk']) {
      if (!available.includes(option)) {
        continue;
      }
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'accent-button';
      button.textContent = accentLabel(option);
      button.setAttribute('aria-pressed', String(option === accent));
      button.addEventListener('click', () => {
        playAccent(option);
      });
      dom.accentControls.append(button);
    }
    dom.accentControls.hidden = false;
  } else if (available.length > 0) {
    const label = document.createElement('span');
    label.className = 'accent-static';
    label.textContent =
      accent === 'unknown' ? '口音未标注' : `${accentLabel(accent)}发音`;
    dom.accentControls.append(label);
    dom.accentControls.hidden = false;
  } else {
    dom.accentControls.hidden = true;
  }

  const sourceUrl = safeHttpUrl(metadata.source_page);
  if (!sourceUrl) {
    dom.audioSource.hidden = true;
    return;
  }
  dom.audioSource.hidden = false;
  dom.audioSourceLink.href = sourceUrl;
  dom.audioLicenseLink.href = safeHttpUrl(metadata.license_url) ?? sourceUrl;
  dom.audioLicenseLink.textContent = metadata.license || '许可信息';
  dom.audioAttribution.textContent = metadata.attribution
    ? ` · ${metadata.attribution}`
    : '';
  dom.audioAttribution.title = metadata.attribution || '';
}

function renderSentenceAudioMetadata(metadata) {
  showSyntheticNotice(metadata.note);
  dom.recognizedMeta.textContent =
    `合成语音（非真人录音） · ${metadata.engine} · ${metadata.voice}` +
    (metadata.cached ? ' · 本地缓存' : '');
  dom.resultPanel.dataset.audioKind = 'sentence';
  dom.resultPanel.dataset.synthetic = 'true';
  delete dom.resultPanel.dataset.audioAccent;
  dom.resultPanel.dataset.audioCached = metadata.cached ? 'true' : 'false';
  dom.accentControls.replaceChildren();
  dom.accentControls.hidden = true;
  dom.audioSource.hidden = true;
}

function playAccent(accent) {
  if (!currentWordText) {
    return;
  }
  dom.recognizedMeta.textContent = `正在加载${accentLabel(accent)}真人录音…`;
  setPlayState('loading', '加载中…');
  disableAccentButtons(true);
  void wordAudioController.play(currentWordText, accent);
}

function disableAccentButtons(disabled) {
  for (const button of dom.accentControls.querySelectorAll('button')) {
    button.disabled = disabled;
  }
}

function showSyntheticNotice(note) {
  dom.syntheticBadge.hidden = false;
  dom.syntheticNote.hidden = false;
  dom.syntheticNote.textContent =
    note || '本机 Windows 系统语音合成生成，不是真人录音。';
}

function hideSyntheticNotice() {
  dom.syntheticBadge.hidden = true;
  dom.syntheticNote.hidden = true;
}

function clearAudioDetails() {
  dom.accentControls.replaceChildren();
  dom.accentControls.hidden = true;
  dom.audioSource.hidden = true;
  dom.audioSourceLink.removeAttribute('href');
  dom.audioLicenseLink.removeAttribute('href');
  dom.audioLicenseLink.textContent = '';
  dom.audioAttribution.textContent = '';
  dom.replayButton.hidden = true;
  hideSyntheticNotice();
  delete dom.resultPanel.dataset.audioKind;
  delete dom.resultPanel.dataset.audioAccent;
  delete dom.resultPanel.dataset.audioCached;
  delete dom.resultPanel.dataset.synthetic;
}

function setPlayState(state, text) {
  dom.playIndicator.classList.remove('is-loading', 'is-playing', 'is-error');
  if (state === 'loading' || state === 'playing' || state === 'error') {
    dom.playIndicator.classList.add(`is-${state}`);
  }
  dom.playText.textContent = text;
}

function resetResult(text) {
  wordAudioController.stop();
  sentenceAudioController.stop();
  currentWordText = '';
  currentAudioMeta = null;
  currentAudioKind = null;
  document
    .querySelectorAll('.sentence-hit.is-active, .word-hit.is-active')
    .forEach((node) => node.classList.remove('is-active'));
  activeHitElement = null;
  dom.recognizedText.textContent =
    text || (clickMode === 'sentence' ? '点击页面上的句子' : '点击页面上的英文单词');
  dom.recognizedMeta.textContent = clickModeHint();
  clearAudioDetails();
  setPlayState('idle', clickMode === 'sentence' ? '合成语音' : '真人发音');
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

function safeHttpUrl(value) {
  if (!value) {
    return null;
  }
  try {
    const url = new URL(value, window.location.origin);
    return url.protocol === 'http:' || url.protocol === 'https:'
      ? url.href
      : null;
  } catch {
    return null;
  }
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

dom.modeWord.addEventListener('click', () => {
  setClickMode('word');
});
dom.modeSentence.addEventListener('click', () => {
  setClickMode('sentence');
});

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

dom.replayButton.addEventListener('click', () => {
  if (!currentAudioMeta) {
    return;
  }
  if (currentAudioKind === 'sentence') {
    sentenceAudioController.replay();
  } else {
    wordAudioController.replay();
  }
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
