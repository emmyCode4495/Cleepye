# ClipMine

**Privacy-first AI video clipper** — Turn long-form videos into polished, viral-ready short clips.

A hybrid of Viral Minner’s focused “mine viral nuggets” experience and ViralMint’s technical depth.

- 100% local processing for heavy work (Whisper, FFmpeg, face tracking)
- Smart viral moment detection
- Face / subject tracking + smooth 9:16 reframing
- Real timeline preview & trim
- Word-level animated captions
- Free re-mine of the same video
- Project history
- Optional BYOK for higher-quality AI scoring

## Features (MVP Roadmap)

### Phase 1 – Core Engine (Current Focus)
- [x] Project structure
- [ ] Local file + URL ingest (yt-dlp)
- [ ] High-quality transcription (faster-whisper)
- [ ] Viral moment scoring
- [ ] Face tracking + 9:16 reframe
- [ ] Caption burn-in
- [ ] Basic export

### Phase 2 – Professional UI
- Real filmstrip timeline
- Preview / select / trim clips
- Project & mine history (SQLite)
- Settings (quality vs speed, caption styles)

### Phase 3 – Polish
- Hardware acceleration (CUDA / Metal)
- Batch processing
- Brand kit
- Desktop packaging (Tauri)
- Optional scouting & generation

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, faster-whisper, FFmpeg, yt-dlp, MediaPipe/OpenCV
- **Frontend**: React + TypeScript + Tailwind (coming)
- **Desktop**: Tauri (planned)
- **AI Scoring**: Local (Ollama) or BYOK (OpenRouter / Anthropic / OpenAI)
- **Storage**: SQLite + local filesystem

## Quick Start (Development)

### Prerequisites
- Python 3.11+
- FFmpeg installed and on PATH
- (Optional) NVIDIA GPU + CUDA for faster transcription
- (Optional) Ollama for fully local AI scoring

```bash
git clone <your-repo>
cd ClipMine

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt

# Copy env example
cp .env.example .env

# Run the API
python -m backend.main
```

The API will start at `http://localhost:8741`

## Project Structure

```
ClipMine/
├── backend/                 # Core Python pipeline
│   ├── core/               # Transcription, scoring, reframe, export
│   ├── api/                # FastAPI routes
│   ├── models/             # Pydantic schemas & DB models
│   └── main.py
├── frontend/               # React UI (Phase 2)
├── docs/
├── scripts/
├── tests/
├── requirements.txt
├── .env.example
└── README.md
```

## License

AGPL-3.0 (same spirit as ViralMint – open core, share improvements)

---

Built to be fast, private, and excellent.
