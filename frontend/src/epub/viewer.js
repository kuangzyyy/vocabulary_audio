import ePub from 'epubjs';

import { epubFileUrl } from '../api/client.js';
import {
  cleanText,
  extractWordAt,
  flattenToc,
  hrefMatches,
  sentenceAtOffset,
} from './text.js';

const FONT_MIN = 70;
const FONT_MAX = 180;
const FONT_STEP = 10;
const BLOCK_TAGS = new Set([
  'p',
  'li',
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
  'blockquote',
  'dd',
  'dt',
  'td',
  'th',
  'figcaption',
  'pre',
  'section',
  'article',
  'aside',
  'header',
  'footer',
  'main',
  'div',
]);

const CONTENT_STYLE = `
::highlight(va-word) {
  background-color: rgba(250, 204, 21, 0.55);
  color: inherit;
}
html.va-click-word body,
html.va-click-sentence body {
  -webkit-tap-highlight-color: transparent;
}
html.va-click-word body,
html.va-click-sentence body {
  cursor: pointer;
}
`;

/**
 * EPUB.js wrapper that preserves the book's reflowable layout and turns text
 * clicks into word/sentence callbacks without wrapping or replacing text nodes.
 */
export class EpubViewer {
  constructor(elements, callbacks = {}) {
    this.container = elements.container;
    this.loading = elements.loading;
    this.callbacks = callbacks;

    this.book = null;
    this.rendition = null;
    this.epub = null;
    this.chapters = [];
    this.chapterCount = 0;
    this.currentHref = '';
    this.currentIndex = 0;
    this.clickMode = 'word';
    this.fontScale = 100;
    this.destroyed = false;
    this.boundDocuments = new WeakSet();
    this.highlightContents = null;
    this.highlightTimer = 0;
    this.resizeObserver = null;
    this.resizeTimer = 0;
    this.lastWidth = 0;
    this.lastHeight = 0;
  }

  get hasBook() {
    return Boolean(this.book && this.rendition);
  }

  async load(epub) {
    this.clear();
    this.destroyed = false;
    this.epub = epub;
    this.setLoading(true, '正在加载 EPUB…');

    try {
      const book = ePub(epubFileUrl(epub.epub_id), { openAs: 'epub' });
      this.book = book;
      await book.ready;
      if (this.destroyed) {
        return null;
      }

      const navigation = await book.loaded.navigation.catch(() => null);
      this.chapters = flattenToc(navigation?.toc ?? []);
      this.chapterCount =
        book.spine?.spineItems?.length || epub.chapter_count || 0;

      const rendition = book.renderTo(this.container, {
        width: '100%',
        height: '100%',
        flow: 'scrolled-doc',
        spread: 'none',
        allowScriptedContent: false,
        allowPopups: false,
      });
      this.rendition = rendition;
      rendition.hooks.content.register((contents) => {
        this.decorateContents(contents);
      });
      rendition.on('rendered', () => {
        this.setLoading(false);
      });
      rendition.on('relocated', (location) => {
        this.handleRelocated(location);
      });

      this.applyFontSize();
      await rendition.display();
      if (this.destroyed) {
        return null;
      }

      this.setLoading(false);
      this.observeResize();
      const initial = this.locationInfo(rendition.location);
      const result = {
        chapters: this.chapters,
        chapterCount: this.chapterCount,
        fontScale: this.fontScale,
        ...initial,
      };
      this.callbacks.onReady?.(result);
      return result;
    } catch (error) {
      this.setLoading(false);
      this.destroyBook();
      console.warn('EPUB failed to open:', error?.message);
      throw new Error(
        '无法打开这个 EPUB，文件可能已损坏或使用了不支持的 DRM。',
      );
    }
  }

  setClickMode(mode) {
    this.clickMode = mode === 'sentence' ? 'sentence' : 'word';
    this.clearHighlight();
    for (const contents of this.rendition?.getContents?.() ?? []) {
      this.applyMode(contents);
    }
  }

  setFontScale(scale) {
    const next = Math.max(
      FONT_MIN,
      Math.min(FONT_MAX, Math.round(Number(scale) || 100)),
    );
    this.fontScale = next;
    this.applyFontSize();
    this.callbacks.onFontChange?.(next);
    return next;
  }

  async displayChapter(href) {
    if (!this.rendition || !href) {
      return;
    }
    this.setLoading(true, '正在加载章节…');
    try {
      await this.rendition.display(href);
    } catch (error) {
      console.warn('EPUB chapter failed:', error?.message);
      this.callbacks.onError?.('这一章加载失败，请换一章重试。');
    } finally {
      this.setLoading(false);
    }
  }

  async nextChapter() {
    if (!this.rendition) {
      return;
    }
    this.setLoading(true, '正在加载下一章…');
    try {
      await this.rendition.next();
    } catch (error) {
      console.warn('EPUB next chapter failed:', error?.message);
      this.callbacks.onError?.('下一章加载失败，请重试。');
    } finally {
      this.setLoading(false);
    }
  }

  async prevChapter() {
    if (!this.rendition) {
      return;
    }
    this.setLoading(true, '正在加载上一章…');
    try {
      await this.rendition.prev();
    } catch (error) {
      console.warn('EPUB previous chapter failed:', error?.message);
      this.callbacks.onError?.('上一章加载失败，请重试。');
    } finally {
      this.setLoading(false);
    }
  }

  clear() {
    this.destroyed = true;
    this.clearHighlight();
    window.clearTimeout(this.resizeTimer);
    this.resizeTimer = 0;
    this.resizeObserver?.disconnect();
    this.resizeObserver = null;
    this.destroyBook();
    this.container.replaceChildren();
    this.epub = null;
    this.chapters = [];
    this.chapterCount = 0;
    this.currentHref = '';
    this.currentIndex = 0;
    this.lastWidth = 0;
    this.lastHeight = 0;
    this.setLoading(false);
  }

  destroyBook() {
    const book = this.book;
    this.book = null;
    this.rendition = null;
    if (book) {
      try {
        book.destroy();
      } catch (error) {
        console.warn('EPUB cleanup failed:', error?.message);
      }
    }
    this.boundDocuments = new WeakSet();
  }

  setLoading(visible, text = '正在加载 EPUB…') {
    if (!this.loading) {
      return;
    }
    if (text) {
      this.loading.textContent = text;
    }
    this.loading.hidden = !visible;
  }

  decorateContents(contents) {
    const document = contents?.document;
    if (!document) {
      return;
    }

    if (!document.getElementById('va-epub-style')) {
      const style = document.createElement('style');
      style.id = 'va-epub-style';
      style.textContent = CONTENT_STYLE;
      (document.head || document.documentElement).append(style);
    }

    this.applyMode(contents);

    if (!this.boundDocuments.has(document)) {
      document.addEventListener(
        'click',
        (event) => this.handleDocumentClick(contents, event),
        true,
      );
      this.boundDocuments.add(document);
    }
  }

  applyMode(contents) {
    const root = contents?.document?.documentElement;
    if (!root) {
      return;
    }
    root.classList.toggle('va-click-word', this.clickMode === 'word');
    root.classList.toggle('va-click-sentence', this.clickMode === 'sentence');
  }

  handleDocumentClick(contents, event) {
    if (!this.book || event.defaultPrevented || event.button !== 0) {
      return;
    }
    const target = event.target;
    if (target?.closest?.('a[href]')) {
      return;
    }

    const point = this.pointToText(
      contents.document,
      event.clientX,
      event.clientY,
    );
    if (!point) {
      return;
    }
    const { node, offset } = point;

    if (this.clickMode === 'word') {
      const word = extractWordAt(node.data, offset);
      if (!word) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      this.highlight(contents, node, word.start, word.end);
      this.callbacks.onWordClick?.({ text: word.text });
      return;
    }

    const block = this.closestBlock(contents.document, node);
    if (!block) {
      return;
    }
    const blockOffset = this.offsetInBlock(
      contents.document,
      block,
      node,
      offset,
    );
    const sentence = sentenceAtOffset(block.textContent || '', blockOffset);
    if (!sentence) {
      return;
    }
    const text = cleanText(sentence.text);
    if (!text) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    const word = extractWordAt(node.data, offset);
    if (word) {
      this.highlight(contents, node, word.start, word.end);
    }
    this.callbacks.onSentenceClick?.({ text });
  }

  pointToText(document, x, y) {
    let node = null;
    let offset = 0;
    try {
      if (typeof document.caretRangeFromPoint === 'function') {
        const range = document.caretRangeFromPoint(x, y);
        if (range) {
          node = range.startContainer;
          offset = range.startOffset;
        }
      } else if (typeof document.caretPositionFromPoint === 'function') {
        const position = document.caretPositionFromPoint(x, y);
        if (position) {
          node = position.offsetNode;
          offset = position.offset;
        }
      }
    } catch {
      return null;
    }
    if (!node) {
      return null;
    }
    if (node.nodeType === 3 && node.data) {
      return { node, offset };
    }

    const element = node.nodeType === 1 ? node : node.parentElement;
    if (!element) {
      return null;
    }
    const child =
      element.childNodes?.[Math.min(offset, element.childNodes.length - 1)] ||
      element;
    const textNode = this.firstTextNode(document, child);
    return textNode ? { node: textNode, offset: 0 } : null;
  }

  firstTextNode(document, root) {
    if (root?.nodeType === 3 && root.data) {
      return root;
    }
    if (!root) {
      return null;
    }
    const walker = document.createTreeWalker(root, 4);
    let node = walker.nextNode();
    while (node) {
      if (node.data && node.data.trim()) {
        return node;
      }
      node = walker.nextNode();
    }
    return null;
  }

  closestBlock(document, node) {
    let element = node.parentElement;
    while (
      element &&
      element !== document.body &&
      !BLOCK_TAGS.has(element.tagName.toLowerCase())
    ) {
      element = element.parentElement;
    }
    if (element && element !== document.body) {
      return element;
    }
    return node.parentElement;
  }

  offsetInBlock(document, block, node, offset) {
    try {
      const range = document.createRange();
      range.selectNodeContents(block);
      range.setEnd(node, offset);
      return range.toString().length;
    } catch {
      return 0;
    }
  }

  highlight(contents, node, start, end) {
    try {
      const window = contents.window;
      if (!window?.CSS?.highlights || typeof window.Highlight !== 'function') {
        return;
      }
      this.clearHighlight();
      const range = contents.document.createRange();
      range.setStart(node, start);
      range.setEnd(node, end);
      const highlight = new window.Highlight(range);
      window.CSS.highlights.set('va-word', highlight);
      this.highlightContents = contents;
      this.highlightTimer = window.setTimeout(() => {
        this.clearHighlight();
      }, 1800);
    } catch {
      // Highlighting is optional; audio and the result panel still work.
    }
  }

  clearHighlight() {
    const contents = this.highlightContents;
    if (contents?.window) {
      try {
        contents.window.clearTimeout(this.highlightTimer);
        contents.window.CSS?.highlights?.delete('va-word');
      } catch {
        // The iframe may already be gone.
      }
    }
    this.highlightContents = null;
    this.highlightTimer = 0;
  }

  applyFontSize() {
    if (!this.rendition) {
      return;
    }
    this.rendition.themes.fontSize(
      this.fontScale === 100 ? '' : `${this.fontScale}%`,
    );
  }

  handleRelocated(location) {
    const info = this.locationInfo(location);
    this.currentHref = info.href;
    this.currentIndex = info.index;
    this.setLoading(false);
    this.callbacks.onLocationChange?.({
      ...info,
      chapterCount: this.chapterCount,
    });
  }

  locationInfo(location) {
    const start = location?.start ?? {};
    const href = typeof start.href === 'string' ? start.href : '';
    const index = Number.isInteger(start.index) ? start.index : 0;
    const chapter = this.chapters.find((item) =>
      hrefMatches(item.href, href),
    );
    return {
      href,
      index,
      label: chapter?.label || `第 ${index + 1} 节`,
      percentage: Number.isFinite(start.percentage) ? start.percentage : null,
    };
  }

  observeResize() {
    if (typeof ResizeObserver !== 'function') {
      return;
    }
    const rect = this.container.getBoundingClientRect();
    this.lastWidth = Math.round(rect.width);
    this.lastHeight = Math.round(rect.height);

    this.resizeObserver = new ResizeObserver(() => {
      if (!this.rendition) {
        return;
      }
      const next = this.container.getBoundingClientRect();
      const width = Math.round(next.width);
      const height = Math.round(next.height);
      if (!width || !height) {
        return;
      }
      if (
        Math.abs(width - this.lastWidth) <= 1 &&
        Math.abs(height - this.lastHeight) <= 1
      ) {
        return;
      }
      this.lastWidth = width;
      this.lastHeight = height;
      if (!this.rendition?.location?.start?.cfi) {
        // A resize before the first location is known would clear the view
        // without a CFI to restore it, leaving a blank EPUB pane.
        return;
      }
      window.clearTimeout(this.resizeTimer);
      this.resizeTimer = window.setTimeout(() => {
        if (!this.rendition?.location?.start?.cfi) {
          return;
        }
        this.rendition.resize(width, height);
      }, 180);
    });
    this.resizeObserver.observe(this.container);
  }
}
