from app.connectors.prefilter import matches_role


def test_backend_and_react_native_are_kept():
    roles = ["Full-Stack Developer"]
    assert matches_role("Backend Engineer", [], roles)
    assert matches_role("React Native Developer", ["react-native"], roles)


def test_data_analyst_and_manual_qa_are_dropped_without_skill_match():
    roles = ["Full-Stack Developer"]
    assert not matches_role("Data Analyst", ["sql"], roles)
    assert not matches_role("Manual QA Tester", ["testing"], roles)


def test_tag_matching_profile_skill_keeps_job():
    roles = ["Python", "FastAPI"]
    assert matches_role("Support Engineer", ["python", "fastapi"], roles) is True
