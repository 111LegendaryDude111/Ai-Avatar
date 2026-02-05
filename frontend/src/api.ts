export type JobStatus = "queued" | "running" | "succeeded" | "failed";

export interface CreateJobResponse {
  job_id: string;
  status: JobStatus;
}

export interface JobStatusResponse {
  job_id: string;
  status: JobStatus;
  generator_backend: string;
  created_at: string;
  updated_at: string;
  progress: number;
  message?: string | null;
  error?: string | null;
  result_url?: string | null;
}

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";

export function apiUrl(path: string): string {
  if (!path.startsWith("/")) return `${API_BASE}/${path}`;
  return `${API_BASE}${path}`;
}

export async function createJob(formData: FormData): Promise<CreateJobResponse> {
  const res = await fetch(apiUrl("/api/v1/jobs"), { method: "POST", body: formData });
  if (!res.ok) throw new Error(await res.text());
  return (await res.json()) as CreateJobResponse;
}

export async function getJob(jobId: string): Promise<JobStatusResponse> {
  const res = await fetch(apiUrl(`/api/v1/jobs/${jobId}`));
  if (!res.ok) throw new Error(await res.text());
  return (await res.json()) as JobStatusResponse;
}
