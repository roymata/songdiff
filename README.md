# SongDiff — Song Similarity Comparator

Compare two songs and get an instant similarity score based on rhythm, tempo, timbre, and harmony.

## Architecture

```
┌─────────────┐     ┌─────────────────┐     ┌──────────────────┐
│   Frontend   │────▶│  Backend (Node)  │────▶│  Audio Service   │
│  React/Vite  │     │  Express API     │     │  Python/librosa  │
│  :5173       │     │  :3001           │     │  :5001           │
└─────────────┘     └─────────────────┘     └──────────────────┘
```

- **Frontend**: React + TypeScript + Tailwind CSS (Vite)
- **Backend**: Node.js + Express — API gateway, file upload handling
- **Audio Service**: Python + Flask + librosa — feature extraction & similarity computation

## Prerequisites

- Node.js 20+
- Python 3.11+
- ffmpeg and libsndfile (for audio processing)

## Local Development Setup

### 1. Audio Service (Python)

```bash
cd audio-service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Runs on `http://localhost:5001`.

### 2. Backend (Node.js)

```bash
cd backend
npm install
npm run dev
```

Runs on `http://localhost:3001`.

### 3. Frontend (React)

```bash
cd frontend
npm install
npm run dev
```

Runs on `http://localhost:5173`. API calls are proxied to the backend via Vite config.

## Docker Setup

```bash
docker compose up --build
```

This starts all three services. The frontend is available at `http://localhost:5173`.

## API Reference

### `POST /api/compare`

Upload two audio files and receive similarity scores.

**Request** (multipart/form-data):

| Field    | Type   | Description          |
|----------|--------|----------------------|
| `file_a` | File   | First audio file     |
| `file_b` | File   | Second audio file    |

Supported formats: MP3, WAV, FLAC, OGG, M4A, AAC (max 50 MB each).

**Example (curl):**

```bash
curl -X POST http://localhost:3001/api/compare \
  -F "file_a=@song1.mp3" \
  -F "file_b=@song2.mp3"
```

**Response:**

```json
{
  "overall": 72.3,
  "breakdown": {
    "rhythm": 78.5,
    "tempo": 95.2,
    "timbre": 61.4,
    "harmony": 68.1
  },
  "details": {
    "song_a": {
      "tempo_bpm": 120.0,
      "spectral_centroid": 2145.3
    },
    "song_b": {
      "tempo_bpm": 122.5,
      "spectral_centroid": 1987.6
    }
  }
}
```

## Deployment

### Frontend → Vercel

```bash
cd frontend
npm run build
# Deploy `dist/` to Vercel or Netlify
```

Set `VITE_API_URL` to your deployed backend URL.

### Backend → Railway / Render

Deploy the `backend/` directory. Set environment variables:

- `PORT=3001`
- `AUDIO_SERVICE_URL=<deployed-audio-service-url>`
- `FRONTEND_URL=<deployed-frontend-url>`

### Audio Service → Railway / Fly.io (Docker)

```bash
cd audio-service
docker build -t song-similarity-audio .
# Push to your container registry and deploy
```

Set `PORT=5001`.

## Project Structure

```
song-similarity/
├── frontend/               # React + Vite + TypeScript + Tailwind
│   ├── src/
│   │   ├── components/     # UI components
│   │   ├── hooks/          # Custom React hooks
│   │   ├── types/          # TypeScript types
│   │   ├── App.tsx         # Main application
│   │   └── main.tsx        # Entry point
│   ├── package.json
│   └── vite.config.ts
│
├── backend/                # Node.js + Express API gateway
│   ├── src/
│   │   ├── routes/         # API route handlers
│   │   └── index.ts        # Server entry
│   └── package.json
│
├── audio-service/          # Python + Flask + librosa
│   ├── app.py              # Flask API
│   ├── analyzer.py         # Feature extraction & similarity
│   ├── requirements.txt
│   └── Dockerfile
│
├── docker-compose.yml
└── README.md
```
