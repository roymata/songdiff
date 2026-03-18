import { Router } from "express";
import multer from "multer";
import FormData from "form-data";
import fs from "fs";

const AUDIO_SERVICE_URL =
  process.env.AUDIO_SERVICE_URL || "http://localhost:5001";

const upload = multer({
  dest: "/tmp/song-uploads/",
  limits: { fileSize: 50 * 1024 * 1024 }, // 50 MB
  fileFilter: (_req, file, cb) => {
    const allowed = [
      "audio/mpeg",
      "audio/wav",
      "audio/flac",
      "audio/ogg",
      "audio/mp4",
      "audio/x-m4a",
      "audio/aac",
      "audio/x-wav",
    ];
    if (allowed.includes(file.mimetype)) {
      cb(null, true);
    } else {
      cb(new Error(`Unsupported audio type: ${file.mimetype}`));
    }
  },
});

export const compareRouter = Router();

const YT_URL_RE =
  /^https?:\/\/(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/shorts\/)[\w-]+/;

// POST /api/compare-urls — accepts { url_a, url_b }
compareRouter.post("/compare-urls", async (req, res) => {
  const { url_a, url_b } = req.body ?? {};

  if (!url_a || !url_b) {
    res.status(400).json({ error: "Two YouTube URLs required (url_a, url_b)" });
    return;
  }

  if (!YT_URL_RE.test(url_a) || !YT_URL_RE.test(url_b)) {
    res.status(400).json({ error: "Both URLs must be valid YouTube links" });
    return;
  }

  try {
    const response = await fetch(`${AUDIO_SERVICE_URL}/compare-urls`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url_a, url_b }),
    });

    const data = await response.json();

    if (!response.ok) {
      res.status(response.status).json(data);
      return;
    }

    res.json(data);
  } catch (err) {
    console.error("Audio service error:", err);
    res.status(502).json({ error: "Audio analysis service unavailable" });
  }
});

// POST /api/compare-search — accepts { song_a: { name, artist }, song_b: { name, artist } }
compareRouter.post("/compare-search", async (req, res) => {
  const { song_a, song_b } = req.body ?? {};

  if (!song_a?.name?.trim() || !song_a?.artist?.trim()) {
    res.status(400).json({ error: "Song A requires name and artist" });
    return;
  }
  if (!song_b?.name?.trim() || !song_b?.artist?.trim()) {
    res.status(400).json({ error: "Song B requires name and artist" });
    return;
  }

  try {
    const response = await fetch(`${AUDIO_SERVICE_URL}/compare-search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ song_a, song_b }),
    });

    const data = await response.json();

    if (!response.ok) {
      res.status(response.status).json(data);
      return;
    }

    res.json(data);
  } catch (err) {
    console.error("Audio service error:", err);
    res.status(502).json({ error: "Audio analysis service unavailable" });
  }
});

// POST /api/compare-mixed — each song can be search or URL
compareRouter.post("/compare-mixed", async (req, res) => {
  const { song_a, song_b } = req.body ?? {};

  if (!song_a || !song_b) {
    res.status(400).json({ error: "song_a and song_b are required" });
    return;
  }

  // Validate each song entry
  for (const [label, song] of [["Song A", song_a], ["Song B", song_b]] as const) {
    const type = song.type || "search";
    if (type === "url" && !song.url?.trim()) {
      res.status(400).json({ error: `${label}: URL is required` });
      return;
    }
    if (type === "search" && (!song.name?.trim() || !song.artist?.trim())) {
      res.status(400).json({ error: `${label}: name and artist are required` });
      return;
    }
  }

  try {
    const response = await fetch(`${AUDIO_SERVICE_URL}/compare-mixed`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ song_a, song_b }),
    });

    const data = await response.json();

    if (!response.ok) {
      res.status(response.status).json(data);
      return;
    }

    res.json(data);
  } catch (err) {
    console.error("Audio service error:", err);
    res.status(502).json({ error: "Audio analysis service unavailable" });
  }
});

// POST /api/compare — accepts file_a and file_b
compareRouter.post(
  "/compare",
  upload.fields([
    { name: "file_a", maxCount: 1 },
    { name: "file_b", maxCount: 1 },
  ]),
  async (req, res) => {
    const files = req.files as { [field: string]: Express.Multer.File[] };

    if (!files?.file_a?.[0] || !files?.file_b?.[0]) {
      res.status(400).json({ error: "Two audio files required (file_a, file_b)" });
      return;
    }

    const fileA = files.file_a[0];
    const fileB = files.file_b[0];

    try {
      // Forward both files to the Python audio-service
      const form = new FormData();
      form.append("file_a", fs.createReadStream(fileA.path), {
        filename: fileA.originalname,
        contentType: fileA.mimetype,
      });
      form.append("file_b", fs.createReadStream(fileB.path), {
        filename: fileB.originalname,
        contentType: fileB.mimetype,
      });

      const response = await fetch(`${AUDIO_SERVICE_URL}/compare`, {
        method: "POST",
        // @ts-ignore form-data works with fetch body
        body: form,
        headers: form.getHeaders(),
      });

      const data = await response.json();

      if (!response.ok) {
        res.status(response.status).json(data);
        return;
      }

      res.json(data);
    } catch (err) {
      console.error("Audio service error:", err);
      res.status(502).json({ error: "Audio analysis service unavailable" });
    } finally {
      // Clean up temp files
      [fileA.path, fileB.path].forEach((p) => {
        try {
          fs.unlinkSync(p);
        } catch {}
      });
    }
  }
);
