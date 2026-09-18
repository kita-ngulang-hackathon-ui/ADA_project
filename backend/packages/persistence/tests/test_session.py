"""session.py tests that need no live database."""
import pytest
from persistence.session import _assert_safe_identifier, make_engine


def test_valid_uuid_passes():
    _assert_safe_identifier("d290f1ee-6c54-4b01-90e6-d701748f0851")


@pytest.mark.parametrize(
    "bad_value",
    [
        "'; DROP TABLE tenants; --",
        "not-a-uuid",
        "",
        "1 OR 1=1",
    ],
)
def test_non_uuid_rejected(bad_value):
    with pytest.raises(ValueError):
        _assert_safe_identifier(bad_value)


def test_make_engine_returns_lazy_engine_without_connecting():
    # create_engine() never opens a connection until first use, so this
    # must succeed even though no Postgres is reachable here.
    engine = make_engine("postgresql+psycopg://user:pass@localhost:5432/db")
    assert engine.url.database == "db"
