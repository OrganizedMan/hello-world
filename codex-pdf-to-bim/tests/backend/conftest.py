from pathlib import Path
from io import BytesIO
import hashlib

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from hearthview_api.config import AppConfig
from hearthview_api.main import create_app
from hearthview.events import ProjectRepository
from hearthview.storage import ArtifactStore


@pytest.fixture
def artifact_store(tmp_path: Path) -> ArtifactStore:
    return ArtifactStore(tmp_path / "artifacts")


@pytest.fixture
def repository(tmp_path: Path) -> ProjectRepository:
    return ProjectRepository(tmp_path / "hearthview.sqlite3")


@pytest.fixture
def one_page_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.fixture
def four_page_pdf() -> bytes:
    writer = PdfWriter()
    for _page in range(4):
        writer.add_blank_page(width=2448, height=3168)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.fixture
def client(tmp_path: Path, four_page_pdf: bytes) -> TestClient:
    return TestClient(create_app(AppConfig(
        data_root=tmp_path / "app-data",
        supported_source_sha256=hashlib.sha256(four_page_pdf).hexdigest(),
    )))
