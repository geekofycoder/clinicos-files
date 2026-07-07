from typing import Optional
from pydantic import BaseModel


class Vitals(BaseModel):
    bp_systolic_mmhg: Optional[int] = None
    bp_diastolic_mmhg: Optional[int] = None
    pulse_bpm: Optional[int] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    temperature_c: Optional[float] = None
    bmi: Optional[float] = None


class Complaint(BaseModel):
    text: str
    entry_type: str = "free_text"
    code: None = None


class Diagnosis(BaseModel):
    text: str
    entry_type: str = "free_text"
    code: None = None


class Dosage(BaseModel):
    frequency_code: Optional[str] = None   # OD|BD|TDS|QID|HS|SOS|STAT
    dose_pattern: Optional[str] = None     # e.g. 1-0-1
    timing: Optional[str] = None           # before_food|after_food|with_food|empty_stomach
    duration_days: Optional[int] = None
    route: Optional[str] = None            # PO|IV|IM|SC|topical


class Medication(BaseModel):
    text: str
    entry_type: str = "free_text"
    dosage: Optional[Dosage] = None


class Investigation(BaseModel):
    text: str
    entry_type: str = "free_text"
    is_panel: bool = False
    fasting_required: bool = False


class FollowUp(BaseModel):
    date: Optional[str] = None
    reason: Optional[str] = None


class VaccineItem(BaseModel):
    vaccine: str
    flagged: bool = False
    eligibility_note: Optional[str] = None


class Prescription(BaseModel):
    vitals: Vitals
    chief_complaints: list[Complaint]
    diagnoses: list[Diagnosis]
    medications: list[Medication]
    advice: Optional[str] = None
    investigations: list[Investigation]
    follow_up: Optional[FollowUp] = None
    vaccine_checklist: list[VaccineItem]
