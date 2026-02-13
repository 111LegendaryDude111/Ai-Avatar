import { useEffect, useMemo, useState } from "react";
import { apiUrl, createJob, getJob, JobStatusResponse } from "./api";

type InputMode = "text" | "audio";

function clamp01(n: number): number {
  if (n < 0) return 0;
  if (n > 1) return 1;
  return n;
}

export default function App() {
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [mode, setMode] = useState<InputMode>("text");
  const [text, setText] = useState("");
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [fullFrame, setFullFrame] = useState(true);
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<JobStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const resultUrl = useMemo(() => {
    if (!job?.result_url) return null;
    return apiUrl(job.result_url);
  }, [job?.result_url]);

  useEffect(() => {
    if (!jobId) return;

    let stopped = false;
    const poll = async () => {
      try {
        const j = await getJob(jobId);
        if (stopped) return;
        setJob(j);
        if (j.status === "succeeded" || j.status === "failed") return;
        setTimeout(poll, 1000);
      } catch (e) {
        if (stopped) return;
        setError(e instanceof Error ? e.message : String(e));
      }
    };
    poll();
    return () => {
      stopped = true;
    };
  }, [jobId]);

  const onSubmit = async () => {
    setError(null);
    setJob(null);
    setJobId(null);

    if (!imageFile) {
      setError("Please upload an image.");
      return;
    }

    if (mode === "text") {
      if (!text.trim()) {
        setError("Please enter text.");
        return;
      }
    } else {
      if (!audioFile) {
        setError("Please upload an audio file.");
        return;
      }
    }

    const formData = new FormData();
    formData.append("image", imageFile);
    if (mode === "text") formData.append("text", text.trim());
    if (mode === "audio" && audioFile) formData.append("audio", audioFile);
    const options: Record<string, unknown> = { video_size: 512, video_fps: 25 };
    if (fullFrame) {
      // SadTalker: keep full input frame and paste animated face back into it.
      options.sadtalker_preprocess = "full";
      options.sadtalker_still = true;
    }
    formData.append("options", JSON.stringify(options));

    setIsSubmitting(true);
    try {
      const created = await createJob(formData);
      setJobId(created.job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="page">
      <header className="header">
        <div className="brand">
          <div className="brand-title">AI Video Avatar Studio</div>
          <div className="brand-subtitle">Upload a portrait + text/audio → get a talking video.</div>
        </div>
      </header>

      <main className="grid">
        <section className="card">
          <h2>Inputs</h2>

          <label className="label">
            Avatar image
            <input
              type="file"
              accept="image/*"
              onChange={(e) => setImageFile(e.target.files?.[0] ?? null)}
            />
          </label>

          <div className="mode">
            <label className="radio">
              <input
                type="radio"
                name="mode"
                value="text"
                checked={mode === "text"}
                onChange={() => setMode("text")}
              />
              Text
            </label>
            <label className="radio">
              <input
                type="radio"
                name="mode"
                value="audio"
                checked={mode === "audio"}
                onChange={() => setMode("audio")}
              />
              Audio
            </label>
          </div>

          <label className="radio">
            <input
              type="checkbox"
              checked={fullFrame}
              onChange={(e) => setFullFrame(e.target.checked)}
            />
            Full frame (fit entire image)
          </label>

          {mode === "text" ? (
            <label className="label">
              Script
              <textarea
                rows={5}
                placeholder="Type what the avatar should say…"
                value={text}
                onChange={(e) => setText(e.target.value)}
              />
            </label>
          ) : (
            <label className="label">
              Audio file
              <input
                type="file"
                accept="audio/*"
                onChange={(e) => setAudioFile(e.target.files?.[0] ?? null)}
              />
            </label>
          )}

          <button className="button" onClick={onSubmit} disabled={isSubmitting}>
            {isSubmitting ? "Submitting…" : "Generate Video"}
          </button>

          {error ? <div className="error">{error}</div> : null}

          {job ? (
            <div className="status">
              <div>
                <span className="pill">{job.status}</span>{" "}
                <span className="muted">{job.message ?? ""}</span>
              </div>
              <div className="progress">
                <div className="progress-bar" style={{ width: `${clamp01(job.progress) * 100}%` }} />
              </div>
              {job.error ? <pre className="error-pre">{job.error}</pre> : null}
              <div className="muted small">Job: {job.job_id}</div>
              <div className="muted small">Backend: {job.generator_backend}</div>
            </div>
          ) : null}
        </section>

        <section className="card">
          <h2>Result</h2>
          {resultUrl ? (
            <>
              <video className="video" src={resultUrl} controls />
              <a className="link" href={resultUrl} download>
                Download MP4
              </a>
            </>
          ) : (
            <div className="muted">No video yet. Submit a job to generate one.</div>
          )}
        </section>
      </main>

      <footer className="footer">
        <div className="muted small">
          Backend: <code>/api/v1/jobs</code> • Configure API base via <code>VITE_API_BASE_URL</code>
        </div>
      </footer>
    </div>
  );
}
