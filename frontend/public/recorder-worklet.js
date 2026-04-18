// AudioWorkletProcessor running on the audio thread.
// Downsamples the microphone input (browsers typically give 48 kHz) to
// 16 kHz mono PCM16 frames of ~20 ms (320 samples) and posts them to the
// main thread as ArrayBuffers. The main thread batches/encodes and pushes
// over the WebSocket.
class Recorder16k extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const opts = (options && options.processorOptions) || {};
    this.targetRate = opts.targetRate || 16000;
    this.frameSamples = Math.round(this.targetRate * 0.02); // 20 ms
    this.inputRate = sampleRate; // AudioWorkletGlobalScope global
    this.ratio = this.inputRate / this.targetRate;
    this._acc = 0;
    this._buf = new Int16Array(this.frameSamples);
    this._bufIdx = 0;
    this._running = true;
    this.port.onmessage = (ev) => {
      if (ev.data === "stop") this._running = false;
    };
  }

  process(inputs) {
    if (!this._running) return false;
    const input = inputs[0];
    if (!input || input.length === 0) return true;
    const ch0 = input[0];
    if (!ch0) return true;

    // Nearest-neighbor downsample (cheap, good enough for 48k->16k; anti-alias not done on-thread).
    for (let i = 0; i < ch0.length; i++) {
      this._acc += 1;
      if (this._acc >= this.ratio) {
        this._acc -= this.ratio;
        // clamp + convert float32 (-1..1) to int16
        let s = ch0[i];
        if (s > 1) s = 1; else if (s < -1) s = -1;
        this._buf[this._bufIdx++] = s < 0 ? s * 0x8000 : s * 0x7fff;
        if (this._bufIdx >= this.frameSamples) {
          // transfer the buffer; allocate a fresh one
          this.port.postMessage(this._buf.buffer, [this._buf.buffer]);
          this._buf = new Int16Array(this.frameSamples);
          this._bufIdx = 0;
        }
      }
    }
    return true;
  }
}

registerProcessor("recorder-16k", Recorder16k);
