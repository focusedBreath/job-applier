import { useState } from "react";
import { Play } from "lucide-react";
import type { Platform, TaskStatus } from "../types/api";
import { LogStream } from "./LogStream";

const PLATFORMS: Platform[] = ["linkedin", "indeed", "dice", "monster"];

interface Props {
  taskStatus: TaskStatus;
  onRefreshJobs: () => void;
}

export function ScrapePanel({ taskStatus, onRefreshJobs }: Props) {
  const [selected, setSelected] = useState<Set<Platform>>(new Set(["linkedin"]));
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");

  const busy = taskStatus.type !== "idle" || submitting;

  const toggle = (p: Platform) => {
    const next = new Set(selected);
    next.has(p) ? next.delete(p) : next.add(p);
    setSelected(next);
  };

  const startScrape = async () => {
    if (selected.size === 0) return;
    setSubmitting(true);
    setMessage("");
    try {
      const res = await fetch("/api/scrape", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ platforms: Array.from(selected) }),
      });
      if (res.status === 409) {
        setMessage("A task is already running.");
      } else if (res.ok) {
        setMessage("Scrape started.");
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
        <h2 className="text-lg font-semibold mb-3">Platforms to scrape</h2>
        <div className="flex flex-wrap gap-3">
          {PLATFORMS.map((p) => (
            <label
              key={p}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg border cursor-pointer transition-colors capitalize select-none ${
                selected.has(p)
                  ? "border-blue-500 bg-blue-950 text-blue-300"
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

      <div className="flex items-center gap-4">
        <button
          onClick={startScrape}
          disabled={busy || selected.size === 0}
          className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-colors"
        >
          <Play size={16} />
          {taskStatus.type === "scraping" ? "Scraping…" : "Start Scraping"}
        </button>
        {taskStatus.type === "scraping" && taskStatus.total > 0 && (
          <span className="text-sm text-gray-400">
            {taskStatus.progress}/{taskStatus.total} platforms
          </span>
        )}
        {message && <span className="text-sm text-gray-400">{message}</span>}
      </div>

      <LogStream />
    </div>
  );
}
