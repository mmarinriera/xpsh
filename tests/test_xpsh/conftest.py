import shutil
from pathlib import Path

import pytest

EXAMPLE_FILE_NAME = "example.txt"


def get_resource(file_name: str) -> Path:
    base_dir = Path.cwd()
    return base_dir / "tests" / "resources" / file_name


@pytest.fixture
def example_file_path(tmp_path: Path) -> Path:
    original_path = get_resource(EXAMPLE_FILE_NAME)
    dest_path = tmp_path / EXAMPLE_FILE_NAME
    shutil.copy(original_path, dest_path)
    return dest_path
