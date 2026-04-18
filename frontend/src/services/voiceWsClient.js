const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function blobToBase64(blob) {
  const buf = await blob.arrayBuffer();
  const bytes = new Uint8Array(buf);
  let binary = "";
  const CHUNK = 0x8000;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
  }
  return btoa(binary);
}

export class VoiceWsClient {
  constructor({ streaming = true } = {}) {
    const wsBase = API_BASE.replace(/^http/, "ws");
    this.url = `${wsBase}/ws/voice${streaming ? "?stream=1" : ""}`;
    this.ws = null;
    this._handlers = new Map();
  }

  connect() {
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(this.url);
      ws.onopen = () => resolve();
      ws.onerror = (e) => reject(e);
      ws.onclose = () => this._emit("close", {});
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          this._emit(msg.type, msg);
        } catch {
          // ignore malformed
        }
      };
      this.ws = ws;
    });
  }

  on(type, fn) {
    this._handlers.set(type, fn);
    return this;
  }

  _emit(type, msg) {
    const fn = this._handlers.get(type);
    if (fn) fn(msg);
  }

  async sendAudio(blob) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error("WebSocket not open");
    }
    const data = await blobToBase64(blob);
    this.ws.send(JSON.stringify({ type: "audio", data }));
  }

  clearHistory() {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "clear_history" }));
    }
  }

  bargeIn() {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "barge_in" }));
    }
  }

  close() {
    if (this.ws) this.ws.close();
    this.ws = null;
  }
}
