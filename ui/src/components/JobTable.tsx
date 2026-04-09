import { useState } from "react";
import { ExternalLink, RotateCcw, XCircle } from "lucide-react";
import { useJobs } from "../hooks/useJobs";
import type { JobStatus, Platform } from "../types/api";

const STATUS_BADGE: Record<JobStatus, string> = {
  pending: "bg-yellow-900 text-yellow-300",
  applied: "bg-green-900 text-green-300",
  skipped: "bg-gray-700 text-gray-400",
  failed: "bg-red-900 text-red-300",
};

const PLATFORMS: Platform[] = ["linkedin", "indeed", "dice", "monster"];
const STATUSES: JobStatus[] = ["pending", "applied", "skipped", "failed"];

export function JobTable() {
  const [statusFilter, setStatusFilter] = useState<JobStatus | undefined>();
  const [platformFilter, setPlatformFilter] = useState<Platform | undefined>();
  const [offset, setOffset] = useState(0);
  const limit = 50;

  const { page, stats, loading, updateStatus } = useJobs({
    status: statusFilter,
    platform: platformFilter,
    limit,
    offset,
    autoRefresh: true,
  });

  const totalPages = page ? Math.ceil(page.total / limit) : 0;
  const currentPage = Math.floor(offset / limit);

  return (
    <div className="space-y-4">
      {/* Stats bar */}
      {stats && (
        <div className="flex gap-4 text-sm">
          {STATUSES.map((s) => (
            <button
              key={s}
              onClick={() => { setStatusFilter(statusFilter === s ? undefined : s); setOffset(0); }}
              className={`px-3 py-1 rounded-full font-medium transition-opacity ${STATUS_BADGE[s]} ${statusFilter && statusFilter !== s ? "opacity-40" : ""}`}
            >
              {s} {stats[s]}
            </button>
          ))}
          <span className="ml-auto text-gray-400">total: {stats.total}</span>
        </div>
      )}

      {/* Platform filter */}
      <div className="flex gap-2 text-sm">
        {PLATFORMS.map((p) => (
          <button
            key={p}
            onClick={() => { setPlatformFilter(platformFilter === p ? undefined : p); setOffset(0); }}
            className={`px-3 py-1 rounded border transition-colors capitalize ${
              platformFilter === p
                ? "border-blue-500 text-blue-300 bg-blue-950"
                : "border-gray-700 text-gray-400 hover:border-gray-500"
            }`}
          >
            {p}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-gray-800">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800 bg-gray-900 text-gray-400 text-left">
              <th className="px-4 py-3">Title</th>
              <th className="px-4 py-3">Company</th>
              <th className="px-4 py-3">Location</th>
              <th className="px-4 py-3">Platform</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Added</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading && !page && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-500">Loading…</td></tr>
            )}
            {page?.items.map((job) => (
              <tr
                key={job.id}
                className="border-b border-gray-800 hover:bg-gray-900 transition-colors"
                title={job.ai_reason || job.skip_reason || job.error}
              >
                <td className="px-4 py-3 font-medium text-white max-w-xs truncate">{job.title}</td>
                <td className="px-4 py-3 text-gray-300">{job.company}</td>
                <td className="px-4 py-3 text-gray-400 max-w-[140px] truncate">{job.location}</td>
                <td className="px-4 py-3 text-gray-400 capitalize">{job.platform}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_BADGE[job.status as JobStatus]}`}>
                    {job.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-500 text-xs">
                  {job.added_at ? new Date(job.added_at).toLocaleDateString() : "—"}
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-2">
                    <a
                      href={job.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-gray-500 hover:text-blue-400 transition-colors"
                      title="Open job listing"
                    >
                      <ExternalLink size={15} />
                    </a>
                    {job.status !== "pending" && (
                      <button
                        onClick={() => updateStatus(job.id, "pending")}
                        className="text-gray-500 hover:text-yellow-400 transition-colors"
                        title="Reset to pending"
                      >
                        <RotateCcw size={15} />
                      </button>
                    )}
                    {job.status === "pending" && (
                      <button
                        onClick={() => updateStatus(job.id, "skipped", "manually skipped")}
                        className="text-gray-500 hover:text-red-400 transition-colors"
                        title="Skip"
                      >
                        <XCircle size={15} />
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {page?.items.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-500">No jobs found.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex gap-2 justify-end text-sm">
          <button
            disabled={currentPage === 0}
            onClick={() => setOffset(Math.max(0, offset - limit))}
            className="px-3 py-1 rounded border border-gray-700 text-gray-400 disabled:opacity-30 hover:border-gray-500"
          >
            Prev
          </button>
          <span className="px-3 py-1 text-gray-500">
            {currentPage + 1} / {totalPages}
          </span>
          <button
            disabled={currentPage >= totalPages - 1}
            onClick={() => setOffset(offset + limit)}
            className="px-3 py-1 rounded border border-gray-700 text-gray-400 disabled:opacity-30 hover:border-gray-500"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
