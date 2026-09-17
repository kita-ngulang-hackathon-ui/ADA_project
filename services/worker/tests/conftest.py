"""Worker test fixtures. Helpers live in worker_world.py (importlib import mode needs the path)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from worker_world import build_store, make_settings


@pytest.fixture
def store():
    return build_store()


@pytest.fixture
def settings():
    return make_settings()
