import os
import json
import uuid as uuid_module
from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Response, UploadFile, File
from models.project import ProjectCreate, ProjectResponse, ProjectListResponse
from models.database import get_db
from models.state import ProjectState
from services.state import update_state, invalidate_downstream, get_state, STATE_ORDER, get_state_index
from services.whisper import transcribe_audio

projects_router = APIRouter()

PROJECTS_BASE_DIR = os.path.join("..", "projects")


def create_project_directory(project_uuid: str) -> None:
    """Create the project directory tree and metadata files."""
    project_dir = os.path.join(PROJECTS_BASE_DIR, project_uuid)
    images_dir = os.path.join(project_dir, "images")
    output_dir = os.path.join(project_dir, "output")
    conduit_dir = os.path.join(project_dir, ".conduit")

    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(conduit_dir, exist_ok=True)

    project_metadata = {
        "uuid": project_uuid,
        "created_at": datetime.utcnow().isoformat(),
    }
    project_json_path = os.path.join(conduit_dir, "project.json")
    with open(project_json_path, "w", encoding="utf-8") as f:
        json.dump(project_metadata, f, indent=2)

    state_metadata = {
        "uuid": project_uuid,
        "state": "created",
        "updated_at": datetime.utcnow().isoformat(),
    }
    state_json_path = os.path.join(conduit_dir, "state.json")
    with open(state_json_path, "w", encoding="utf-8") as f:
        json.dump(state_metadata, f, indent=2)


@projects_router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(project: ProjectCreate):
    """Create a new project with auto-generated UUID and directory tree."""
    project_uuid = str(uuid_module.uuid4())
    now = datetime.utcnow().isoformat()

    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO projects (uuid, name, state, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (project_uuid, project.name, "created", now, now),
        )
        await db.commit()
    finally:
        await db.close()

    create_project_directory(project_uuid)

    return ProjectResponse(
        uuid=project_uuid,
        name=project.name,
        state="created",
        created_at=now,
        updated_at=now,
    )


@projects_router.get("/projects", response_model=ProjectListResponse)
async def list_projects():
    """List all projects."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT uuid, name, state, created_at, updated_at FROM projects ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()

    projects = [
        ProjectResponse(
            uuid=row[0],
            name=row[1],
            state=row[2],
            created_at=row[3],
            updated_at=row[4],
        )
        for row in rows
    ]

    return ProjectListResponse(projects=projects)


@projects_router.get("/projects/{project_uuid}", response_model=ProjectResponse)
async def get_project(project_uuid: str):
    """Get a single project by UUID."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT uuid, name, state, created_at, updated_at FROM projects WHERE uuid = ?",
            (project_uuid,),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    return ProjectResponse(
        uuid=row[0],
        name=row[1],
        state=row[2],
        created_at=row[3],
        updated_at=row[4],
    )


@projects_router.delete("/projects/{project_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_uuid: str):
    """Delete a project by UUID and remove its directory tree."""
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM projects WHERE uuid = ?", (project_uuid,))
        await db.commit()
        deleted_rows = cursor.rowcount
    finally:
        await db.close()

    if deleted_rows == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    project_dir = os.path.join(PROJECTS_BASE_DIR, project_uuid)
    if os.path.exists(project_dir):
        import shutil
        shutil.rmtree(project_dir)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@projects_router.put("/projects/{project_uuid}/step/{step_number}", response_model=ProjectResponse)
async def update_step(project_uuid: str, step_number: int):
    """Complete a step for a project."""
    if step_number < 1 or step_number > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid step number",
        )

    state_map = {
        1: ProjectState.STEP_1_COMPLETE,
        2: ProjectState.STEP_2_COMPLETE,
        3: ProjectState.STEP_3_COMPLETE,
        4: ProjectState.STEP_4_COMPLETE,
        5: ProjectState.STEP_5_COMPLETE,
    }
    target_state = state_map[step_number]

    current_state = await get_state(project_uuid)
    current_idx = get_state_index(current_state)
    target_idx = get_state_index(target_state)

    # If current state is already at or beyond the target, data is being modified
    if current_idx >= target_idx:
        await invalidate_downstream(project_uuid, step_number)

    # Update state to the target
    updated_state = await update_state(project_uuid, target_state)

    # Return updated project
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT uuid, name, state, created_at, updated_at FROM projects WHERE uuid = ?",
            (project_uuid,),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return ProjectResponse(
        uuid=row[0],
        name=row[1],
        state=row[2],
        created_at=row[3],
        updated_at=row[4],
    )


@projects_router.get("/projects/{project_uuid}/state")
async def get_project_state(project_uuid: str):
    """Get the current state of a project."""
    state = await get_state(project_uuid)
    return {"state": state.value}


@projects_router.post("/projects/{project_uuid}/voiceover", status_code=status.HTTP_202_ACCEPTED)
async def upload_voiceover(project_uuid: str, file: UploadFile = File(...)):
    """Upload a voiceover audio file for transcription."""
    # Validate file type
    allowed_extensions = {".mp3", ".wav", ".m4a"}
    file_ext = os.path.splitext(file.filename or "")[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Accepted: {', '.join(allowed_extensions)}",
        )

    # Ensure project directory exists
    project_dir = os.path.join(PROJECTS_BASE_DIR, project_uuid)
    if not os.path.exists(project_dir):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Save uploaded file
    voiceover_path = os.path.join(project_dir, f"voiceover{file_ext}")
    with open(voiceover_path, "wb") as f:
        content = await file.read()
        f.write(content)

    return {
        "processing": True,
        "message": "Audio uploaded. Transcription in progress.",
    }


@projects_router.get("/projects/{project_uuid}/status")
async def get_project_status(project_uuid: str):
    """Get the processing status of a project."""
    state = await get_state(project_uuid)
    state_value = state.value
    if state_value == "created":
        return {"state": "processing"}
    return {"state": state_value}
