"""Fixtures.

The legacy tables are built from the same ``.sql`` files the demo uses, inside
the transaction pytest-django wraps each test in, so they disappear on rollback
and no test can see another's rows. Building them from SQL rather than from a
migration is the point: Django does not own this schema, and the suite should
be reading the same description a DBA would hand over.
"""

from __future__ import annotations

import pytest

from legacy import schema


@pytest.fixture
def legacy_db(db: None) -> None:
    """The legacy schema, seeded."""
    schema.reset(seed=True)


@pytest.fixture
def empty_legacy_db(db: None) -> None:
    """The legacy schema with no rows, for tests that insert their own."""
    schema.reset(seed=False)
