import retasc.validator.config as config


def test_schema_version_exists():
    assert hasattr(
        config, "SCHEMA_VERSION"
    ), "SCHEMA_VERSION is not defined in the config module"
