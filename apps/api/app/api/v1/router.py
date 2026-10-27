from fastapi import APIRouter

from app.api.v1 import agents, approvals, health, memories, runs, workflows

api_router = APIRouter(prefix="/api/v1")
for module in (health, agents, workflows, runs, approvals, memories):
    api_router.include_router(module.router)
