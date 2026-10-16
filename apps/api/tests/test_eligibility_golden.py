from app.core.models import Job
from app.normalize.normalizer import normalize_job


def _job(location, work_mode=None, **fields):
    return Job(title="Backend Engineer", company="Acme", url="https://example.com/job/1", source="example.com", location=location, work_mode=work_mode, **fields)


def test_remote_city_only_is_unclear_with_hint():
    for location, hint in [("Toronto", "CA"), ("Warsaw", "PL"), ("Bengaluru", "IN"), ("Berlin", "DE"), ("Ireland", "IE")]:
        job = _job(location, work_mode="remote")
        n = normalize_job(job)
        assert n.remote_scope == "unclear", (location, n.remote_scope)
        assert n.location_hint == hint, (location, n.location_hint)


def test_explicit_remote_single_country_is_restricted():
    job = _job("Remote - Canada", work_mode="remote")
    n = normalize_job(job)
    assert n.remote_scope == "country_restricted"
    assert n.allowed_countries == ["CA"]
    assert n.location_hint is None
    assert "Remote - Canada" in (n.eligibility_evidence or "")


def test_gitlab_explicit_multi_country():
    job = _job("Remote, Canada; Remote, Poland; Remote, United Kingdom", work_mode="remote", allowed_countries=["CA", "PL", "GB"])
    n = normalize_job(job)
    assert n.remote_scope == "country_restricted"
    assert set(n.allowed_countries) == {"CA", "PL", "GB"}
    assert "CA, PL, GB" not in (n.eligibility_evidence or "")
    assert "Remote" in (n.eligibility_evidence or "")


def test_fully_remote_is_unclear():
    job = _job("Fully Remote", work_mode="remote")
    n = normalize_job(job)
    assert n.remote_scope == "unclear"


def test_worldwide_is_worldwide():
    job = _job("Worldwide", work_mode="remote")
    n = normalize_job(job)
    assert n.remote_scope == "worldwide"


def test_onsite_city_is_location_bound():
    job = _job("Suitland, MD", work_mode="onsite")
    n = normalize_job(job)
    assert n.remote_scope == "location_bound"
    assert n.country == "US"


def test_non_english_country_names_are_hint_when_remote_city_only():
    for location, hint in [("Italia", "IT"), ("España", "ES"), ("Polska", "PL"), ("Deutschland", "DE"), ("Perú", "PE")]:
        job = _job(location, work_mode="remote")
        n = normalize_job(job)
        assert n.remote_scope == "unclear", (location, n.remote_scope)
        assert n.location_hint == hint, (location, n.location_hint)


def test_pulse_mena_region():
    job = _job("MENA", work_mode="remote", allowed_regions="MENA")
    n = normalize_job(job)
    assert n.remote_scope == "region_restricted"
    assert n.allowed_regions == "MENA"


def test_no_codes_as_evidence_country_restricted():
    job = _job("Remote - Canada", work_mode="remote")
    n = normalize_job(job)
    assert n.eligibility_evidence == "Remote - Canada"
