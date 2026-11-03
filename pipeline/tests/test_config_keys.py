"""Configuration must not silently replace a language pack or nested family."""
import pytest
import yaml

from anthrion_signal.config import UniqueKeyLoader


@pytest.mark.parametrize("text", [
    "fr:\n  crm: [premier]\nfr:\n  portals: [second]\n",
    "nl:\n  crm: [eerste]\n  crm: [tweede]\n",
])
def test_duplicate_configuration_keys_fail_explicitly(text):
    with pytest.raises(ValueError, match="Duplicate configuration key"):
        yaml.load(text, Loader=UniqueKeyLoader)


def test_same_family_in_different_languages_remains_valid():
    value = yaml.load("fr:\n  crm: [relation client]\nnl:\n  crm: [klantrelatiebeheer]\n", Loader=UniqueKeyLoader)
    assert value == {"fr": {"crm": ["relation client"]}, "nl": {"crm": ["klantrelatiebeheer"]}}
