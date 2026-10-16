from app.connectors.prefilter import matches_role


def test_role_match_accepts_title_variants():
    roles = ["Full-Stack Developer", "Frontend Developer"]
    assert matches_role("Full Stack Engineer", ["react"], roles)
    assert matches_role("Frontend Developer", ["typescript"], roles)


def test_role_match_rejects_unrelated_titles_with_generic_tags():
    roles = ["Full-Stack Developer"]
    assert not matches_role("Remote Office Assistant", ["frontend", "css"], roles)


def test_no_targets_keeps_feed_item():
    assert matches_role("Anything", [])