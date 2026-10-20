/**
 * One audio element and one in-flight request at a time.
 *
 * The same controller is used for word recordings and sentence TTS; the caller
 * supplies the fetcher. Duplicate clicks for the same key reuse the loaded
 * audio; a new request cancels the previous one and pauses playback.
 */
export class AudioPlaybackController {
  constructor(audioElement, callbacks = {}, options = {}) {
    if (typeof options.fetcher !== 'function') {
      throw new Error('AudioPlaybackController requires a fetcher');
    }
    this.audio = audioElement;
    this.callbacks = callbacks;
    this.fetcher = options.fetcher;
    this.requestId = 0;
    this.pendingKey = null;
    this.pendingPromise = null;
    this.lastKey = null;
    this.lastMeta = null;
    this.suppressPause = false;

    this.audio.addEventListener('playing', () => {
      if (this.lastMeta && !this.suppressPause) {
        this.callbacks.onPlaying?.(this.lastMeta);
      }
    });
    this.audio.addEventListener('ended', () => {
      if (this.lastMeta) {
        this.callbacks.onEnded?.(this.lastMeta);
      }
    });
    this.audio.addEventListener('error', () => {
      if (!this.audio.src || !this.lastMeta) {
        return;
      }
      this.callbacks.onPlaybackError?.(
        new Error('音频播放失败，请点击“重播”再试。'),
        this.lastMeta,
      );
    });
  }

  play(keyText, accent = 'auto') {
    const key = `${keyText.toLowerCase()}|${accent}`;
    if (this.pendingKey === key && this.pendingPromise) {
      return this.pendingPromise;
    }
    if (this.lastKey === key && this.lastMeta && this.audio.src) {
      this.callbacks.onMeta?.(this.lastMeta);
      this.audio.currentTime = 0;
      return this._play(this.lastMeta, this.requestId);
    }

    const requestId = ++this.requestId;
    this.pendingKey = key;
    this.lastKey = null;
    this.lastMeta = null;
    this._pauseCurrent();
    this.callbacks.onLoading?.({ word: keyText, accent });

    const promise = (async () => {
      try {
        const metadata = await this.fetcher(keyText, accent);
        if (requestId !== this.requestId) {
          return;
        }
        this.lastKey = key;
        this.lastMeta = metadata;
        this.callbacks.onMeta?.(metadata);
        this.audio.src = metadata.audio_url;
        this.audio.load();
        await this._play(metadata, requestId);
      } catch (error) {
        if (requestId !== this.requestId) {
          return;
        }
        this.callbacks.onFetchError?.(error, keyText, accent);
      } finally {
        if (requestId === this.requestId) {
          this.pendingKey = null;
          this.pendingPromise = null;
        }
      }
    })();
    this.pendingPromise = promise;
    return promise;
  }

  async _play(metadata, requestId) {
    try {
      await this.audio.play();
    } catch (error) {
      if (requestId !== this.requestId) {
        return;
      }
      if (error?.name === 'NotAllowedError') {
        this.callbacks.onAutoplayBlocked?.(metadata);
      } else {
        this.callbacks.onPlaybackError?.(error, metadata);
      }
    }
  }

  replay() {
    if (!this.lastMeta || !this.audio.src) {
      return;
    }
    this.audio.currentTime = 0;
    void this._play(this.lastMeta, this.requestId);
  }

  stop() {
    this.requestId += 1;
    this.pendingKey = null;
    this.pendingPromise = null;
    this.lastKey = null;
    this.lastMeta = null;
    this.suppressPause = true;
    this.audio.pause();
    this.audio.removeAttribute('src');
    this.audio.load();
    this.suppressPause = false;
  }

  _pauseCurrent() {
    this.suppressPause = true;
    this.audio.pause();
    this.audio.currentTime = 0;
    this.suppressPause = false;
  }
}
