import { useState } from "react";

const categories = [
  {
    id: "stt",
    icon: "🎙️",
    title: "Speech-to-Text (STT)",
    color: "#FF6B35",
    tools: [
      {
        name: "Faster-Whisper",
        desc: "4× faster than OpenAI Whisper, 7.75% WER, 99+ languages. Uses CTranslate2 optimization.",
        install: "pip install faster-whisper",
        license: "MIT",
        link: "github.com/SYSTRAN/faster-whisper",
        note: "Best overall choice — fast, accurate, easy to use",
      },
      {
        name: "Whisper (OpenAI)",
        desc: "Original model. Large-v3 Turbo is fastest variant. Great multilingual support.",
        install: "pip install openai-whisper",
        license: "MIT",
        link: "github.com/openai/whisper",
        note: "Use Faster-Whisper wrapper for better performance",
      },
      {
        name: "Vosk",
        desc: "Lightweight offline STT. Runs on CPU, models as small as 50MB. Real-time streaming.",
        install: "pip install vosk",
        license: "Apache 2.0",
        link: "alphacephei.com/vosk",
        note: "Best for real-time streaming on low-end hardware",
      },
      {
        name: "IBM Granite Speech 3.3",
        desc: "IBM's own STT model — 5.85% WER. Shows IBM ecosystem knowledge in interviews.",
        install: "pip install transformers",
        license: "Apache 2.0",
        link: "huggingface.co/ibm-granite",
        note: "⭐ Use this to impress IBM recruiters!",
      },
    ],
  },
  {
    id: "tts",
    icon: "🔊",
    title: "Text-to-Speech (TTS)",
    color: "#4ECDC4",
    tools: [
      {
        name: "Kokoro TTS",
        desc: "82M params, <0.3s latency, 210× real-time on GPU. Highest-ranked open-weight on TTS Arena.",
        install: "pip install kokoro",
        license: "Apache 2.0",
        link: "huggingface.co/hexgrad/Kokoro-82M",
        note: "Best speed-to-quality ratio for voice assistants",
      },
      {
        name: "Chatterbox (Resemble AI)",
        desc: "Voice cloning from 5-10s clips. Beats ElevenLabs in blind tests. Emotion control.",
        install: "pip install chatterbox-tts",
        license: "MIT",
        link: "github.com/resemble-ai/chatterbox",
        note: "Best for voice cloning demo feature",
      },
      {
        name: "Piper TTS",
        desc: "Ultra-fast, runs on Raspberry Pi. Great for edge deployment demos.",
        install: "pip install piper-tts",
        license: "MIT",
        link: "github.com/rhasspy/piper",
        note: "Lightest option — works even on ARM/CPU-only",
      },
      {
        name: "StyleTTS 2",
        desc: "Style transfer TTS. 0.1s latency, 95× real-time. Human-level quality on LJSpeech.",
        install: "git clone + pip install",
        license: "MIT",
        link: "github.com/yl4579/StyleTTS2",
        note: "Best naturalness for single-speaker use",
      },
    ],
  },
  {
    id: "llm",
    icon: "🧠",
    title: "AI / LLM Backend",
    color: "#A855F7",
    tools: [
      {
        name: "Groq API (Free Tier)",
        desc: "~80ms time-to-first-token. Llama 3.3 70B. 14,400 req/day free. No credit card needed.",
        install: "pip install groq",
        license: "Free tier",
        link: "console.groq.com",
        note: "⭐ Fastest free LLM API — perfect for voice assistant",
      },
      {
        name: "OpenRouter (Free Models)",
        desc: "30+ free models via one API. Llama, Mistral, Gemma all available free.",
        install: "pip install openai  # compatible API",
        license: "Free tier",
        link: "openrouter.ai",
        note: "Great fallback — switch models without code changes",
      },
      {
        name: "Ollama (Local)",
        desc: "Run LLMs locally. Llama 3.2 3B, Gemma 2B, Phi-3. No API key needed.",
        install: "curl -fsSL https://ollama.com/install.sh | sh",
        license: "MIT",
        link: "ollama.com",
        note: "Best for local dev — no internet dependency",
      },
      {
        name: "Hugging Face Inference API",
        desc: "Free serverless inference for open models. Rate-limited but works well for demos.",
        install: "pip install huggingface_hub",
        license: "Free tier",
        link: "huggingface.co/inference-api",
        note: "Good for lightweight model serving",
      },
    ],
  },
  {
    id: "frontend",
    icon: "🖥️",
    title: "Frontend & Backend",
    color: "#F59E0B",
    tools: [
      {
        name: "React + Vite",
        desc: "Fast dev server, hot reload. Build the voice UI with audio recording/playback.",
        install: "npm create vite@latest -- --template react",
        license: "MIT",
        link: "vitejs.dev",
        note: "Matches IBM's React/JS requirement perfectly",
      },
      {
        name: "FastAPI",
        desc: "Async Python backend. Native WebSocket support, auto-generated API docs at /docs.",
        install: "pip install fastapi uvicorn",
        license: "MIT",
        link: "fastapi.tiangolo.com",
        note: "Better than Flask for real-time voice streaming",
      },
      {
        name: "@ricky0123/vad-react",
        desc: "Voice Activity Detection in browser. Silero VAD via ONNX Runtime. Auto-segments speech.",
        install: "npm install @ricky0123/vad-react",
        license: "MIT",
        link: "github.com/ricky0123/vad",
        note: "Essential for natural turn-taking in voice UI",
      },
      {
        name: "Gradio",
        desc: "Quick ML demo UIs. Direct HuggingFace Spaces integration. Great for rapid prototyping.",
        install: "pip install gradio",
        license: "Apache 2.0",
        link: "gradio.app",
        note: "Fastest way to get a working demo live",
      },
    ],
  },
  {
    id: "deploy",
    icon: "🚀",
    title: "Free Deployment",
    color: "#10B981",
    tools: [
      {
        name: "Hugging Face Spaces",
        desc: "Free CPU (2 vCPU, 16GB RAM). ZeroGPU gives free H200 access. Gradio/Docker support.",
        install: "git push to HF Space repo",
        license: "Free (no card)",
        link: "huggingface.co/spaces",
        note: "⭐ #1 choice — free GPU via ZeroGPU, no card needed",
      },
      {
        name: "Vercel",
        desc: "Free React frontend hosting. Auto-deploy from GitHub. Custom domains. Global CDN.",
        install: "npx vercel",
        license: "Free (no card)",
        link: "vercel.com",
        note: "Best for hosting the React frontend separately",
      },
      {
        name: "Render",
        desc: "Free web services tier. Supports Docker, Python, Node. Auto-deploy from Git.",
        install: "Connect GitHub repo",
        license: "Free (no card)",
        link: "render.com",
        note: "Good alternative for backend hosting",
      },
      {
        name: "Railway",
        desc: "$5 free credit on signup, no card. Deploy FastAPI + Docker. Quick provisioning.",
        install: "railway init",
        license: "Free $5 credit",
        link: "railway.com",
        note: "Easy backend deploy with free starter credits",
      },
    ],
  },
  {
    id: "mlops",
    icon: "⚙️",
    title: "MLOps & DevOps",
    color: "#EF4444",
    tools: [
      {
        name: "MLflow",
        desc: "Track experiments, log WER/MOS metrics, register models. Runs locally or on HF Spaces.",
        install: "pip install mlflow",
        license: "Apache 2.0",
        link: "mlflow.org",
        note: "IBM lists MLOps experience — this checks that box",
      },
      {
        name: "GitHub Actions",
        desc: "Free CI/CD for public repos. Run tests, lint, build Docker, auto-deploy.",
        install: "Add .github/workflows/ci.yml",
        license: "Free (public repos)",
        link: "github.com/features/actions",
        note: "2,000 free mins/month for private repos too",
      },
      {
        name: "Docker",
        desc: "Containerize everything. Docker Compose for multi-service local dev. Free Desktop.",
        install: "apt install docker.io",
        license: "Apache 2.0",
        link: "docker.com",
        note: "IBM explicitly requires Docker experience",
      },
      {
        name: "DVC (Data Version Control)",
        desc: "Git for datasets. Track audio files, model weights. Free with any Git remote.",
        install: "pip install dvc",
        license: "Apache 2.0",
        link: "dvc.org",
        note: "Shows mature data engineering practices",
      },
    ],
  },
  {
    id: "data",
    icon: "📊",
    title: "Free Datasets",
    color: "#6366F1",
    tools: [
      {
        name: "LibriSpeech",
        desc: "1,000 hours of English read speech. The gold standard STT benchmark dataset.",
        install: "huggingface: openslr/librispeech_asr",
        license: "CC BY 4.0",
        link: "openslr.org/12",
        note: "Must-use for STT evaluation and fine-tuning",
      },
      {
        name: "Mozilla Common Voice",
        desc: "28,000+ hours across 112 languages. Community-contributed. Great for diversity.",
        install: "huggingface: mozilla-foundation/common_voice_17_0",
        license: "CC-0",
        link: "commonvoice.mozilla.org",
        note: "Best multilingual dataset — shows inclusive AI",
      },
      {
        name: "LJSpeech",
        desc: "24 hours, single female speaker. Professional quality. Standard TTS training set.",
        install: "huggingface: keithito/lj_speech",
        license: "Public Domain",
        link: "keithito.com/LJ-Speech-Dataset",
        note: "Start TTS fine-tuning here",
      },
      {
        name: "VCTK Corpus",
        desc: "44 hours, 110 speakers with diverse accents. Multi-speaker TTS training.",
        install: "huggingface: CSTR-Edinburgh/vctk",
        license: "CC BY 4.0",
        link: "datashare.ed.ac.uk/handle/10283/3443",
        note: "Shows accent/diversity awareness in your project",
      },
    ],
  },
  {
    id: "gpu",
    icon: "💻",
    title: "Free GPU for Training",
    color: "#EC4899",
    tools: [
      {
        name: "Google Colab",
        desc: "Free T4 GPU (15GB VRAM). Jupyter notebooks. ~4-12 hrs/session. No card needed.",
        install: "colab.research.google.com",
        license: "Free",
        link: "colab.research.google.com",
        note: "⭐ Best free GPU for training & experimentation",
      },
      {
        name: "Kaggle Notebooks",
        desc: "Free P100 GPU (16GB) or 2× T4. 30 hrs/week GPU quota. Great datasets built-in.",
        install: "kaggle.com/code",
        license: "Free",
        link: "kaggle.com",
        note: "More GPU hours than Colab — use for longer training",
      },
      {
        name: "Lightning AI Studios",
        desc: "Free tier with GPU access. VS Code in browser. 15GB storage. Good for prototyping.",
        install: "lightning.ai",
        license: "Free tier",
        link: "lightning.ai",
        note: "Full IDE in browser with free GPU",
      },
      {
        name: "HF ZeroGPU",
        desc: "Free H200 GPU slices for Gradio Spaces. Dynamic allocation — GPU only during inference.",
        install: "@spaces.GPU decorator",
        license: "Free",
        link: "huggingface.co/docs/hub/spaces-zerogpu",
        note: "Free H200 access for deployed demos!",
      },
    ],
  },
];

const architectureSteps = [
  { step: "1", label: "User speaks", tool: "Browser + VAD", color: "#FF6B35" },
  { step: "2", label: "Audio → Text", tool: "Faster-Whisper", color: "#FF6B35" },
  { step: "3", label: "Text → AI Response", tool: "Groq (Llama 3.3)", color: "#A855F7" },
  { step: "4", label: "Response → Speech", tool: "Kokoro TTS", color: "#4ECDC4" },
  { step: "5", label: "Audio playback", tool: "Browser MediaSource", color: "#F59E0B" },
];

export default function FreeToolkit() {
  const [activeCategory, setActiveCategory] = useState("stt");
  const [expandedTool, setExpandedTool] = useState(null);

  const active = categories.find((c) => c.id === activeCategory);

  return (
    <div style={{
      minHeight: "100vh",
      background: "#0A0A0F",
      color: "#E8E6E3",
      fontFamily: "'Segoe UI', -apple-system, sans-serif",
      padding: "24px 16px",
    }}>
      {/* Header */}
      <div style={{ textAlign: "center", marginBottom: 32 }}>
        <div style={{
          display: "inline-block",
          background: "linear-gradient(135deg, #FF6B35 0%, #A855F7 50%, #4ECDC4 100%)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          fontSize: 28,
          fontWeight: 800,
          letterSpacing: "-0.5px",
          lineHeight: 1.2,
        }}>
          AI Voice Assistant
        </div>
        <div style={{ fontSize: 14, color: "#888", marginTop: 6 }}>
          100% Free Toolkit — No Credit Card Needed
        </div>
        <div style={{
          marginTop: 16,
          padding: "10px 16px",
          background: "rgba(168,85,247,0.1)",
          border: "1px solid rgba(168,85,247,0.25)",
          borderRadius: 8,
          fontSize: 12,
          color: "#C4A8FF",
          maxWidth: 500,
          margin: "16px auto 0",
        }}>
          Every tool below is completely free and works without a credit card. Build, train, deploy, and showcase your entire project at zero cost.
        </div>
      </div>

      {/* Pipeline visualization */}
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 4,
        marginBottom: 32,
        flexWrap: "wrap",
        padding: "0 8px",
      }}>
        {architectureSteps.map((s, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <div style={{
              background: `${s.color}18`,
              border: `1px solid ${s.color}40`,
              borderRadius: 8,
              padding: "8px 12px",
              textAlign: "center",
              minWidth: 90,
            }}>
              <div style={{ fontSize: 10, color: s.color, fontWeight: 700, marginBottom: 2 }}>
                STEP {s.step}
              </div>
              <div style={{ fontSize: 11, fontWeight: 600, color: "#E8E6E3" }}>{s.label}</div>
              <div style={{ fontSize: 10, color: "#888", marginTop: 2 }}>{s.tool}</div>
            </div>
            {i < architectureSteps.length - 1 && (
              <span style={{ color: "#444", fontSize: 16 }}>→</span>
            )}
          </div>
        ))}
      </div>

      {/* Category tabs */}
      <div style={{
        display: "flex",
        gap: 6,
        flexWrap: "wrap",
        justifyContent: "center",
        marginBottom: 24,
        padding: "0 4px",
      }}>
        {categories.map((cat) => (
          <button
            key={cat.id}
            onClick={() => { setActiveCategory(cat.id); setExpandedTool(null); }}
            style={{
              padding: "8px 14px",
              borderRadius: 20,
              border: activeCategory === cat.id
                ? `2px solid ${cat.color}`
                : "1px solid #2A2A35",
              background: activeCategory === cat.id ? `${cat.color}18` : "#14141C",
              color: activeCategory === cat.id ? cat.color : "#888",
              fontSize: 12,
              fontWeight: 600,
              cursor: "pointer",
              transition: "all 0.2s",
              whiteSpace: "nowrap",
            }}
          >
            {cat.icon} {cat.title}
          </button>
        ))}
      </div>

      {/* Active category tools */}
      {active && (
        <div style={{ maxWidth: 700, margin: "0 auto" }}>
          <div style={{
            display: "grid",
            gap: 12,
          }}>
            {active.tools.map((tool, i) => {
              const isExpanded = expandedTool === `${active.id}-${i}`;
              return (
                <div
                  key={i}
                  onClick={() => setExpandedTool(isExpanded ? null : `${active.id}-${i}`)}
                  style={{
                    background: "#14141C",
                    border: `1px solid ${isExpanded ? active.color + "60" : "#2A2A35"}`,
                    borderRadius: 12,
                    padding: 16,
                    cursor: "pointer",
                    transition: "all 0.2s",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                        <span style={{ fontSize: 16, fontWeight: 700, color: "#fff" }}>{tool.name}</span>
                        <span style={{
                          fontSize: 10,
                          padding: "2px 8px",
                          borderRadius: 10,
                          background: "#10B98120",
                          color: "#10B981",
                          fontWeight: 600,
                        }}>
                          {tool.license}
                        </span>
                        {tool.note?.includes("⭐") && (
                          <span style={{
                            fontSize: 10,
                            padding: "2px 8px",
                            borderRadius: 10,
                            background: "#F59E0B20",
                            color: "#F59E0B",
                            fontWeight: 600,
                          }}>
                            RECOMMENDED
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: 13, color: "#999", marginTop: 6, lineHeight: 1.5 }}>
                        {tool.desc}
                      </div>
                    </div>
                    <span style={{
                      color: "#555",
                      fontSize: 18,
                      transform: isExpanded ? "rotate(180deg)" : "rotate(0deg)",
                      transition: "transform 0.2s",
                      marginLeft: 8,
                      flexShrink: 0,
                    }}>
                      ▾
                    </span>
                  </div>

                  {isExpanded && (
                    <div style={{ marginTop: 14, paddingTop: 14, borderTop: "1px solid #2A2A35" }}>
                      <div style={{
                        background: "#0D0D12",
                        borderRadius: 8,
                        padding: "10px 14px",
                        fontFamily: "'Fira Code', 'Consolas', monospace",
                        fontSize: 12,
                        color: active.color,
                        marginBottom: 10,
                        overflowX: "auto",
                        whiteSpace: "nowrap",
                      }}>
                        $ {tool.install}
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
                        <span style={{ fontSize: 12, color: "#6B7280" }}>
                          🔗 {tool.link}
                        </span>
                        <span style={{
                          fontSize: 11,
                          color: tool.note?.includes("⭐") ? "#F59E0B" : "#6B7280",
                          fontStyle: "italic",
                        }}>
                          {tool.note}
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Deployment strategy summary */}
      <div style={{
        maxWidth: 700,
        margin: "32px auto 0",
        background: "#14141C",
        border: "1px solid #2A2A35",
        borderRadius: 12,
        padding: 20,
      }}>
        <div style={{ fontSize: 16, fontWeight: 700, color: "#fff", marginBottom: 12 }}>
          🎯 Recommended Free Deployment Strategy
        </div>
        <div style={{ display: "grid", gap: 10 }}>
          {[
            { label: "Backend (STT + TTS + LLM)", value: "Hugging Face Spaces (ZeroGPU) — free H200 GPU, Gradio UI, Docker support", color: "#10B981" },
            { label: "Frontend (React app)", value: "Vercel — auto-deploy from GitHub, free SSL, global CDN", color: "#F59E0B" },
            { label: "LLM API", value: "Groq Free Tier — 14,400 req/day, Llama 3.3 70B, no card required", color: "#A855F7" },
            { label: "Model Training", value: "Google Colab (T4) + Kaggle (P100) — combined ~40+ GPU hours/week free", color: "#EC4899" },
            { label: "CI/CD", value: "GitHub Actions — free for public repos, auto-test + deploy on push", color: "#EF4444" },
            { label: "Experiment Tracking", value: "MLflow on Colab/local — log all WER, MOS, latency metrics", color: "#6366F1" },
          ].map((item, i) => (
            <div key={i} style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
              <div style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: item.color,
                marginTop: 7,
                flexShrink: 0,
              }} />
              <div>
                <span style={{ fontSize: 13, fontWeight: 600, color: item.color }}>{item.label}: </span>
                <span style={{ fontSize: 13, color: "#999" }}>{item.value}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Total cost */}
      <div style={{
        textAlign: "center",
        marginTop: 24,
        padding: "16px",
        background: "linear-gradient(135deg, rgba(16,185,129,0.08), rgba(168,85,247,0.08))",
        border: "1px solid rgba(16,185,129,0.2)",
        borderRadius: 12,
        maxWidth: 700,
        margin: "24px auto 0",
      }}>
        <div style={{ fontSize: 24, fontWeight: 800, color: "#10B981" }}>
          Total Cost: ₹0
        </div>
        <div style={{ fontSize: 12, color: "#888", marginTop: 4 }}>
          All 32 tools above are completely free — no credit card, no trial expiry, no hidden charges
        </div>
      </div>
    </div>
  );
}
