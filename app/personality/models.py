"""Data models and schemas for the JARVIS personality subsystem."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class OperatingMode(str, Enum):
    """Supported personality and operational modes."""

    NORMAL = "normal"
    CODING = "coding"
    STUDY = "study"
    RESEARCH = "research"
    PROFESSIONAL = "professional"
    EMERGENCY = "emergency"

    @classmethod
    def from_str(cls, value: str) -> OperatingMode:
        """Parse string to OperatingMode safely."""
        clean = value.strip().lower()
        for mode in cls:
            if mode.value == clean or mode.name.lower() == clean:
                return mode
        raise ValueError(f"Invalid operating mode: '{value}'. Valid: {[m.value for m in cls]}")


class PersonalityTraits(BaseModel):
    """Quantitative and qualitative personality dimensions."""

    humor: float = Field(default=0.6, ge=0.0, le=1.0, description="Witty banter and playfulness (0.0 to 1.0)")
    sarcasm: float = Field(default=0.4, ge=0.0, le=1.0, description="Irony and dry British sarcasm (0.0 to 1.0)")
    formality: float = Field(default=0.7, ge=0.0, le=1.0, description="Adherence to formal etiquette (0.0 to 1.0)")
    warmth: float = Field(default=0.6, ge=0.0, le=1.0, description="Empathy, friendliness, and approachability (0.0 to 1.0)")
    verbosity: float = Field(default=0.4, ge=0.0, le=1.0, description="Detail and length of responses (0.0 to 1.0)")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="Assertiveness and certainty (0.0 to 1.0)")
    proactivity: float = Field(default=0.5, ge=0.0, le=1.0, description="Propensity to offer forward guidance (0.0 to 1.0)")
    preferred_address: str = Field(default="sir", description="Preferred salutation for the user")
    response_style: str = Field(default="concise", description="Style preference: concise, detailed, bulleted")

    def copy_with_overrides(self, overrides: Dict[str, Any]) -> PersonalityTraits:
        """Return a new PersonalityTraits instance with given attribute overrides applied."""
        current_data = self.model_dump()
        current_data.update(overrides)
        return PersonalityTraits(**current_data)


class ModeProfile(BaseModel):
    """Definition of an operating mode with prompt directives and trait overrides."""

    name: str
    mode: OperatingMode
    description: str
    directives: List[str] = Field(default_factory=list)
    trait_overrides: Dict[str, float] = Field(default_factory=dict)
