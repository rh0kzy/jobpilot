from app.core.models import Job
from app.normalize.normalizer import normalize_job


def _norm(location, **fields):
    job = Job(title="Backend Engineer", company="Acme", url="https://example.com/job/1", source="example.com", location=location, **fields)
    return normalize_job(job)


def test_accenture_suitland_md():
    job = _norm("Suitland, MD")
    assert job.remote_scope == "country_restricted"
    assert job.allowed_countries == ["US"]
    assert job.country == "US"
    assert job.eligibility_evidence


def test_ivanti_united_states_remote():
    job = _norm("United States, Remote")
    assert job.remote_scope == "country_restricted"
    assert job.allowed_countries == ["US"]


def test_everbridge_bengaluru():
    job = _norm("Bengaluru")
    assert job.remote_scope == "country_restricted"
    assert job.allowed_countries == ["IN"]


def test_melotech_berlin():
    job = _norm("Berlin")
    assert job.remote_scope == "country_restricted"
    assert job.allowed_countries == ["DE"]


def test_bjak_ireland():
    job = _norm("Ireland")
    assert job.remote_scope == "country_restricted"
    assert job.allowed_countries == ["IE"]


def test_owl_co_and_leap_tools_toronto():
    for _ in ("Owl.co", "Leap Tools"):
        job = _norm("Toronto")
        assert job.remote_scope == "country_restricted"
        assert job.allowed_countries == ["CA"]


def test_pulse_mena_arabic_location():
    job = _norm("المنطقة MENA")
    assert job.remote_scope == "region_restricted"
    assert job.allowed_regions == "MENA"
    assert job.allowed_countries == []
    assert job.eligibility_evidence


def test_freelance_worldwide_location():
    job = _norm("Worldwide")
    assert job.remote_scope == "worldwide"
    assert job.allowed_countries == []
    assert job.country == "unspecified"
    assert job.allowed_regions == "Worldwide"


def test_gitlab_multi_country():
    job = _norm("Canada, Poland and the UK")
    assert job.remote_scope == "country_restricted"
    assert set(job.allowed_countries) == {"CA", "PL", "GB"}
    assert job.eligibility_evidence


def test_non_english_country_names_are_mapped():
    for location, expected in [("Italia", "IT"), ("España", "ES"), ("Polska", "PL"), ("Deutschland", "DE"), ("Perú", "PE")]:
        job = _norm(location)
        assert job.remote_scope == "country_restricted"
        assert job.allowed_countries == [expected], (location, job.allowed_countries)


def test_same_location_is_deterministic():
    first = _norm("Toronto")
    second = _norm("Toronto")
    assert first.remote_scope == second.remote_scope
    assert first.allowed_countries == second.allowed_countries
    assert first.country == second.country


def test_no_evidence_without_explicit_worldwide_is_not_worldwide():
    job = _norm("Ukraine")
    assert job.remote_scope == "country_restricted"
    job2 = Job(title="x", company="y", url="u", source="s")
    assert normalize_job(job2).remote_scope == "unclear"
