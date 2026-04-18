/**
 * Gapless playback of a sequence of base64-encoded audio blobs (e.g. per-sentence
 * WAVs emitted by the streaming TTS path). Each call to `enqueue` schedules
 * the chunk to start exactly when the previous one finishes, so there is no
 * audible gap between sentences.
 *
 * `stop()` cancels all pending sources immediately — used for barge-in in B.5.
 */
export class StreamingAudioPlayer {
  constructor() {
    this._ctx = null;
    this._nextStartAt = 0;
    this._sources = new Set();
    this._pending = 0;
    this._firstChunkAt = null;
    this._onFirstChunk = null;
    this._onEnd = null;
    this._awaitingEnd = false;
  }

  _ctxOrCreate() {
    if (!this._ctx) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      this._ctx = new Ctx();
      this._nextStartAt = this._ctx.currentTime;
    }
    return this._ctx;
  }

  async enqueue(base64Audio) {
    const ctx = this._ctxOrCreate();
    if (ctx.state === "suspended") {
      try {
        await ctx.resume();
      } catch {
        // autoplay policy may still block; caller is expected to invoke from a user gesture
      }
    }

    const bin = atob(base64Audio);
    const buf = new ArrayBuffer(bin.length);
    const view = new Uint8Array(buf);
    for (let i = 0; i < bin.length; i++) view[i] = bin.charCodeAt(i);

    const audioBuffer = await ctx.decodeAudioData(buf);
    const startAt = Math.max(this._nextStartAt, ctx.currentTime);
    const source = ctx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(ctx.destination);
    source.start(startAt);
    this._nextStartAt = startAt + audioBuffer.duration;
    this._sources.add(source);
    this._pending += 1;

    if (this._firstChunkAt === null) {
      this._firstChunkAt = performance.now();
      if (this._onFirstChunk) this._onFirstChunk();
    }

    source.onended = () => {
      this._sources.delete(source);
      this._pending -= 1;
      if (this._pending === 0 && this._awaitingEnd && this._onEnd) {
        this._awaitingEnd = false;
        this._onEnd();
      }
    };

    return { scheduledAt: startAt, duration: audioBuffer.duration };
  }

  /** Call after the last chunk has been enqueued; fires `onEnd` when playback drains. */
  markEnd() {
    if (this._pending === 0) {
      if (this._onEnd) this._onEnd();
    } else {
      this._awaitingEnd = true;
    }
  }

  stop() {
    for (const s of this._sources) {
      try { s.stop(); } catch { /* already stopped */ }
    }
    this._sources.clear();
    this._pending = 0;
    this._awaitingEnd = false;
    if (this._ctx) this._nextStartAt = this._ctx.currentTime;
  }

  onFirstChunk(fn) { this._onFirstChunk = fn; }
  onEnd(fn) { this._onEnd = fn; }
  reset() {
    this.stop();
    this._firstChunkAt = null;
  }
  get firstChunkAt() { return this._firstChunkAt; }
}
