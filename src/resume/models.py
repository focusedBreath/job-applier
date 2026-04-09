from pydantic import BaseModel


class ExperienceEntry(BaseModel):
    title: str = ""
    company: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""


class EducationEntry(BaseModel):
    degree: str = ""
    institution: str = ""
    graduation_date: str = ""
    gpa: str = ""


class ResumeData(BaseModel):
    # Personal
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    github: str = ""
    website: str = ""

    # Profile
    summary: str = ""

    # Experience
    experience: list[ExperienceEntry] = []
    total_years_experience: str = ""

    # Education
    education: list[EducationEntry] = []

    # Skills & certs
    skills: list[str] = []
    certifications: list[str] = []

    def merged(self, overrides: dict) -> "ResumeData":
        """Return a copy of this ResumeData with override values applied."""
        data = self.model_dump()
        for key, value in overrides.items():
            if key in data:
                data[key] = value
        return ResumeData(**data)
