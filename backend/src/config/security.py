"""Production startup security checks."""

from __future__ import annotations

from urllib.parse import urlparse

from src.config.settings import Settings, settings


_WEAK_JWT_SECRETS = {
    "",
    "change-me",
    "changeme",
    "dev-secret",
    "jwt-secret",
    "secret",
    "test-secret",
}


def _is_local_origin(origin: str) -> bool:
    parsed = urlparse(origin)
    host = (parsed.hostname or origin).strip().lower()
    return host in {"localhost", "127.0.0.1", "::1"}


def _is_strong_jwt_secret(secret: str) -> bool:
    normalized = secret.strip()
    return len(normalized) >= 32 and normalized.lower() not in _WEAK_JWT_SECRETS


def validate_production_security(active_settings: Settings = settings) -> None:
    """Fail fast when production is started with development-grade security."""
    if not active_settings.is_production:
        return

    errors: list[str] = []
    if not _is_strong_jwt_secret(active_settings.auth.jwt_secret):
        errors.append("JWT_SECRET must be set to a non-placeholder value with at least 32 characters.")

    if active_settings.storage.database_url.startswith("sqlite:"):
        errors.append("DATABASE_URL must point to Postgres in production.")

    origins = active_settings.api.cors_allow_origins
    if not origins:
        errors.append("CORS_ALLOW_ORIGINS must list explicit production origins.")
    if "*" in origins:
        errors.append("CORS_ALLOW_ORIGINS must not include '*' in production.")
    if any(_is_local_origin(origin) for origin in origins):
        errors.append("CORS_ALLOW_ORIGINS must not include localhost origins in production.")

    if active_settings.auth.api_key:
        errors.append("API_KEY/KNOWBASE_API_KEY is development-only; use JWT login in production.")

    if errors:
        raise RuntimeError("Production security check failed: " + " ".join(errors))
