from typing import Literal

from pydantic import BaseModel


class ApplyDecision(BaseModel):
    action: Literal["apply", "skip", "save"]
    reason: str


class FormFieldDecision(BaseModel):
    value: str
    confidence: float = 1.0


class CustomAnswerDecision(BaseModel):
    answer: str


class SubmitDecision(BaseModel):
    action: Literal["submit", "review", "cancel"]
    reason: str


# Fallback defaults used when Claude is unavailable or times out
FALLBACK_APPLY = ApplyDecision(action="apply", reason="AI unavailable — defaulting to apply")
FALLBACK_SUBMIT = SubmitDecision(action="submit", reason="AI unavailable — defaulting to submit")
FALLBACK_FIELD = FormFieldDecision(value="", confidence=0.0)
FALLBACK_ANSWER = CustomAnswerDecision(answer="")
