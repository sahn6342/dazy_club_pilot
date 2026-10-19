"""Scheduler hook. Hit POST /api/v1/internal/sweep every 1-5 minutes from any external
cron (Cloudflare Cron Trigger, cron-job.org, Render cron job) so booking expiry and payment
reconciliation do not depend on traffic. Disabled (404) unless DAZY_INTERNAL_TOKEN is set."""
import hmac
import os

from fastapi import APIRouter, Header, HTTPException

from services.availability_service import _sweep_stale_pending
from services.reconciliation import reconcile_unsettled_payments

router = APIRouter()


@router.post("/internal/sweep")
def sweep(x_internal_token: str | None = Header(default=None)):
    expected = os.environ.get("DAZY_INTERNAL_TOKEN")
    if not expected:
        raise HTTPException(status_code=404, detail="Not found.")
    if not x_internal_token or not hmac.compare_digest(x_internal_token.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Invalid token.")
    expired = _sweep_stale_pending()
    reconciled = reconcile_unsettled_payments()
    return {"expired": expired, "reconciled": reconciled}
