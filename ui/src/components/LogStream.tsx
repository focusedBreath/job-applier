import { useEffect, useRef } from "react";
import { useLogStream } from "../hooks/useLogStream";
import type { LogEvent } from "../types/api";

const LEVEL_COLOR: Record<string, string> = {
  info: "text-blue-400",
  warning: "text-yellow-400",
  error: "text-red-400",
  debug: "text-gray-500",
};

function formatLine(entry: LogEvent): string {
  const ts = entry.timestamp ? String(entry.timestamp).slice(11, 19) : "";
  const extras = Object.entries(entry)
    .filter(([k]) => !["event", "level", "timestamp", "logger"].includes(k))
    .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
    .join(" ");
  return [ts, entry.event, extras].filter(Boolean).join("  ");
}

export function LogStream() {
  const { lines, clear } = useLogStream();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-300">Live Log</span>
        <button
          onClick={clear}
          className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
        >
          Clear
        </button>
      </div>
      <div className="flex-1 overflow-y-auto bg-gray-950 rounded-lg p-3 font-mono text-xs min-h-[200px] max-h-[400px]">
        {lines.length === 0 && (
          <span className="text-gray-600">Waiting for events…</span>
        )}
        {lines.map((entry, i) => (
          <div
            key={i}
            className={`leading-5 ${LEVEL_COLOR[entry.level ?? "info"] ?? "text-gray-300"}`}
          >
            {formatLine(entry)}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
