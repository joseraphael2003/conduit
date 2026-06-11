import os
import tempfile
import shutil
import pytest_asyncio
import httpx

# Must set OPENAI_API_KEY before importing anything that uses it
os.environ.setdefault("OPENAI_API_KEY", "test-key")

# Import database module before app
import models.database

# Now import app
from main import app

# Clear any real env overrides AFTER dotenv has loaded, so tests use Fireworks defaults
os.environ.pop("FIREWORKS_BASE_URL", None)
os.environ.pop("FIREWORKS_MODEL", None)

# Centralized test isolation: single source of truth for all base-dir modules
from tests.isolation_modules import PATCHED_MODULES
import routers.projects as projects_module

# Save original PROJECTS_BASE_DIR for each patched module
_original_bases = {mod: mod.PROJECTS_BASE_DIR for mod in PATCHED_MODULES}


@pytest_asyncio.fixture
async def temp_projects_dir():
    """Create a temporary projects directory and patch all modules."""
    temp_dir = tempfile.mkdtemp(prefix="test_conduit_projects_")
    for mod in PATCHED_MODULES:
        mod.PROJECTS_BASE_DIR = temp_dir
    # Guard: fail loudly if any module was not patched
    for mod in PATCHED_MODULES:
        assert mod.PROJECTS_BASE_DIR == temp_dir, f"Module {mod.__name__} PROJECTS_BASE_DIR not patched"
    yield temp_dir
    for mod in PATCHED_MODULES:
        mod.PROJECTS_BASE_DIR = _original_bases[mod]
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest_asyncio.fixture
async def test_db(temp_projects_dir):
    """Initialize test database and clean it up after."""
    fd, test_db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    # Remove empty file created by mkstemp so init_db creates a fresh DB
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    # Patch DB_PATH to the isolated temp path
    original_db_path = models.database.DB_PATH
    models.database.DB_PATH = test_db_path
    await models.database.init_db()
    yield test_db_path
    # Cleanup
    models.database.DB_PATH = original_db_path
    if os.path.exists(test_db_path):
        os.remove(test_db_path)


@pytest_asyncio.fixture
async def async_client(test_db):
    """Provide an async HTTP client for in-process testing."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest_asyncio.fixture
async def cleanup_projects(test_db):
    """Clean up test projects from database and filesystem after each test."""
    yield
    # Remove all projects from database
    db = await models.database.get_db()
    try:
        await db.execute("DELETE FROM projects")
        await db.commit()
    finally:
        await db.close()
    # Clean up any remaining directories in temp projects dir
    if os.path.exists(projects_module.PROJECTS_BASE_DIR):
        for item in os.listdir(projects_module.PROJECTS_BASE_DIR):
            item_path = os.path.join(projects_module.PROJECTS_BASE_DIR, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path, ignore_errors=True)


@pytest_asyncio.fixture
async def created_project(async_client, cleanup_projects):
    """Create a project and return its data for dependent tests."""
    response = await async_client.post("/api/v1/projects", json={"name": "Test Project"})
    assert response.status_code == 201, f"Failed to create project: {response.text}"
    data = response.json()
    return data
