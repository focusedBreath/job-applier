export type JobStatus = "pending" | "applied" | "skipped" | "failed";
export type Platform = "linkedin" | "indeed" | "dice" | "monster";

export interface Job {
  id: number;
  title: string;
  company: string;
  location: string;
  url: string;
  platform: Platform;
  description: string;
  salary: string;
  posted_date: string;
  status: JobStatus;
  added_at: string | null;
  applied_at: string | null;
  skip_reason: string;
  error: string;
  ai_reason: string;
}

export interface JobPage {
  items: Job[];
  total: number;
  offset: number;
  limit: number;
}

export interface JobStats {
  total: number;
  pending: number;
  applied: number;
  skipped: number;
  failed: number;
  by_platform: Record<string, number>;
}

export interface ExperienceEntry {
  title: string;
  company: string;
  start_date: string;
  end_date: string;
  description: string;
}

export interface EducationEntry {
  degree: string;
  institution: string;
  graduation_date: string;
  gpa: string;
}

export interface ResumeData {
  name: string;
  email: string;
  phone: string;
  location: string;
  linkedin: string;
  github: string;
  website: string;
  summary: string;
  experience: ExperienceEntry[];
  education: EducationEntry[];
  skills: string[];
  certifications: string[];
  total_years_experience: string;
}

export interface TaskStatus {
  type: "idle" | "scraping" | "applying";
  progress: number;
  total: number;
  error: string;
}

export interface LogEvent {
  event: string;
  level?: string;
  timestamp?: string;
  [key: string]: unknown;
}
