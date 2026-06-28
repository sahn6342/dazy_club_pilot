# State Machine

Draft
→ Locked
→ PaymentPending
→ Confirmed
→ Completed

Failure:
Locked → Expired
PaymentPending → Failed
Confirmed → Cancelled
