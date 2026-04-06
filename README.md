# Job Applier - AI-Powered Job Application Automation

An intelligent job application automation tool that searches multiple job boards and submits applications with AI oversight.

## Features

- **Multi-platform search**: LinkedIn, Indeed, Monster, and Dice
- **Smart application**: Handles LinkedIn Easy Apply, Workday forms, and generic applications
- **AI oversight**: Every decision is reviewed by an AI agent (that's me!)
- **Rate limiting**: Respects platform limits to avoid bans
- **Anti-detection**: Human-like behavior to avoid bot detection

## Installation

```bash
cd job-applier
pip install -r requirements.txt
playwright install chromium
```

## Configuration

Edit `config.yaml`:

```yaml
search:
  keywords: [SOC, cybersecurity, software engineer]
  locations: [Remote]
  days_back: 7

credentials:
  linkedin_email: "your@email.com"
  linkedin_password: "yourpassword"

resume:
  docx_path: "../Vishnu Srinivasan Resume.docx"
```

## Usage

```bash
# Search only (see what jobs would be found)
python -m src.main --search-only

# Dry run (search + preview applications without submitting)
python -m src.main --dry-run

# Full run (search + apply)
python -m src.main

# Headless mode
python -m src.main --headless

# Specific platforms only
python -m src.main --platforms linkedin indeed
```

## How AI Oversight Works

When running, the system will pause at key decision points:

1. **Job Decision**: Should I apply to this job?
2. **Form Filling**: What should I fill in this custom field?
3. **Custom Questions**: How should I answer this application question?
4. **Confirmation**: Ready to submit?

For each decision, a JSON file is created in the `decisions/` folder. I (the AI agent) will review these and provide responses. The tool waits for my response before proceeding.

## Workflow

1. Parse your resume to extract personal info
2. Search all configured job boards
3. For each job:
   - Show you the job details
   - Fill forms automatically with your resume data
   - Ask me for help with custom questions
   - Submit when ready
4. Generate a report of all applications

## Files

```
job-applier/
├── src/
│   ├── main.py              # Entry point
│   ├── config.py            # Configuration
│   ├── parser/              # Resume parsing
│   ├── scrapers/            # Job board scrapers
│   ├── appliers/            # Application submitters
│   ├── browser/             # Playwright automation
│   ├── ai/                  # AI oversight
│   └── utils/               # Utilities
├── config.yaml              # Your configuration
├── decisions/               # AI decision files (created at runtime)
├── reports/                 # Application reports (created at runtime)
└── sessions/                # Browser sessions (created at runtime)
```

## Legal Notice

- LinkedIn's Terms of Service prohibit automated access
- Use at your own risk
- Some platforms may block automated access
- Consider using dedicated proxies for production use
