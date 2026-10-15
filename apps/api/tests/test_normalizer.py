from app.core.models import Job
from app.normalize.normalizer import dedupe, normalize_job


def test_normalize_and_dedupe():
    jobs = [
        Job(title="Engineer", company="Acme", url="u1", source="s", page_text="Remote full time", country="de"),
        Job(title="Engineer", company="Acme", url="u2", source="s", page_text="Remote full time", country="de"),
    ]
    norm = [normalize_job(j) for j in jobs]
    out = dedupe(norm)
    assert len(out) == 1