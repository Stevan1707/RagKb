from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """探活接口，前端或运维可用它判断后端是否就绪。"""
    return {"status": "ok"}
