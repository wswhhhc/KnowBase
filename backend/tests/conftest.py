from __future__ import annotations

import pytest

from src.api.main import app


@pytest.fixture(autouse=True)
def clear_rate_limiter_between_tests():
    app.state.rate_limiter.clear()
    yield
    app.state.rate_limiter.clear()
