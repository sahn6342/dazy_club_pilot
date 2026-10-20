"""Fail-closed production config check, run from the FastAPI lifespan.

Production is detected via DAZY_ENV=production, or the RENDER env var that
Render injects into every service. Dev/test (neither set) is unaffected."""
import os

_DEFAULT_JWT_SECRET = "dazy-dev-secret-change-in-production"
_MIN_SECRET_LEN = 32


def is_production() -> bool:
    return os.environ.get("DAZY_ENV", "").lower() == "production" or bool(os.environ.get("RENDER"))


def forbid_noop_payments_in_production(provider: str) -> None:
    """Called when the payment provider is built: the noop provider confirms any
    payment and trusts unsigned webhooks, so it must never exist in production."""
    if provider != "razorpay" and is_production():
        raise RuntimeError(
            "Refusing to start with unsafe production config: DAZY_PAYMENT_PROVIDER must be 'razorpay' "
            "(noop trusts the client and confirms unpaid bookings)."
        )


def config_problems() -> list[str]:
    """Return human-readable misconfigurations that are unsafe in production."""
    problems: list[str] = []
    secret = os.environ.get("JWT_SECRET", _DEFAULT_JWT_SECRET)
    if secret == _DEFAULT_JWT_SECRET or secret.startswith("replace-with") or len(secret) < _MIN_SECRET_LEN:
        problems.append(f"JWT_SECRET must be set to a random value of {_MIN_SECRET_LEN}+ characters.")
    if os.environ.get("ADMIN_PASSWORD_HASH"):
        if not os.environ["ADMIN_PASSWORD_HASH"].startswith("$2"):
            problems.append("ADMIN_PASSWORD_HASH must be a bcrypt hash (starts with $2).")
    elif os.environ.get("ADMIN_PASSWORD", "admin") in ("admin", "") or os.environ.get("ADMIN_PASSWORD", "").startswith("replace-with"):
        problems.append("ADMIN_PASSWORD (or ADMIN_PASSWORD_HASH) must be set to a non-default value.")
    if os.environ.get("DAZY_PAYMENT_PROVIDER", "noop") != "razorpay":
        problems.append("DAZY_PAYMENT_PROVIDER must be 'razorpay' (noop trusts the client and confirms unpaid bookings).")
    elif not os.environ.get("RAZORPAY_WEBHOOK_SECRET"):
        problems.append("RAZORPAY_WEBHOOK_SECRET must be set (webhooks are the source of truth for payments).")
    if os.environ.get("DAZY_MEDIA_BACKEND", "local").strip().lower() == "r2":
        missing = [k for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET", "R2_PUBLIC_BASE_URL")
                   if not os.environ.get(k)]
        if missing:
            problems.append(f"DAZY_MEDIA_BACKEND=r2 needs {', '.join(missing)}.")
    elif not os.environ.get("DAZY_MEDIA_LOCAL_OK"):
        problems.append("Uploads would be written to local disk and lost on redeploy: set DAZY_MEDIA_BACKEND=r2 "
                        "(or DAZY_MEDIA_LOCAL_OK=1 if a persistent disk is mounted at DAZY_MEDIA_DIR).")
    if os.environ.get("DAZY_RATE_LIMIT_SCALE", "1") != "1":
        problems.append("DAZY_RATE_LIMIT_SCALE must be unset/1 in production (it loosens every rate limit).")
    if not os.environ.get("TURNSTILE_SECRET"):
        problems.append("TURNSTILE_SECRET must be set (bot protection on booking, enquiry and OTP endpoints).")
    return problems


def assert_production_config() -> None:
    """Raise RuntimeError on unsafe config when running in production; no-op otherwise."""
    if not is_production():
        return
    problems = config_problems()
    if problems:
        raise RuntimeError("Refusing to start with unsafe production config:\n - " + "\n - ".join(problems))
