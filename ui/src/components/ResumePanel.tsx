import { useEffect, useRef, useState } from "react";
import { Upload, Save } from "lucide-react";
import type { ResumeData } from "../types/api";

type ScalarKey = keyof Omit<ResumeData, "experience" | "education" | "skills" | "certifications">;

const SCALAR_FIELDS: { key: ScalarKey; label: string; multiline?: boolean }[] = [
  { key: "name", label: "Full Name" },
  { key: "email", label: "Email" },
  { key: "phone", label: "Phone" },
  { key: "location", label: "Location" },
  { key: "linkedin", label: "LinkedIn URL" },
  { key: "github", label: "GitHub URL" },
  { key: "website", label: "Website" },
  { key: "total_years_experience", label: "Years of Experience" },
  { key: "summary", label: "Summary", multiline: true },
];

export function ResumePanel() {
  const [resume, setResume] = useState<ResumeData | null>(null);
  const [edits, setEdits] = useState<Partial<ResumeData>>({});
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetch("/api/resume")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => { if (data) setResume(data); })
      .catch(() => {});
  }, []);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setMessage("");
    const form = new FormData();
    form.append("file", file);
    try {
      const res = await fetch("/api/resume/upload", { method: "POST", body: form });
      if (res.ok) {
        const data = await res.json() as ResumeData;
        setResume(data);
        setEdits({});
        setMessage("Resume uploaded and parsed.");
      } else {
        const err = await res.json() as { detail?: string };
        setMessage(`Upload failed: ${err.detail ?? res.statusText}`);
      }
    } finally {
      setUploading(false);
    }
  };

  const handleSave = async () => {
    if (Object.keys(edits).length === 0) return;
    setSaving(true);
    setMessage("");
    try {
      const res = await fetch("/api/resume/fields", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ overrides: edits }),
      });
      if (res.ok) {
        setResume((prev) => prev ? { ...prev, ...edits } : prev);
        setEdits({});
        setMessage("Changes saved.");
      } else {
        setMessage("Save failed.");
      }
    } finally {
      setSaving(false);
    }
  };

  const getValue = (key: ScalarKey): string => {
    if (key in edits) return String(edits[key] ?? "");
    return resume ? String(resume[key] ?? "") : "";
  };

  const setEdit = (key: ScalarKey, value: string) => {
    setEdits((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <div className="space-y-6">
      {/* Upload */}
      <div>
        <h2 className="text-lg font-semibold mb-3">Resume File</h2>
        <div className="flex items-center gap-4">
          <button
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-2 px-4 py-2 border border-gray-600 hover:border-gray-400 text-gray-300 rounded-lg transition-colors disabled:opacity-40"
          >
            <Upload size={16} />
            {uploading ? "Uploading…" : resume ? "Replace DOCX" : "Upload DOCX"}
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".docx"
            className="hidden"
            onChange={handleUpload}
          />
          {message && <span className="text-sm text-gray-400">{message}</span>}
        </div>
      </div>

      {resume && (
        <>
          {/* Scalar fields */}
          <div>
            <h2 className="text-lg font-semibold mb-3">Parsed Fields</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {SCALAR_FIELDS.map(({ key, label, multiline }) => (
                <div key={key} className={multiline ? "md:col-span-2" : ""}>
                  <label className="block text-xs text-gray-500 mb-1">{label}</label>
                  {multiline ? (
                    <textarea
                      rows={4}
                      value={getValue(key)}
                      onChange={(e) => setEdit(key, e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-gray-900 border border-gray-700 text-white text-sm focus:border-blue-500 outline-none resize-y"
                    />
                  ) : (
                    <input
                      type="text"
                      value={getValue(key)}
                      onChange={(e) => setEdit(key, e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-gray-900 border border-gray-700 text-white text-sm focus:border-blue-500 outline-none"
                    />
                  )}
                  {key in edits && (
                    <span className="text-xs text-yellow-500 mt-0.5 block">Modified</span>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Skills */}
          <div>
            <h2 className="text-base font-semibold mb-2 text-gray-300">Skills</h2>
            <div className="flex flex-wrap gap-2">
              {resume.skills.map((s, i) => (
                <span key={i} className="px-2 py-1 bg-gray-800 rounded text-sm text-gray-300">
                  {s}
                </span>
              ))}
            </div>
          </div>

          {/* Certifications */}
          {resume.certifications.length > 0 && (
            <div>
              <h2 className="text-base font-semibold mb-2 text-gray-300">Certifications</h2>
              <ul className="space-y-1">
                {resume.certifications.map((c, i) => (
                  <li key={i} className="text-sm text-gray-300">• {c}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Experience */}
          {resume.experience.length > 0 && (
            <div>
              <h2 className="text-base font-semibold mb-3 text-gray-300">Experience</h2>
              <div className="space-y-4">
                {resume.experience.map((e, i) => (
                  <div key={i} className="pl-3 border-l border-gray-700">
                    <div className="font-medium text-white">{e.title}</div>
                    <div className="text-sm text-gray-400">{e.company}</div>
                    <div className="text-xs text-gray-500">{e.start_date} – {e.end_date}</div>
                    {e.description && (
                      <div className="text-sm text-gray-400 mt-1 line-clamp-3">{e.description}</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Education */}
          {resume.education.length > 0 && (
            <div>
              <h2 className="text-base font-semibold mb-3 text-gray-300">Education</h2>
              <div className="space-y-3">
                {resume.education.map((e, i) => (
                  <div key={i} className="pl-3 border-l border-gray-700">
                    <div className="font-medium text-white">{e.degree}</div>
                    <div className="text-sm text-gray-400">{e.institution}</div>
                    <div className="text-xs text-gray-500">{e.graduation_date}{e.gpa ? ` · GPA ${e.gpa}` : ""}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Save button */}
          {Object.keys(edits).length > 0 && (
            <div className="sticky bottom-4">
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white rounded-lg font-medium transition-colors shadow-lg"
              >
                <Save size={16} />
                {saving ? "Saving…" : `Save ${Object.keys(edits).length} change${Object.keys(edits).length > 1 ? "s" : ""}`}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
