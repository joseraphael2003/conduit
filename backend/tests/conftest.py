import os
import tempfile
import shutil
import pytest_asyncio
import httpx

# Must set OPENAI_API_KEY before importing anything that uses it
os.environ.setdefault("OPENAI_API_KEY", "test-key")

# Patch database path before any imports that use it
import models.database

_original_db_path = models.database.DB_PATH

test_db_path = os.path.join(tempfile.gettempdir(), "test_conduit.db")
models.database.DB_PATH = test_db_path

# Now import app
from main import app

# Patch projects base dir in routers.projects, services.state, and routers.segments
import routers.projects as projects_module
import services.state as state_module
import routers.segments as segments_module

_original_projects_base = projects_module.PROJECTS_BASE_DIR
_original_state_base = state_module.PROJECTS_BASE_DIR
_original_segments_base = segments_module.PROJECTS_BASE_DIR


@pytest_asyncio.fixture
async def temp_projects_dir():
    """Create a temporary projects directory and patch all modules."""
    temp_dir = tempfile.mkdtemp(prefix="test_conduit_projects_")
    projects_module.PROJECTS_BASE_DIR = temp_dir
    state_module.PROJECTS_BASE_DIR = temp_dir
    segments_module.PROJECTS_BASE_DIR = temp_dir
    yield temp_dir
    projects_module.PROJECTS_BASE_DIR = _original_projects_base
    state_module.PROJECTS_BASE_DIR = _original_state_base
    segments_module.PROJECTS_BASE_DIR = _original_segments_base
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest_asyncio.fixture
async def test_db(temp_projects_dir):
    """Initialize test database and clean it up after."""
    # Remove old test db if it exists
    if os.path.exists(models.database.DB_PATH):
        os.remove(models.database.DB_PATH)
    await models.database.init_db()
    yield models.database.DB_PATH
    # Cleanup
    if os.path.exists(models.database.DB_PATH):
        os.remove(models.database.DB_PATH)


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
