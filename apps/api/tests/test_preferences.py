from app.core.models import Preferences


def test_preferences_country_normalization():
    p = Preferences(countries=["fr", "worldwide", "US"])
    assert p.countries == ["FR", "WORLDWIDE", "US"]


def test_preferences_invalid_country():
    import pytest

    with pytest.raises(ValueError):
        Preferences(countries=["France"])