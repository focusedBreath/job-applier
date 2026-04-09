import { useState } from "react";
import { Play } from "lucide-react";
import type { Platform, TaskStatus } from "../types/api";
import { LogStream } from "./LogStream";

const PLATFORMS: Platform[] = ["linkedin", "indeed", "dice", "monster"];

interface Props {
  taskStatus: TaskStatus;
  onRefreshJobs: () => void;
}

export function ApplyPanel({ taskStatus, onRefreshJobs }: Props) {
  const [selected, setSelected] = useState<Set<Platform>>(new Set(["linkedin"]));
  const [limit, setLimit] = useState(50);
  const [dryRun, setDryRun] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");

  const busy = taskStatus.type !== "idle" || submitting;

  const toggle = (p: Platform) => {
    const next = new Set(selected);
    next.has(p) ? next.delete(p) : next.add(p);
    setSelected(next);
  };

  const startApply = async () => {
    setSubmitting(true);
    setMessage("");
    try {
      const res = await fetch("/api/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          platforms: selected.size > 0 ? Array.from(selected) : null,
          limit,
          dry_run: dryRun,
        }),
      });
      if (res.status === 409) {
        setMessage("A task is already running.");
      } else if (res.status === 404) {
        setMessage("No resume uploaded yet — go to the Resume tab first.");
      } else if (res.ok) {
        setMessage(dryRun ? "Dry run started." : "Applying started.");
        onRefreshJobs();
      } else {
        setMessage(`Error: ${res.statusText}`);
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold mb-3">Platforms to apply on</h2>
        <div className="flex flex-wrap gap-3">
          {PLATFORMS.map((p) => (
            <label
              key={p}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg border cursor-pointer transition-colors capitalize select-none ${
                selected.has(p)
                  ? "border-green-500 bg-green-950 text-green-300"
                  : "border-gray-700 text-gray-400 hover:border-gray-500"
              }`}
            >
              <input
                type="checkbox"
                className="sr-only"
                checked={selected.has(p)}
                onChange={() => toggle(p)}
                disabled={busy}
              />
              {p}
            </label>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-6">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-gray-400">Max applications</span>
          <input
            type="number"
            min={1}
            max={200}
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            disabled={busy}
            className="w-24 px-3 py-1.5 rounded-lg bg-gray-900 border border-gray-700 text-white focus:border-blue-500 outline-none"
          />
        </label>

        <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer select-none mt-5">
          <input
            type="checkbox"
            checked={dryRun}
            onChange={(e) => setDryRun(e.target.checked)}
            disabled={busy}
            className="w-4 h-4 rounded accent-blue-500"
          />
          Dry run (no submissions)
        </label>
      </div>

      <div className="flex items-center gap-4">
        <button
          onClick={startApply}
          disabled={busy}
          className="flex items-center gap-2 px-5 py-2.5 bg-green-700 hover:bg-green-600 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-colors"
        >
          <Play size={16} />
          {taskStatus.type === "applying"
            ? "Applying…"
            : dryRun
            ? "Start Dry Run"
            : "Start Applying"}
        </button>
        {taskStatus.type === "applying" && taskStatus.total > 0 && (
          <span className="text-sm text-gray-400">
            {taskStatus.progress}/{taskStatus.total} jobs
          </span>
        )}
        {message && <span className="text-sm text-gray-400">{message}</span>}
      </div>

      <LogStream />
    </div>
  );
}
