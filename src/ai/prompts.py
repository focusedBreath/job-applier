CANDIDATE_PROFILE = """You are an intelligent job application assistant.

CANDIDATE PROFILE:
- Name: Vishnu Srinivasan
- Location: South Windsor, CT
- Email: vishnusrnvsn@gmail.com
- Phone: 860-995-4118
- LinkedIn: linkedin.com/in/v-srinivasan1
- Experience: 
  * Associate at Infosys (Java Development)
  * Full-Stack Developer Trainee at Revature
- Skills: Python, Java, Go, Rust, SQL, AWS, Docker, Nmap, Metasploit, OWASP Zap, OSINT, SOC, Firewalls, Cisco, SIEM, Jenkins, CI/CD, Git, Linux
- Education: BS in Cybersecurity, Southern New Hampshire University (May 2024)
- Certifications: CompTIA Security+, AWS Cloud Practitioner
- Preferred Work: Remote or South Windsor CT area
- Salary Expectation: Not specified (flexible for right role)

DECISION RULES:
- APPLY: Role matches skills, legitimate company, reasonable requirements, no red flags
- SKIP: Scam/AI-generated job posts, requires relocation we can't do, extreme salary mismatch, suspicious URLs, asks for payment, vague company
- SAVE: Interesting but need more research, apply later, good company but not perfect match

IMPORTANT: Always respond with ONLY one word: apply, skip, or save"""

FORM_FIELD_PROMPT = """Given the following form field and candidate information, decide the best value to fill.

Form Field Label: {field_label}
Field Type: {field_type}
Available Options: {options}
Resume Data Available: {resume_value}

Respond with ONLY the value to fill in the field, or leave blank if not applicable."""

CUSTOM_QUESTION_PROMPT = """Answer this job application question based on the candidate's profile.

Question: {question}
Job Title: {job_title}
Company: {company}

Candidate Profile Summary:
{resume_summary}

Instructions:
- Write a concise, professional answer (2-3 sentences max)
- Match the answer to the job requirements
- Use first person
- Do not fabricate information

Respond with ONLY the answer text."""

CONFIRMATION_PROMPT = """Review this job application before submission.

Job Title: {job_title}
Company: {company}
Platform: {platform}
Fields to Submit:
{fields}

Candidate Info That Will Be Used:
- Name: Vishnu Srinivasan
- Email: vishnusrnvsn@gmail.com
- Phone: 860-995-4118
- Location: South Windsor, CT
- LinkedIn: linkedin.com/in/v-srinivasan1

Decision Options:
- SUBMIT: Looks good, proceed with submission
- REVIEW: Something needs checking, pause for manual review
- CANCEL: Don't submit this application

Respond with ONLY: submit, review, or cancel"""

CAPTCHA_PROMPT = """CAPTCHA detected during job application.

Type: {captcha_type}
URL: {url}

Options:
- SOLVE: Attempt to solve programmatically (if possible)
- SKIP: Skip this job application
- WAIT: Wait and retry

Respond with ONLY: solve, skip, or wait"""


def get_system_prompt(resume_data=None):
    prompt = CANDIDATE_PROFILE

    if resume_data:
        prompt = prompt.replace(
            "- Experience: \n  * Associate at Infosys (Java Development)\n  * Full-Stack Developer Trainee at Revature",
            _format_experience(resume_data),
        )

    return prompt


def _format_experience(resume_data):
    exp_lines = []
    for exp in resume_data.experience[:3]:
        line = f"  * {exp.title} at {exp.company}"
        if exp.start_date:
            line += f" ({exp.start_date} - {exp.end_date or 'Present'})"
        exp_lines.append(line)

    if not exp_lines:
        exp_lines = [
            "  * Associate at Infosys (Java Development)",
            "  * Full-Stack Developer Trainee at Revature",
        ]

    return "\n".join(exp_lines)


def get_decision_prompt(job_info: dict) -> str:
    return f"""Should I apply to this job?

Job Title: {job_info.get("title", "N/A")}
Company: {job_info.get("company", "N/A")}
Location: {job_info.get("location", "N/A")}

Job Description (first 500 chars):
{job_info.get("description", "N/A")[:500]}

Respond with ONLY: apply, skip, or save"""


def get_form_field_prompt(
    field_label: str, field_type: str, options: list, resume_value: str
) -> str:
    opts = ", ".join(options) if options else "None"
    return FORM_FIELD_PROMPT.format(
        field_label=field_label,
        field_type=field_type,
        options=opts,
        resume_value=resume_value or "Not found in resume",
    )


def get_custom_question_prompt(
    question: str, job_title: str, company: str, resume_summary: str
) -> str:
    return CUSTOM_QUESTION_PROMPT.format(
        question=question,
        job_title=job_title,
        company=company,
        resume_summary=resume_summary or "See candidate profile",
    )


def get_confirmation_prompt(application_data: dict) -> str:
    fields = application_data.get("form_data", {})
    fields_str = "\n".join(f"  - {k}: {v}" for k, v in list(fields.items())[:10])

    return CONFIRMATION_PROMPT.format(
        job_title=application_data.get("title", "N/A"),
        company=application_data.get("company", "N/A"),
        platform=application_data.get("platform", "N/A"),
        fields=fields_str or "  Standard fields",
    )
