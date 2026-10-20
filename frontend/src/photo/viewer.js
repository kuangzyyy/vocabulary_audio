import { toPercentBox } from '../pdf/coordinates.js';

const MIN_SCALE = 1;
const MAX_SCALE = 6;
const PAN_THRESHOLD = 6;

/**
 * Photo display with normalized OCR hit boxes, pinch zoom and drag panning.
 *
 * The image and both hit layers live in the same transformed stage, so the
 * boxes stay aligned at any scale or offset without recomputing coordinates.
 */
export class PhotoViewer {
  constructor(elements, callbacks = {}) {
    this.viewport = elements.viewport;
    this.stage = elements.stage;
    this.image = elements.image;
    this.sentenceLayer = elements.sentenceLayer;
    this.wordLayer = elements.wordLayer;
    this.loading = elements.loading;
    this.callbacks = callbacks;

    this.photo = null;
    this.baseWidth = 0;
    this.baseHeight = 0;
    this.scale = 1;
    this.offsetX = 0;
    this.offsetY = 0;
    this.pointers = new Map();
    this.dragStart = null;
    this.pinch = null;
    this.moved = false;
    this.suppressClick = false;
    this.suppressTimer = 0;
    this.clickMode = 'word';
    this.setClickMode('word');
    this.bindGestures();
  }

  async load(photo) {
    this.photo = photo;
    this.clearLayers();
    this.setLoading(true, '正在加载照片…');
    try {
      await this.loadImage(photo.photo_url);
      this.renderHitLayers(photo);
      this.fit();
      requestAnimationFrame(() => {
        if (this.photo) {
          this.fit();
        }
      });
      this.setLoading(false);
    } catch (error) {
      this.setLoading(false);
      this.clear();
      throw error;
    }
  }

  clear() {
    this.photo = null;
    this.image.removeAttribute('src');
    this.clearLayers();
    this.stage.style.width = '0px';
    this.stage.style.height = '0px';
    this.baseWidth = 0;
    this.baseHeight = 0;
    this.scale = 1;
    this.offsetX = 0;
    this.offsetY = 0;
    this.applyTransform();
  }

  setLoading(visible, text = '正在识别照片…') {
    this.loading.textContent = text;
    this.loading.hidden = !visible;
  }

  setClickMode(mode) {
    this.clickMode = mode === 'sentence' ? 'sentence' : 'word';
    const sentenceMode = this.clickMode === 'sentence';
    this.stage.classList.toggle('mode-sentence', sentenceMode);
    this.stage.classList.toggle('mode-word', !sentenceMode);
  }

  zoomBy(factor) {
    if (!this.photo) {
      return;
    }
    const anchorX = this.viewport.clientWidth / 2;
    const anchorY = this.viewport.clientHeight / 2;
    this.setScale(this.scale * factor, anchorX, anchorY);
  }

  reset() {
    if (this.photo) {
      this.fit();
    }
  }

  handleResize() {
    if (this.photo) {
      this.fit();
    }
  }

  async loadImage(url) {
    await new Promise((resolve, reject) => {
      const onLoad = () => {
        cleanup();
        resolve();
      };
      const onError = () => {
        cleanup();
        reject(new Error('照片加载失败，请重新选择。'));
      };
      const cleanup = () => {
        this.image.removeEventListener('load', onLoad);
        this.image.removeEventListener('error', onError);
      };
      this.image.addEventListener('load', onLoad);
      this.image.addEventListener('error', onError);
      this.image.src = url;
      if (this.image.complete && this.image.naturalWidth > 0) {
        onLoad();
      }
    });
  }

  fit() {
    if (!this.photo) {
      return;
    }
    const viewportWidth = Math.max(this.viewport.clientWidth, 320);
    const viewportHeight = Math.max(this.viewport.clientHeight, 260);
    const availableWidth = Math.max(viewportWidth - 24, 160);
    const availableHeight = Math.max(viewportHeight - 24, 160);
    const aspect =
      (this.image.naturalWidth || this.photo.width) /
      (this.image.naturalHeight || this.photo.height || 1);

    let width = availableWidth;
    let height = width / aspect;
    if (height > availableHeight) {
      height = availableHeight;
      width = height * aspect;
    }

    this.baseWidth = width;
    this.baseHeight = height;
    this.stage.style.width = `${width}px`;
    this.stage.style.height = `${height}px`;
    this.scale = 1;
    this.offsetX = (viewportWidth - width) / 2;
    this.offsetY = (viewportHeight - height) / 2;
    this.applyTransform();
  }

  setScale(nextScale, anchorX, anchorY) {
    const clamped = Math.max(MIN_SCALE, Math.min(MAX_SCALE, nextScale));
    if (clamped === this.scale) {
      return;
    }
    const ratio = clamped / this.scale;
    this.offsetX = anchorX - (anchorX - this.offsetX) * ratio;
    this.offsetY = anchorY - (anchorY - this.offsetY) * ratio;
    this.scale = clamped;
    this.clampOffsets();
    this.applyTransform();
  }

  clampOffsets() {
    const viewportWidth = this.viewport.clientWidth;
    const viewportHeight = this.viewport.clientHeight;
    const scaledWidth = this.baseWidth * this.scale;
    const scaledHeight = this.baseHeight * this.scale;

    if (scaledWidth <= viewportWidth) {
      this.offsetX = (viewportWidth - scaledWidth) / 2;
    } else {
      this.offsetX = Math.min(0, Math.max(viewportWidth - scaledWidth, this.offsetX));
    }
    if (scaledHeight <= viewportHeight) {
      this.offsetY = (viewportHeight - scaledHeight) / 2;
    } else {
      this.offsetY = Math.min(0, Math.max(viewportHeight - scaledHeight, this.offsetY));
    }
  }

  applyTransform() {
    this.stage.style.transform =
      `translate3d(${this.offsetX}px, ${this.offsetY}px, 0) scale(${this.scale})`;
    this.callbacks.onZoomChange?.(this.scale);
  }

  renderHitLayers(photo) {
    this.clearLayers();

    const sentenceFragment = document.createDocumentFragment();
    for (const sentence of photo.sentences ?? []) {
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
        element.setAttribute('aria-label', `播放整句合成语音：${sentence.text}`);
        element.title = `点击播放整句（本机合成语音，非真人录音）：${sentence.text}`;
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
    for (const word of photo.words ?? []) {
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

  bindGestures() {
    this.viewport.addEventListener(
      'pointerdown',
      (event) => {
        if (event.pointerType === 'mouse' && event.button !== 0) {
          return;
        }
        this.pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
        if (this.pointers.size === 1) {
          this.dragStart = {
            x: event.clientX,
            y: event.clientY,
            offsetX: this.offsetX,
            offsetY: this.offsetY,
          };
          this.moved = false;
          this.pinch = null;
          this.viewport.classList.add('is-panning');
        } else if (this.pointers.size === 2) {
          this.startPinch();
          this.moved = true;
          this.suppressClick = true;
        }
      },
      { passive: true },
    );

    this.viewport.addEventListener(
      'pointermove',
      (event) => {
        if (!this.pointers.has(event.pointerId)) {
          return;
        }
        this.pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });

        if (this.pointers.size >= 2 && this.pinch) {
          const points = [...this.pointers.values()];
          const distance = Math.hypot(
            points[1].x - points[0].x,
            points[1].y - points[0].y,
          );
          const midX = (points[0].x + points[1].x) / 2;
          const midY = (points[0].y + points[1].y) / 2;
          const nextScale =
            this.pinch.scale * (distance / Math.max(this.pinch.distance, 1));
          const ratio =
            Math.max(MIN_SCALE, Math.min(MAX_SCALE, nextScale)) / this.pinch.scale;
          this.scale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, nextScale));
          this.offsetX =
            midX - (this.pinch.midX - this.pinch.offsetX) * ratio;
          this.offsetY =
            midY - (this.pinch.midY - this.pinch.offsetY) * ratio;
          this.clampOffsets();
          this.applyTransform();
          return;
        }

        if (this.pointers.size === 1 && this.dragStart) {
          const dx = event.clientX - this.dragStart.x;
          const dy = event.clientY - this.dragStart.y;
          if (!this.moved && Math.hypot(dx, dy) > PAN_THRESHOLD) {
            this.moved = true;
            this.suppressClick = true;
          }
          if (this.moved) {
            this.offsetX = this.dragStart.offsetX + dx;
            this.offsetY = this.dragStart.offsetY + dy;
            this.clampOffsets();
            this.applyTransform();
          }
        }
      },
      { passive: true },
    );

    const finishPointer = (event) => {
      this.pointers.delete(event.pointerId);
      if (this.pointers.size === 1) {
        const remaining = [...this.pointers.entries()][0];
        this.dragStart = {
          x: remaining[1].x,
          y: remaining[1].y,
          offsetX: this.offsetX,
          offsetY: this.offsetY,
        };
        this.pinch = null;
      } else if (this.pointers.size === 0) {
        this.dragStart = null;
        this.pinch = null;
        this.viewport.classList.remove('is-panning');
        if (this.moved) {
          window.clearTimeout(this.suppressTimer);
          this.suppressTimer = window.setTimeout(() => {
            this.suppressClick = false;
          }, 400);
        }
      }
    };
    this.viewport.addEventListener('pointerup', finishPointer, { passive: true });
    this.viewport.addEventListener('pointercancel', finishPointer, { passive: true });

    this.viewport.addEventListener(
      'click',
      (event) => {
        if (this.suppressClick) {
          event.preventDefault();
          event.stopPropagation();
          this.suppressClick = false;
        }
      },
      true,
    );

    this.viewport.addEventListener(
      'wheel',
      (event) => {
        if (!this.photo) {
          return;
        }
        event.preventDefault();
        const rect = this.viewport.getBoundingClientRect();
        const anchorX = event.clientX - rect.left;
        const anchorY = event.clientY - rect.top;
        const factor = event.deltaY < 0 ? 1.15 : 1 / 1.15;
        this.setScale(this.scale * factor, anchorX, anchorY);
      },
      { passive: false },
    );
  }

  startPinch() {
    const points = [...this.pointers.values()];
    const distance = Math.hypot(
      points[1].x - points[0].x,
      points[1].y - points[0].y,
    );
    this.pinch = {
      distance: Math.max(distance, 1),
      midX: (points[0].x + points[1].x) / 2,
      midY: (points[0].y + points[1].y) / 2,
      scale: this.scale,
      offsetX: this.offsetX,
      offsetY: this.offsetY,
    };
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
    console.warn('Skipped an invalid photo text box:', bbox, error);
    return false;
  }
}
