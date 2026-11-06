"""Plan it for me (F-193): the screens and the Stripe webhook. The rules, the order and the money are gitaway/planforme.py.

POST /stripe/webhook     Stripe's `checkout.session.completed`: verified with STRIPE_WEBHOOK_SECRET, then idempotent by event id (400 for a body Stripe did not sign, 503 with no secret set)
"""

from starlette.concurrency import run_in_threadpool
from starlette.responses import PlainTextResponse

from gitaway import planforme as pfm


def register(app):
    @app.post("/stripe/webhook")
    async def stripe_webhook(request):
        status, answer = await run_in_threadpool(pfm.receive, await request.body(), request.headers.get("stripe-signature", ""))
        return PlainTextResponse(answer, status_code=status)
