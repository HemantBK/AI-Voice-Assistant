/**
 * Lightweight client-side VAD for barge-in (B.5). Uses RMS energy with a
 * short hold/release window. Deliberately not Silero — a 2 MB ONNX model
 * in the browser is overkill for "did the user start talking".
 *
 * Feed float32 samples via `push(frame)`; listen for `onSpeechStart`.
 * Designed to run during TTS playback to detect barge-in; once fired,
 * caller should stop audio and cancel the in-flight turn.
 */
export class EnergyVad {
  constructor({ sampleRate = 16000, thresholdDb = -40, holdMs = 80, onSpeechStart } = {}) {
    this.sampleRate = sampleRate;
    this.threshold = 10 ** (thresholdDb / 20); // dBFS to linear
    this.holdSamples = Math.round((holdMs / 1000) * sampleRate);
    this._active = 0;
    this._fired = false;
    this.onSpeechStart = onSpeechStart;
  }

  push(frame) {
    if (this._fired) return;
    let sumSq = 0;
    for (let i = 0; i < frame.length; i++) sumSq += frame[i] * frame[i];
    const rms = Math.sqrt(sumSq / frame.length);
    if (rms >= this.threshold) {
      this._active += frame.length;
      if (this._active >= this.holdSamples) {
        this._fired = true;
        this.onSpeechStart?.();
      }
    } else {
      this._active = Math.max(0, this._active - frame.length);
    }
  }

  reset() {
    this._active = 0;
    this._fired = false;
  }
}
