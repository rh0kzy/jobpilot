from app.core.models import Preferences


def test_preferences_country_normalization():
    p = Preferences(countries=["fr", "worldwide", "US"])
    assert p.countries == ["FR", "WORLDWIDE", "US"]


def test_preferences_invalid_country():
    import pytest

    with pytest.raises(ValueError):
        Preferences(countries=["France"])

def test_residence_country_validation():
    import pytest

    from app.core.models import Preferences

    bad = ["F", "FRANCE", "12"]
    for value in bad:
        with pytest.raises(ValueError):
            Preferences(residence_country=value)

    valid = Preferences(residence_country="dz", authorized_countries=[])
    assert valid.residence_country == "DZ"
    assert valid.authorized_countries == ["DZ"]


def test_authorized_countries_validation():
    import pytest

    from app.core.models import Preferences

    with pytest.raises(ValueError):
        Preferences(residence_country="DZ", authorized_countries=["France"])
