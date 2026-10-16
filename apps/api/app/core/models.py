"""Pydantic models shared across the pipeline."""

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class WorkMode(str, Enum):
    remote = "remote"
    hybrid = "hybrid"
    onsite = "onsite"
    unspecified = "unspecified"


class EmploymentType(str, Enum):
    full_time = "full_time"
    part_time = "part_time"
    contract = "contract"
    internship = "internship"
    unspecified = "unspecified"


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
    residence_country: str | None = None
    authorized_countries: list[str] = Field(default_factory=list)

    @field_validator("countries", mode="before")
    @classmethod
    def _normalize_countries(cls, value):
        if value is None:
            return []
        return [str(v).strip().upper() for v in value]

    @field_validator("residence_country", mode="before")
    @classmethod
    def _normalize_residence(cls, value):
        if value is None:
            return None
        value = str(value).strip().upper()
        if value == "":
            return None
        if value == "WORLDWIDE":
            return value
        if len(value) != 2 or not value.isalpha():
            raise ValueError(f"Invalid residence country code: {value}")
        return value

    @field_validator("authorized_countries", mode="before")
    @classmethod
    def _normalize_authorized(cls, value):
        if value is None:
            return []
        out = []
        for v in value:
            code = str(v).strip().upper()
            if code == "":
                continue
            out.append(code)
        return out

    @staticmethod
    def _valid_country(value: str) -> bool:
        value = value.strip().upper()
        if value in {"WORLDWIDE", "UNSPECIFIED"}:
            return True
        return len(value) == 2 and value.isalpha()

    def model_post_init(self, __context, /) -> None:
        for c in self.countries:
            if not self._valid_country(c):
                raise ValueError(f"Invalid country code: {c}")
        for c in self.authorized_countries:
            if not self._valid_country(c):
                raise ValueError(f"Invalid authorized country code: {c}")
        if not self.authorized_countries and self.residence_country is not None:
            self.authorized_countries = [self.residence_country]

    # Compatibility aliases for alternate naming used in prompts/tests.
    @property
    def country_of_residence(self) -> str | None:
        return self.residence_country

    @property
    def work_authorization_countries(self) -> list[str]:
        return self.authorized_countries

    @property
    def work_countries(self) -> list[str]:
        return self.authorized_countries

    @property
    def authorized_locations(self) -> list[str]:
        return self.authorized_countries


class Job(BaseModel):
    title: str
    company: str
    url: str
    source: str
    posted_date: date | None = None
    work_mode: str | None = None
    employment_type: str | None = None
    location: str | None = None
    country: str | None = None
    remote_scope: str | None = None
    allowed_countries: list[str] = Field(default_factory=list)
    allowed_regions: str | None = None
    timezone_restriction: str | None = None
    work_authorization_required: str | None = None
    eligibility_evidence: str | None = None
    location_hint: str | None = None
    seniority: str | None = None
    seniority_level: str | None = None
    original_url: str | None = None
    url_verified: bool = False
    url_verification_status: str | None = None
    page_type: str | None = None
    confidence: float | None = None
    freshness_status: str | None = None
    page_text: str = ""

    # Compatibility alias removed field name from Phase 1; keep reads from old fixtures returning None.
    @property
    def remote_eligibility(self) -> str | None:
        return None


class SearchResult(BaseModel):
    query: str
    jobs: list[Job] = Field(default_factory=list)
