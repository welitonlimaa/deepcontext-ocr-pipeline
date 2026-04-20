class RateLimitExceeded(Exception):
    pass


def check_rate_limit(
    redis_client,
    key: str,
    limit: int,
    window: int,
):
    """
    Rate limit genérico baseado em contador + TTL.

    - key: identificador único (ex: global:ip ou critical:ip)
    - limit: número máximo de requests
    - window: tempo em segundos (ex: 86400)
    """

    current = redis_client.incr(key)

    if current == 1:
        redis_client.expire(key, window)

    ttl = redis_client.ttl(key)
    if ttl == -1:
        redis_client.expire(key, window)

    if current > limit:
        raise RateLimitExceeded()
