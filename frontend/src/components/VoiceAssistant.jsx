import { useState, useRef, useEffect } from "react";
import { useAudioRecorder } from "../hooks/useAudioRecorder";
import { sendAudioPipeline, playBase64Audio } from "../services/api";

export default function VoiceAssistant() {
  const [messages, setMessages] = useState([]);
  const [status, setStatus] = useState("idle"); // idle | recording | processing | speaking
  const [error, setError] = useState(null);
  const { isRecording, startRecording, stopRecording } = useAudioRecorder();
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleMicClick = async () => {
    setError(null);

    if (isRecording) {
      // Stop recording and process
      setStatus("processing");
      try {
        const audioBlob = await stopRecording();
        if (!audioBlob) return;

        const result = await sendAudioPipeline(audioBlob);

        if (result.transcript) {
          setMessages((prev) => [
            ...prev,
            { role: "user", text: result.transcript },
            { role: "assistant", text: result.response },
          ]);
        }

        // Play the response audio
        if (result.audio) {
          setStatus("speaking");
          await playBase64Audio(result.audio);
        }
      } catch (err) {
        setError(err.message);
      } finally {
        setStatus("idle");
      }
    } else {
      // Start recording
      try {
        await startRecording();
        setStatus("recording");
      } catch (err) {
        setError(err.message);
        setStatus("idle");
      }
    }
  };

  const clearChat = () => {
    setMessages([]);
    setError(null);
  };

  const statusText = {
    idle: "Click to speak",
    recording: "Listening... Click to stop",
    processing: "Thinking...",
    speaking: "Speaking...",
  };

  return (
    <div className="assistant-container">
      <header className="assistant-header">
        <h1>AI Voice Assistant</h1>
        <p className="subtitle">Speak naturally — powered by free & open-source AI</p>
      </header>

      <div className="chat-window">
        {messages.length === 0 && (
          <div className="empty-state">
            <div className="empty-icon">🎙️</div>
            <p>Press the microphone and start talking</p>
            <p className="hint">Your conversation will appear here</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            <div className="message-avatar">
              {msg.role === "user" ? "🧑" : "🤖"}
            </div>
            <div className="message-bubble">
              <p>{msg.text}</p>
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {error && (
        <div className="error-banner">
          <span>⚠️ {error}</span>
          <button onClick={() => setError(null)}>✕</button>
        </div>
      )}

      <div className="controls">
        <button
          className={`mic-button ${status}`}
          onClick={handleMicClick}
          disabled={status === "processing" || status === "speaking"}
        >
          <span className="mic-icon">
            {status === "recording" ? "⏹️" : status === "processing" ? "⏳" : status === "speaking" ? "🔊" : "🎙️"}
          </span>
        </button>
        <p className="status-text">{statusText[status]}</p>

        {messages.length > 0 && (
          <button className="clear-button" onClick={clearChat}>
            Clear Chat
          </button>
        )}
      </div>

      <footer className="assistant-footer">
        <div className="tech-stack">
          <span>Faster-Whisper</span>
          <span>Groq / Llama 3.3</span>
          <span>Kokoro TTS</span>
        </div>
        <p>100% Free — No API costs</p>
      </footer>
    </div>
  );
}
