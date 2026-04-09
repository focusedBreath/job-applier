import json
import re
from pathlib import Path

from docx import Document

from src.resume.models import EducationEntry, ExperienceEntry, ResumeData


# ── Regex helpers ────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")
_LINKEDIN_RE = re.compile(r"linkedin\.com/in/[\w-]+", re.IGNORECASE)
_GITHUB_RE = re.compile(r"github\.com/[\w-]+", re.IGNORECASE)
_URL_RE = re.compile(r"https?://[\w./%-]+")

_SECTION_HEADERS = {
    "experience": {"experience", "work experience", "employment", "work history"},
    "education": {"education", "academic background"},
    "skills": {"skills", "technical skills", "core competencies", "technologies"},
    "certifications": {"certifications", "certificates", "licenses"},
    "summary": {"summary", "profile", "objective", "about"},
}


def _detect_section(text: str) -> str | None:
    lower = text.strip().lower().rstrip(":").strip()
    for section, keywords in _SECTION_HEADERS.items():
        if lower in keywords:
            return section
    return None


def _paragraphs(doc: Document) -> list[str]:
    return [p.text.strip() for p in doc.paragraphs if p.text.strip()]


def parse_docx(path: str | Path) -> ResumeData:
    doc = Document(str(path))
    paras = _paragraphs(doc)
    full_text = "\n".join(paras)

    # ── Personal info from full text ─────────────────────────────
    email = m.group() if (m := _EMAIL_RE.search(full_text)) else ""
    phone = m.group() if (m := _PHONE_RE.search(full_text)) else ""
    linkedin = m.group() if (m := _LINKEDIN_RE.search(full_text)) else ""
    github = m.group() if (m := _GITHUB_RE.search(full_text)) else ""

    # Name is heuristically the first non-empty line (usually bold/large in resume)
    name = paras[0] if paras else ""

    # ── Section parsing ──────────────────────────────────────────
    sections: dict[str, list[str]] = {
        "header": [],
        "summary": [],
        "experience": [],
        "education": [],
        "skills": [],
        "certifications": [],
    }
    current = "header"

    for para in paras[1:]:
        detected = _detect_section(para)
        if detected:
            current = detected
            continue
        sections[current].append(para)

    summary = " ".join(sections["summary"])

    skills = _parse_skills(sections["skills"])
    certifications = _parse_certifications(sections["certifications"])
    experience = _parse_experience(sections["experience"])
    education = _parse_education(sections["education"])

    # Location: look in header section lines that aren't email/phone/url
    location = _extract_location(sections["header"], email, phone)

    return ResumeData(
        name=name,
        email=email,
        phone=phone,
        location=location,
        linkedin=f"https://{linkedin}" if linkedin and not linkedin.startswith("http") else linkedin,
        github=f"https://{github}" if github and not github.startswith("http") else github,
        summary=summary,
        experience=experience,
        education=education,
        skills=skills,
        certifications=certifications,
    )


def _extract_location(header_lines: list[str], email: str, phone: str) -> str:
    for line in header_lines:
        if email and email in line:
            continue
        if phone and phone in line:
            continue
        if _URL_RE.search(line):
            continue
        # Simple heuristic: city/state pattern
        if re.search(r"[A-Z][a-z]+,\s*[A-Z]{2}", line):
            return line
        if re.search(r"[A-Z][a-z]+\s+[A-Z][a-z]+,?\s*(NJ|NY|CA|TX|FL|Remote)", line):
            return line
    return ""


def _parse_skills(lines: list[str]) -> list[str]:
    skills: list[str] = []
    for line in lines:
        # Split on common delimiters
        parts = re.split(r"[|,•·/]", line)
        for p in parts:
            s = p.strip()
            if s and len(s) < 60:
                skills.append(s)
    return skills


def _parse_certifications(lines: list[str]) -> list[str]:
    certs: list[str] = []
    for line in lines:
        line = re.sub(r"^[•\-*]\s*", "", line).strip()
        if line:
            certs.append(line)
    return certs


def _parse_experience(lines: list[str]) -> list[ExperienceEntry]:
    """
    Heuristic: lines that look like "Title | Company" or "Title at Company"
    followed by a date range, followed by description bullets.
    """
    entries: list[ExperienceEntry] = []
    current: ExperienceEntry | None = None
    desc_lines: list[str] = []

    date_re = re.compile(
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|"
        r"April|June|July|August|September|October|November|December)[\s,]+\d{4}"
        r"|\d{4}\s*[-–]\s*(\d{4}|Present|Current)",
        re.IGNORECASE,
    )

    def flush() -> None:
        if current:
            current.description = " ".join(desc_lines).strip()
            entries.append(current)

    for line in lines:
        is_date_line = bool(date_re.search(line))
        is_bullet = line.startswith(("•", "-", "*", "–"))

        if is_date_line and current:
            # Attach date to current entry
            dates = date_re.findall(line)
            if dates:
                parts = re.split(r"\s*[-–]\s*", line.strip())
                current.start_date = parts[0].strip() if parts else ""
                current.end_date = parts[1].strip() if len(parts) > 1 else "Present"
        elif "|" in line or " at " in line.lower():
            flush()
            current = ExperienceEntry()
            desc_lines = []
            if "|" in line:
                left, right = line.split("|", 1)
                current.title = left.strip()
                current.company = right.strip()
            else:
                m = re.match(r"(.+?)\s+at\s+(.+)", line, re.IGNORECASE)
                if m:
                    current.title = m.group(1).strip()
                    current.company = m.group(2).strip()
                else:
                    current.title = line
        elif is_bullet and current:
            desc_lines.append(re.sub(r"^[•\-*–]\s*", "", line).strip())
        elif current is None and line and not is_date_line:
            # First non-date line — treat as job title
            current = ExperienceEntry(title=line)
            desc_lines = []

    flush()
    return entries


def _parse_education(lines: list[str]) -> list[EducationEntry]:
    entries: list[EducationEntry] = []
    current: EducationEntry | None = None

    degree_keywords = re.compile(
        r"\b(bachelor|master|associate|b\.?s\.?|m\.?s\.?|b\.?a\.?|m\.?b\.?a\.?|ph\.?d|"
        r"degree|diploma|certificate)\b",
        re.IGNORECASE,
    )
    gpa_re = re.compile(r"GPA[:\s]+(\d\.\d+)", re.IGNORECASE)

    for line in lines:
        if degree_keywords.search(line):
            if current:
                entries.append(current)
            current = EducationEntry(degree=line)
        elif current:
            gpa_m = gpa_re.search(line)
            if gpa_m:
                current.gpa = gpa_m.group(1)
            elif re.search(r"\d{4}", line):
                current.graduation_date = line.strip()
            elif not current.institution:
                current.institution = line.strip()

    if current:
        entries.append(current)
    return entries


# ── Override file ────────────────────────────────────────────────

def load_overrides(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    with p.open() as f:
        return json.load(f)


def save_overrides(path: str | Path, overrides: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w") as f:
        json.dump(overrides, f, indent=2)
