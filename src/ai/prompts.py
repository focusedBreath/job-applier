from src.queue.models import JobListing
from src.resume.models import ResumeData


def candidate_system_prompt(resume: ResumeData) -> str:
    skills = ", ".join(resume.skills[:20]) if resume.skills else "not specified"
    certs = ", ".join(resume.certifications) if resume.certifications else "none"
    exp_summary = ""
    for e in resume.experience[:3]:
        exp_summary += f"  - {e.title} at {e.company} ({e.start_date}–{e.end_date})\n"

    return f"""You are an AI assistant helping {resume.name} apply for jobs.

Candidate profile:
- Name: {resume.name}
- Email: {resume.email}
- Phone: {resume.phone}
- Location: {resume.location}
- LinkedIn: {resume.linkedin}
- Summary: {resume.summary}
- Skills: {skills}
- Certifications: {certs}
- Recent experience:
{exp_summary or "  (not provided)"}

Always respond in the exact JSON format requested. Be concise and professional."""


def should_apply_prompt(job: JobListing) -> str:
    return f"""Evaluate whether the candidate should apply to this job.

Job:
- Title: {job.title}
- Company: {job.company}
- Location: {job.location}
- Platform: {job.platform}
- Description (excerpt): {job.description[:1000]}

Respond with JSON matching this schema:
{{"action": "apply" | "skip" | "save", "reason": "<one sentence>"}}

- "apply": good fit, candidate should apply now
- "skip": poor fit, irrelevant, or clearly below/above level
- "save": potentially interesting but not an immediate match (junior roles, stretch roles)"""


def fill_field_prompt(
    label: str,
    field_type: str,
    options: list[str],
    resume_value: str,
    job: JobListing,
) -> str:
    opts = f"\nOptions: {options}" if options else ""
    return f"""Fill in a job application form field for the candidate.

Field: {label}
Type: {field_type}{opts}
Job: {job.title} at {job.company}
Candidate's resume value for this field: {resume_value or "(none)"}

Respond with JSON:
{{"value": "<value to fill>", "confidence": 0.0-1.0}}

If unsure or field is irrelevant, return {{"value": "", "confidence": 0.0}}"""


def answer_question_prompt(question: str, job: JobListing) -> str:
    return f"""Answer a custom question on a job application.

Job: {job.title} at {job.company}
Question: {question}

Write a 2-3 sentence professional answer in first person.
Respond with JSON:
{{"answer": "<your answer>"}}"""


def confirm_submission_prompt(job: JobListing, fields: dict[str, str]) -> str:
    field_summary = "\n".join(f"  {k}: {v}" for k, v in list(fields.items())[:20])
    return f"""Review this job application before final submission.

Job: {job.title} at {job.company} ({job.platform})
URL: {job.url}

Fields filled:
{field_summary}

Should we submit?
Respond with JSON:
{{"action": "submit" | "review" | "cancel", "reason": "<one sentence>"}}

- "submit": everything looks correct
- "review": something seems off but not a dealbreaker (will pause for human check)
- "cancel": critical problem (wrong company, suspicious listing, etc.)"""
