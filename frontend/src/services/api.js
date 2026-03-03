const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function sendAudioPipeline(audioBlob) {
  const formData = new FormData();
  formData.append("audio", audioBlob, "recording.wav");

  const response = await fetch(`${API_BASE}/api/pipeline`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Pipeline request failed");
  }

  return response.json();
}

export async function sendChatMessage(message, conversationHistory = []) {
  const response = await fetch(`${API_BASE}/api/chat/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_history: conversationHistory }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Chat request failed");
  }

  return response.json();
}

export function createWebSocket() {
  const wsUrl = API_BASE.replace(/^http/, "ws");
  return new WebSocket(`${wsUrl}/ws/voice`);
}

export function playBase64Audio(base64Audio) {
  return new Promise((resolve, reject) => {
    const audioData = atob(base64Audio);
    const arrayBuffer = new ArrayBuffer(audioData.length);
    const view = new Uint8Array(arrayBuffer);
    for (let i = 0; i < audioData.length; i++) {
      view[i] = audioData.charCodeAt(i);
    }

    const blob = new Blob([arrayBuffer], { type: "audio/wav" });
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);

    audio.onended = () => {
      URL.revokeObjectURL(url);
      resolve();
    };
    audio.onerror = (e) => {
      URL.revokeObjectURL(url);
      reject(e);
    };

    audio.play().catch(reject);
  });
}
