from pathlib import Path

from app.cv.profile_extractor import _normalize_education, extract_profile


class StubProvider:
    def __init__(self, payload):
        self.payload = payload

    async def complete(self, prompt, system=None):
        return self.payload


def test_education_string_and_dict_messy_output_parsed():
    value = [
        {"diploma": "BSc", "major": "Computer Science", "school": "Example University", "years": "2020-2023"},
        "Certification",
    ]
    normalized = _normalize_education(value)
    assert len(normalized) == 2
    assert normalized[0].degree == "BSc"
    assert normalized[0].field == "Computer Science"
    assert normalized[0].institution == "Example University"
    assert normalized[0].start_year == 2020
    assert normalized[0].end_year == 2023
    assert normalized[1].degree == "Certification"


async def test_extract_profile_creates_structured_education():
    payload = """
{
  "name": "Anonymized",
  "skills": ["Python", {"name": "FastAPI"}],
  "job_titles": ["Backend Engineer"],
  "years_experience": "4",
  "seniority": "Mid",
  "languages": ["French", "English"],
  "education": [
    {"degree":"Computer Engineering","institution":"Example USTHB","years":"2023-2028"}
  ],
  "location":"Someplace"
}
"""
    profile = await extract_profile(Path("tests/fixtures/cv_en.pdf").read_bytes().decode("utf-8", errors="ignore"), StubProvider(payload))
    assert profile.name == "Anonymized"
    assert profile.skills == ["Python", "name: FastAPI"]
    assert profile.years_experience == 4.0
    assert len(profile.education) == 1
    edu = profile.education[0]
    assert edu.degree == "Computer Engineering"
    assert edu.institution == "Example USTHB"
    assert edu.start_year == 2023
    assert edu.end_year == 2028