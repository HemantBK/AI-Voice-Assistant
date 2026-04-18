/**
 * Continuous microphone capture for B.4. Produces 20 ms PCM16 mono frames at
 * 16 kHz and delivers them via `onFrame(Int16Array)`. Uses an AudioWorklet so
 * the downsampling runs off the main thread.
 */
export class MicrophoneStream {
  constructor({ onFrame, workletUrl = "/recorder-worklet.js" } = {}) {
    this.onFrame = onFrame;
    this.workletUrl = workletUrl;
    this._ctx = null;
    this._node = null;
    this._source = null;
    this._mediaStream = null;
  }

  async start() {
    if (this._ctx) return;
    const Ctx = window.AudioContext || window.webkitAudioContext;
    const ctx = new Ctx();
    await ctx.audioWorklet.addModule(this.workletUrl);
    const media = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
    const source = ctx.createMediaStreamSource(media);
    const node = new AudioWorkletNode(ctx, "recorder-16k", {
      processorOptions: { targetRate: 16000 },
    });
    node.port.onmessage = (ev) => {
      const frame = new Int16Array(ev.data);
      this.onFrame?.(frame);
    };
    source.connect(node);
    // Do not connect to destination (we don't want to hear our own mic).
    this._ctx = ctx;
    this._node = node;
    this._source = source;
    this._mediaStream = media;
  }

  async stop() {
    try { this._node?.port.postMessage("stop"); } catch { /* noop */ }
    try { this._source?.disconnect(); } catch { /* noop */ }
    try { this._node?.disconnect(); } catch { /* noop */ }
    this._mediaStream?.getTracks().forEach((t) => t.stop());
    if (this._ctx && this._ctx.state !== "closed") {
      try { await this._ctx.close(); } catch { /* noop */ }
    }
    this._ctx = null;
    this._node = null;
    this._source = null;
    this._mediaStream = null;
  }
}

/** Pack an Int16Array to base64 for WS transport. */
export function int16ToBase64(int16) {
  const bytes = new Uint8Array(int16.buffer, int16.byteOffset, int16.byteLength);
  let binary = "";
  const CHUNK = 0x8000;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
  }
  return btoa(binary);
}
