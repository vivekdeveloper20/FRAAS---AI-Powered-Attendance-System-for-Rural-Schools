from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RecognitionResult:
    student_id: int
    confidence: float


