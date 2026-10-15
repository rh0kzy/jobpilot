from app.filters.liveness import is_live, register_closed_phrase


def test_closed_phrases_multilingual():
    assert not is_live("This position has been filled")
    assert not is_live("Poste pourvu")
    assert not is_live("الوظيفة مغلقة")


def test_open_job():
    assert is_live("Apply now for this role")


def test_extendable():
    register_closed_phrase("custom closed")
    assert not is_live("This is custom closed")