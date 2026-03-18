import express from "express";
import cors from "cors";
import { compareRouter } from "./routes/compare";

const app = express();
const PORT = parseInt(process.env.PORT || "3001", 10);

const frontendUrl = process.env.FRONTEND_URL || "http://localhost:5173";
app.use(cors({ origin: frontendUrl === "*" ? true : frontendUrl }));
app.use(express.json());

app.get("/health", (_req, res) => {
  res.json({ status: "ok" });
});

app.use("/api", compareRouter);

app.listen(PORT, () => {
  console.log(`Backend running on http://localhost:${PORT}`);
});
