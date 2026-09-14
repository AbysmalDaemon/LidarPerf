from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def lo_protocol_data() -> dict:
    data = yaml.safe_load((ROOT / "protocols/lo/se3_v1.yaml").read_text(encoding="utf-8"))
    return deepcopy(data)


@pytest.fixture
def lio_protocol_data() -> dict:
    data = yaml.safe_load((ROOT / "protocols/lio/se3_v1.yaml").read_text(encoding="utf-8"))
    return deepcopy(data)
