from fastapi import HTTPException, Request

from app.config.settings import settings
from app.scripts.job_state import registry, JobState
from app.utils.check_rate_limit import RateLimitExceeded, check_rate_limit
from app.utils.get_client_ip import get_client_ip
from app.config.redis import redis_client
from app.config.logging_config import get_logger

logger = get_logger(__name__)


def require_rate_limit(request: Request) -> str:
    client_ip = get_client_ip(request)

    try:
        check_rate_limit(
            redis_client,
            key=f"critical:{client_ip}",
            limit=settings.RATE_LIMIT_CRITICAL,
            window=86400,
        )
    except RateLimitExceeded:
        logger.warning(
            "Rate limit crítico excedido",
            extra={"action": "rate_limit_exceeded", "client_ip": client_ip},
        )
        raise HTTPException(
            status_code=429,
            detail="Limite de requisições críticas atingido",
        )

    return client_ip


def require_global_rate_limit(request: Request) -> str:
    client_ip = get_client_ip(request)

    try:
        check_rate_limit(
            redis_client,
            key=f"global:{client_ip}",
            limit=settings.RATE_LIMIT_GLOBAL,
            window=86400,
        )
    except RateLimitExceeded:
        logger.warning(
            "Global rate limit excedido",
            extra={"action": "global_rate_limit_exceeded", "client_ip": client_ip},
        )
        raise HTTPException(
            status_code=429,
            detail="Limite global de requisições atingido",
        )

    return client_ip


def require_job(job_id: str) -> JobState:
    """
    Garante que o job existe no Redis. Retorna o JobState.
    Levanta HTTP 404 se o job não for encontrado.
    """
    state = registry.get(job_id)
    if not state:
        logger.warning(
            "Consulta de status para job inexistente",
            extra={"action": "job_not_found", "job_id": job_id},
        )
        raise HTTPException(404, f"Job {job_id} não encontrado")
    return state
