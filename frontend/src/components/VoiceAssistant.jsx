import { useEffect, useRef, useState } from "react";
import { useAudioRecorder } from "../hooks/useAudioRecorder";
import { StreamingAudioPlayer } from "../audio/streamingPlayer";
import { VoiceWsClient } from "../services/voiceWsClient";

export default function VoiceAssistant() {
  const [messages, setMessages] = useState([]);
  const [status, setStatus] = useState("idle"); // idle | recording | processing | speaking
  const [error, setError] = useState(null);
  const { isRecording, startRecording, stopRecording } = useAudioRecorder();
  const messagesEndRef = useRef(null);

  const wsRef = useRef(null);
  const playerRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    return () => {
      wsRef.current?.close();
      playerRef.current?.stop();
    };
  }, []);

  const ensureClient = async () => {
    if (wsRef.current && wsRef.current.ws?.readyState === WebSocket.OPEN) return wsRef.current;
    const client = new VoiceWsClient({ streaming: true });

    const player = playerRef.current || new StreamingAudioPlayer();
    playerRef.current = player;

    client.on("transcript", (msg) => {
      if (msg.text) setMessages((prev) => [...prev, { role: "user", text: msg.text }]);
    });
    client.on("llm_delta", (msg) => {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last && last.role === "assistant" && last.streaming) {
          const updated = { ...last, text: last.text + msg.delta };
          return [...prev.slice(0, -1), updated];
        }
        return [...prev, { role: "assistant", text: msg.delta, streaming: true }];
      });
    });
    client.on("response", (msg) => {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last && last.role === "assistant" && last.streaming) {
          const updated = { ...last, text: msg.text, streaming: false };
          return [...prev.slice(0, -1), updated];
        }
        return [...prev, { role: "assistant", text: msg.text }];
      });
    });
    client.on("tts_chunk", async (msg) => {
      if (status !== "speaking") setStatus("speaking");
      try {
        await player.enqueue(msg.audio);
      } catch (e) {
        setError(`Audio decode failed: ${e.message}`);
      }
    });
    client.on("tts_end", () => {
      player.onEnd(() => setStatus("idle"));
      player.markEnd();
    });
    client.on("audio", async (msg) => {
      if (status !== "speaking") setStatus("speaking");
      try {
        await player.enqueue(msg.data);
        player.onEnd(() => setStatus("idle"));
        player.markEnd();
      } catch (e) {
        setError(`Audio decode failed: ${e.message}`);
      }
    });
    client.on("cancelled", () => {
      player.stop();
      setStatus("idle");
    });
    client.on("error", (msg) => setError(msg.message || "Server error"));
    client.on("close", () => {
      wsRef.current = null;
    });

    await client.connect();
    wsRef.current = client;
    return client;
  };

  const handleMicClick = async () => {
    setError(null);

    // Manual barge-in: click while assistant is speaking -> stop playback + server cancel.
    if (status === "speaking") {
      playerRef.current?.stop();
      wsRef.current?.bargeIn();
      setStatus("idle");
      return;
    }

    if (isRecording) {
      setStatus("processing");
      try {
        const audioBlob = await stopRecording();
        if (!audioBlob) {
          setStatus("idle");
          return;
        }
        const client = await ensureClient();
        playerRef.current?.reset();
        await client.sendAudio(audioBlob);
      } catch (err) {
        setError(err.message);
        setStatus("idle");
      }
      return;
    }

    try {
      await ensureClient();
      await startRecording();
      setStatus("recording");
    } catch (err) {
      setError(err.message);
      setStatus("idle");
    }
  };

  const clearChat = () => {
    setMessages([]);
    setError(null);
    wsRef.current?.clearHistory();
    playerRef.current?.stop();
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
          disabled={status === "processing"}
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
          <span>Qwen2.5 / Groq</span>
          <span>Kokoro TTS</span>
          <span>streaming</span>
        </div>
        <p>100% Free — No API costs</p>
      </footer>
    </div>
  );
}
