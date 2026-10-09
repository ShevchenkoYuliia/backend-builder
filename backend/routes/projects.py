from datetime import UTC, datetime

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from database import projects_collection
from dependencies import get_current_user
from schemas import DeleteResponse, ProjectRecord, ProjectSchema, UserPublic


router = APIRouter()


def _to_object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid project id.",
        ) from exc


def _serialize_project(doc: dict) -> ProjectRecord:
    return ProjectRecord(
        id=str(doc["_id"]),
        owner_id=str(doc["owner_id"]),
        name=doc["name"],
        description=doc.get("description", ""),
        db_type=doc["db_type"],
        entities=doc.get("entities", []),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


@router.get("/", response_model=list[ProjectRecord])
async def list_projects(user: UserPublic = Depends(get_current_user)) -> list[ProjectRecord]:
    projects: list[ProjectRecord] = []
    cursor = projects_collection.find({"owner_id": user.id}).sort("updated_at", -1)
    async for doc in cursor:
        projects.append(_serialize_project(doc))
    return projects


@router.get("/{project_id}", response_model=ProjectRecord)
async def get_project(
    project_id: str,
    user: UserPublic = Depends(get_current_user),
) -> ProjectRecord:
    doc = await projects_collection.find_one(
        {"_id": _to_object_id(project_id), "owner_id": user.id}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Project not found.")
    return _serialize_project(doc)


@router.post("/", status_code=201, response_model=ProjectRecord)
async def create_project(
    project: ProjectSchema,
    user: UserPublic = Depends(get_current_user),
) -> ProjectRecord:
    now = datetime.now(UTC)
    payload = project.model_dump(mode="json")
    payload.update(
        {
            "owner_id": user.id,
            "created_at": now,
            "updated_at": now,
        }
    )
    result = await projects_collection.insert_one(payload)
    created = await projects_collection.find_one({"_id": result.inserted_id})
    return _serialize_project(created)


@router.put("/{project_id}", response_model=ProjectRecord)
async def update_project(
    project_id: str,
    project: ProjectSchema,
    user: UserPublic = Depends(get_current_user),
) -> ProjectRecord:
    existing = await projects_collection.find_one(
        {"_id": _to_object_id(project_id), "owner_id": user.id}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Project not found.")

    payload = project.model_dump(mode="json")
    payload["updated_at"] = datetime.now(UTC)
    await projects_collection.update_one(
        {"_id": existing["_id"]},
        {"$set": payload},
    )
    updated = await projects_collection.find_one({"_id": existing["_id"]})
    return _serialize_project(updated)


@router.delete("/{project_id}", response_model=DeleteResponse)
async def delete_project(
    project_id: str,
    user: UserPublic = Depends(get_current_user),
) -> DeleteResponse:
    result = await projects_collection.delete_one(
        {"_id": _to_object_id(project_id), "owner_id": user.id}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Project not found.")
    return DeleteResponse()
