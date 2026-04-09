import { useEffect, useState } from "react";
import { Save, Eye, EyeOff } from "lucide-react";

const MASK = "••••••••";

interface Settings {
  linkedin_email: string;
  linkedin_password: string;
  indeed_email: string;
  indeed_password: string;
  dice_email: string;
  dice_password: string;
  monster_email: string;
  monster_password: string;
  claude_api_key: string;
  claude_decision_model: string;
  claude_fill_model: string;
  search_keywords: string[];
  search_locations: string[];
  search_days_back: number;
  max_applications_per_day: number;
  delay_min_seconds: number;
  delay_max_seconds: number;
}

type SettingsKey = keyof Settings;

const SENSITIVE: Set<SettingsKey> = new Set([
  "linkedin_password",
  "indeed_password",
  "dice_password",
  "monster_password",
  "claude_api_key",
]);

function SectionHeader({ title }: { title: string }) {
  return (
    <h2 className="text-base font-semibold text-gray-300 border-b border-gray-800 pb-2 mb-4">
      {title}
    </h2>
  );
}

function Field({
  label,
  value,
  onChange,
  sensitive,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  sensitive?: boolean;
  placeholder?: string;
}) {
  const [show, setShow] = useState(false);
  const isMasked = sensitive && value === MASK;

  return (
    <div>
      <label className="block text-xs text-gray-500 mb-1">{label}</label>
      <div className="relative">
        <input
          type={sensitive && !show ? "password" : "text"}
          value={value}
          placeholder={placeholder}
          onFocus={() => { if (isMasked) onChange(""); }}
          onChange={(e) => onChange(e.target.value)}
          className="w-full px-3 py-2 rounded-lg bg-gray-900 border border-gray-700 text-white text-sm focus:border-blue-500 outline-none pr-8"
        />
        {sensitive && (
          <button
            type="button"
            onClick={() => setShow((s) => !s)}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
          >
            {show ? <EyeOff size={14} /> : <Eye size={14} />}
          </button>
        )}
      </div>
    </div>
  );
}

function ListField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string[];
  onChange: (v: string[]) => void;
  placeholder?: string;
}) {
  const raw = value.join(", ");
  return (
    <div>
      <label className="block text-xs text-gray-500 mb-1">
        {label} <span className="text-gray-600">(comma-separated)</span>
      </label>
      <input
        type="text"
        defaultValue={raw}
        placeholder={placeholder}
        onBlur={(e) =>
          onChange(e.target.value.split(",").map((s) => s.trim()).filter(Boolean))
        }
        className="w-full px-3 py-2 rounded-lg bg-gray-900 border border-gray-700 text-white text-sm focus:border-blue-500 outline-none"
      />
    </div>
  );
}

function NumberField({
  label,
  value,
  onChange,
  min,
  max,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
}) {
  return (
    <div>
      <label className="block text-xs text-gray-500 mb-1">{label}</label>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full px-3 py-2 rounded-lg bg-gray-900 border border-gray-700 text-white text-sm focus:border-blue-500 outline-none"
      />
    </div>
  );
}

export function SettingsPanel() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [edits, setEdits] = useState<Partial<Settings>>({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    fetch("/api/settings")
      .then((r) => r.json())
      .then((d) => setSettings(d as Settings));
  }, []);

  const get = <K extends SettingsKey>(key: K): Settings[K] => {
    if (key in edits) return edits[key] as Settings[K];
    return settings ? settings[key] : ("" as Settings[K]);
  };

  const set = <K extends SettingsKey>(key: K, value: Settings[K]) => {
    setEdits((prev) => ({ ...prev, [key]: value }));
  };

  const save = async () => {
    if (Object.keys(edits).length === 0) return;
    setSaving(true);
    setMessage("");
    try {
      const res = await fetch("/api/settings", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(edits),
      });
      if (res.ok) {
        setSettings((prev) => prev ? { ...prev, ...edits } : prev);
        setEdits({});
        setMessage("Settings saved. Restart the container to apply credential changes.");
      } else {
        setMessage("Save failed.");
      }
    } finally {
      setSaving(false);
    }
  };

  if (!settings) {
    return <div className="text-gray-500 text-sm">Loading…</div>;
  }

  const dirty = Object.keys(edits).length > 0;

  return (
    <div className="space-y-8 max-w-2xl">
      {/* Credentials */}
      <div>
        <SectionHeader title="Job Board Credentials" />
        <div className="grid grid-cols-2 gap-4">
          <Field label="LinkedIn Email" value={get("linkedin_email")} onChange={(v) => set("linkedin_email", v)} />
          <Field label="LinkedIn Password" value={get("linkedin_password")} onChange={(v) => set("linkedin_password", v)} sensitive />
          <Field label="Indeed Email" value={get("indeed_email")} onChange={(v) => set("indeed_email", v)} />
          <Field label="Indeed Password" value={get("indeed_password")} onChange={(v) => set("indeed_password", v)} sensitive />
          <Field label="Dice Email" value={get("dice_email")} onChange={(v) => set("dice_email", v)} />
          <Field label="Dice Password" value={get("dice_password")} onChange={(v) => set("dice_password", v)} sensitive />
          <Field label="Monster Email" value={get("monster_email")} onChange={(v) => set("monster_email", v)} />
          <Field label="Monster Password" value={get("monster_password")} onChange={(v) => set("monster_password", v)} sensitive />
        </div>
      </div>

      {/* Claude */}
      <div>
        <SectionHeader title="Claude API" />
        <div className="space-y-4">
          <Field label="API Key" value={get("claude_api_key")} onChange={(v) => set("claude_api_key", v)} sensitive placeholder="sk-ant-..." />
          <div className="grid grid-cols-2 gap-4">
            <Field label="Decision Model" value={get("claude_decision_model")} onChange={(v) => set("claude_decision_model", v)} placeholder="claude-sonnet-4-6" />
            <Field label="Fill Model" value={get("claude_fill_model")} onChange={(v) => set("claude_fill_model", v)} placeholder="claude-haiku-4-5-20251001" />
          </div>
        </div>
      </div>

      {/* Search */}
      <div>
        <SectionHeader title="Search" />
        <div className="space-y-4">
          <ListField label="Keywords" value={get("search_keywords")} onChange={(v) => set("search_keywords", v)} placeholder="SOC analyst, software engineer" />
          <ListField label="Locations" value={get("search_locations")} onChange={(v) => set("search_locations", v)} placeholder="Remote, New Jersey" />
          <div className="w-32">
            <NumberField label="Days back" value={get("search_days_back")} onChange={(v) => set("search_days_back", v)} min={1} max={30} />
          </div>
        </div>
      </div>

      {/* Limits */}
      <div>
        <SectionHeader title="Application Limits" />
        <div className="grid grid-cols-3 gap-4">
          <NumberField label="Max per day" value={get("max_applications_per_day")} onChange={(v) => set("max_applications_per_day", v)} min={1} max={500} />
          <NumberField label="Min delay (s)" value={get("delay_min_seconds")} onChange={(v) => set("delay_min_seconds", v)} min={1} />
          <NumberField label="Max delay (s)" value={get("delay_max_seconds")} onChange={(v) => set("delay_max_seconds", v)} min={1} />
        </div>
      </div>

      {/* Save */}
      <div className="flex items-center gap-4">
        <button
          onClick={save}
          disabled={!dirty || saving}
          className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-colors"
        >
          <Save size={16} />
          {saving ? "Saving…" : "Save Settings"}
        </button>
        {message && <span className="text-sm text-gray-400">{message}</span>}
      </div>

      <p className="text-xs text-gray-600">
        Settings are written to <code className="text-gray-500">data/settings.json</code> and take effect on next container restart.
        Search keywords, locations, and limits are applied immediately on the next scrape/apply run.
      </p>
    </div>
  );
}
