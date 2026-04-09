import { useCallback, useEffect, useState } from "react";
import type { Job, JobPage, JobStats, JobStatus, Platform } from "../types/api";

const BASE = "/api";

export function useJobs(opts: {
  status?: JobStatus;
  platform?: Platform;
  limit?: number;
  offset?: number;
  autoRefresh?: boolean;
}) {
  const { status, platform, limit = 50, offset = 0, autoRefresh = false } = opts;
  const [page, setPage] = useState<JobPage | null>(null);
  const [stats, setStats] = useState<JobStats | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (platform) params.set("platform", platform);
    params.set("limit", String(limit));
    params.set("offset", String(offset));

    const [jobsRes, statsRes] = await Promise.all([
      fetch(`${BASE}/jobs?${params}`),
      fetch(`${BASE}/jobs/stats`),
    ]);
    setPage(await jobsRes.json());
    setStats(await statsRes.json());
    setLoading(false);
  }, [status, platform, limit, offset]);

  useEffect(() => {
    fetchJobs();
    if (!autoRefresh) return;
    const id = setInterval(fetchJobs, 5000);
    return () => clearInterval(id);
  }, [fetchJobs, autoRefresh]);

  const updateStatus = async (jobId: number, newStatus: JobStatus, reason = "") => {
    await fetch(`${BASE}/jobs/${jobId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: newStatus, reason }),
    });
    fetchJobs();
  };

  return { page, stats, loading, refresh: fetchJobs, updateStatus };
}
