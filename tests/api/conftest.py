import pytest
from fastapi.testclient import TestClient

from api.deps import get_db_path
from api.main import app

# Real-secrets isolation (previously a local _no_real_secrets fixture here) now
# lives as an autouse fixture in the root tests/conftest.py, applying to every
# test in the suite instead of just this directory.


@pytest.fixture
def client(db_path):
    app.dependency_overrides[get_db_path] = lambda: db_path
    yield TestClient(app)
    app.dependency_overrides.clear()
