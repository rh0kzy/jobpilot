"""Pydantic models shared across the pipeline."""

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class WorkMode(str, Enum):
    remote = "remote"
    hybrid = "hybrid"
    onsite = "onsite"


class EmploymentType(str, Enum):
    full_time = "full_time"
    part_time = "part_time"
    contract = "contract"
    internship = "internship"


class Education(BaseModel):
    degree: str | None = None
    field: str | None = None
    institution: str | None = None
    start_year: int | None = None
    end_year: int | None = None


class Profile(BaseModel):
    raw_text: str = ""
    name: str | None = None
    skills: list[str] = Field(default_factory=list)
    job_titles: list[str] = Field(default_factory=list)
    years_experience: float | None = None
    seniority: str | None = None
    languages: list[str] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    location: str | None = None


class Preferences(BaseModel):
    work_modes: list[WorkMode] = Field(default_factory=list)
    employment_types: list[EmploymentType] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    seniority_override: str | None = None

    @field_validator("countries", mode="before")
    @classmethod
    def _normalize_countries(cls, value):
        if value is None:
            return []
        return [str(v).strip().upper() for v in value]

    @staticmethod
    def _valid_country(value: str) -> bool:
        value = value.strip().upper()
        if value == "WORLDWIDE":
            return True
        return len(value) == 2 and value.isalpha()

    def model_post_init(self, __context, /) -> None:
        for c in self.countries:
            if not self._valid_country(c):
                raise ValueError(f"Invalid country code: {c}")


class Job(BaseModel):
    title: str
    company: str
    url: str
    source: str
    posted_date: date | None = None
    work_mode: str | None = None
    employment_type: str | None = None
    country: str | None = None
    page_text: str = ""


class SearchResult(BaseModel):
    query: str
    jobs: list[Job] = Field(default_factory=list)
