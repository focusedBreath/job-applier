import { useEffect, useState } from "react";
import { BriefcaseIcon, SearchIcon, SendIcon, FileTextIcon, SettingsIcon } from "lucide-react";
import { JobTable } from "./components/JobTable";
import { ScrapePanel } from "./components/ScrapePanel";
import { ApplyPanel } from "./components/ApplyPanel";
import { ResumePanel } from "./components/ResumePanel";
import { SettingsPanel } from "./components/SettingsPanel";
import type { TaskStatus } from "./types/api";
import { useJobs } from "./hooks/useJobs";

type Tab = "jobs" | "scrape" | "apply" | "resume" | "settings";

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: "jobs", label: "Jobs", icon: <BriefcaseIcon size={16} /> },
  { id: "scrape", label: "Scrape", icon: <SearchIcon size={16} /> },
  { id: "apply", label: "Apply", icon: <SendIcon size={16} /> },
  { id: "resume", label: "Resume", icon: <FileTextIcon size={16} /> },
  { id: "settings", label: "Settings", icon: <SettingsIcon size={16} /> },
];

function useTaskStatus() {
  const [status, setStatus] = useState<TaskStatus>({ type: "idle", progress: 0, total: 0, error: "" });

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch("/api/tasks/status");
        if (res.ok) setStatus(await res.json() as TaskStatus);
      } catch {}
    };
    poll();
    const id = setInterval(poll, 2000);
    return () => clearInterval(id);
  }, []);

  return status;
}

export default function App() {
  const [tab, setTab] = useState<Tab>("jobs");
  const taskStatus = useTaskStatus();
  const { refresh } = useJobs({ autoRefresh: false });

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <h1 className="text-xl font-bold tracking-tight">Job Applier</h1>
          {taskStatus.type !== "idle" && (
            <div className="flex items-center gap-2 text-sm">
              <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
              <span className="text-gray-300 capitalize">{taskStatus.type}…</span>
              {taskStatus.total > 0 && (
                <span className="text-gray-500">
                  {taskStatus.progress}/{taskStatus.total}
                </span>
              )}
            </div>
          )}
        </div>
      </header>

      {/* Nav */}
      <nav className="border-b border-gray-800 bg-gray-900">
        <div className="max-w-6xl mx-auto px-6">
          <div className="flex gap-1">
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  tab === t.id
                    ? "border-blue-500 text-white"
                    : "border-transparent text-gray-400 hover:text-gray-300"
                }`}
              >
                {t.icon}
                {t.label}
              </button>
            ))}
          </div>
        </div>
      </nav>

      {/* Content */}
      <main className="max-w-6xl mx-auto px-6 py-8">
        {tab === "jobs" && <JobTable />}
        {tab === "scrape" && <ScrapePanel taskStatus={taskStatus} onRefreshJobs={refresh} />}
        {tab === "apply" && <ApplyPanel taskStatus={taskStatus} onRefreshJobs={refresh} />}
        {tab === "resume" && <ResumePanel />}
        {tab === "settings" && <SettingsPanel />}
      </main>
    </div>
  );
}
