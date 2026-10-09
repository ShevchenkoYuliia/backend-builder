import io
import json
import os
import socket
import subprocess
import tempfile
import time
import zipfile

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from dependencies import get_current_user
from database import users_collection
from schemas import ProjectSchema, UserPublic
from security import decrypt_secret
from services.generator import generate_project, snake_case
from services.validator import build_validation_report
from services.llm_service import generate_custom_endpoint


router = APIRouter()


async def _ai_settings_for_user(user: UserPublic) -> dict:
    user_doc = await users_collection.find_one({"email": user.email})
    settings = (user_doc or {}).get("ai_settings", {})
    encrypted_api_key = settings.get("encrypted_api_key")
    return {
        "provider": settings.get("provider", "ollama"),
        "model": settings.get("model", "llama3.1"),
        "api_key": decrypt_secret(encrypted_api_key) if encrypted_api_key else "",
        "base_url": settings.get("base_url"),
    }


@router.post("/")
async def generate(
    project: ProjectSchema,
    user: UserPublic = Depends(get_current_user),
):
    report = build_validation_report(project)
    if not report.valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Project validation failed.",
                "issues": report.model_dump(mode="json")["issues"],
            },
        )

    start_time = time.time()
    files, compile_success = await generate_project(
        project,
        await _ai_settings_for_user(user),
    )
    files["project-spec.json"] = json.dumps(project.model_dump(mode="json"), indent=2)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    zip_buffer.seek(0)
    generation_time = round(time.time() - start_time, 2)

    filename = f"{project.name.lower().replace(' ', '_')}_backend.zip"
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "X-Generated-For": user.email,
            "X-Generation-Time-Sec": str(generation_time),
            "X-Compile-Success": "true" if compile_success else "false",
            "Access-Control-Expose-Headers": "X-Generation-Time-Sec, X-Compile-Success",
        },
    )

@router.post("/deploy")
async def deploy_project(
    project: ProjectSchema,
    user: UserPublic = Depends(get_current_user),
):
    report = build_validation_report(project)
    if not report.valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Project validation failed."},
        )

    start_time = time.time()
    files, compile_success = await generate_project(
        project,
        await _ai_settings_for_user(user),
    )
    generation_time = round(time.time() - start_time, 2)
    if not compile_success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Syntax compilation failed for the generated project."},
        )

    project_slug = snake_case(project.name)
    deploy_dir = tempfile.mkdtemp(prefix=f"ai_deploy_{project_slug}_")
    for path, content in files.items():
        full_path = os.path.join(deploy_dir, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

    env_path = os.path.join(deploy_dir, ".env")
    with open(env_path, "a", encoding="utf-8") as f:
        f.write(f"\nROOT_PATH=/{project_slug}\n")

    nginx_conf_path = os.path.join("/app/nginx_locations", f"{project_slug}.conf")
    nginx_conf_content = f"""
location /{project_slug}/ {{
    resolver 127.0.0.11 valid=5s;
    set $upstream_app {project_slug}_app;
    rewrite ^/{project_slug}/(.*) /$1 break;
    proxy_pass http://$upstream_app:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}}
"""
    try:
        os.makedirs("/app/nginx_locations", exist_ok=True)
        with open(nginx_conf_path, "w", encoding="utf-8") as f:
            f.write(nginx_conf_content)
    except Exception as e:
        print(f"Warning: could not write Nginx conf, running without Nginx reverse proxy? Error: {e}")

    try:
        env_vars = os.environ.copy()

        subprocess.run(
            ["docker-compose", "-p", project_slug, "up", "-d", "--build"],
            cwd=deploy_dir,
            env=env_vars,
            check=True,
            capture_output=True,
            text=True
        )

        subprocess.run(
            ["docker", "exec", "nginx_proxy", "nginx", "-s", "reload"],
            check=False,
            capture_output=True,
            text=True
        )

    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Docker deployment failed: {e.stderr}"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Docker deployment failed: {str(e)}"
        )

    return {
        "status": "deployed",
        "url": f"http://localhost/{project_slug}/docs",
        "generationTime": generation_time,
        "compileSuccess": True,
    }


@router.post("/endpoints")
async def generate_endpoints(
    project: ProjectSchema,
    user: UserPublic = Depends(get_current_user),
):
    ai_settings = await _ai_settings_for_user(user)
    start_time = time.time()
    total_tokens = 0
    success = True

    for entity in project.entities:
        for endpoint in entity.custom_endpoints:
            try:
                code, tokens = await generate_custom_endpoint(
                    entity_name=entity.name,
                    method=endpoint.method,
                    path=endpoint.path,
                    description=endpoint.description,
                    db_type=project.db_type.value,
                    entity_slug=snake_case(entity.name),
                    provider=ai_settings.get("provider", "ollama"),
                    model=ai_settings.get("model", "llama3.1"),
                    api_key=ai_settings.get("api_key", ""),
                    base_url=ai_settings.get("base_url"),
                )
                endpoint.code = code
                total_tokens += tokens
            except Exception as e:
                print(f"Error generating endpoint {endpoint.path}: {e}", flush=True)
                success = False

    elapsed_time = round(time.time() - start_time, 2)

    return {
        "project": project.model_dump(mode="json"),
        "tokens_used": total_tokens,
        "time_spent": elapsed_time,
        "success": success,
    }
