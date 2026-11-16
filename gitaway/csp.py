"""A Content-Security-Policy in REPORT-ONLY mode for the trip matrix and its booking sheet (F-274 review, D-849): what the page would allow if a policy were enforced, so a browser's console
(and DevTools) shows what it would block, and nothing is blocked. It is not enforced yet and has no report address: enforcing it waits for the founder's look at a real booking.

The page's own scripts are all files of ours (`'self'`, no inline script: tests/test_no_cdn_scripts.py and tests/test_csp_report_only.py read the served page), so no nonce or hash is
needed; the one script of another site is LiteAPI's payment form, which loads its processor's. The hosts are the ones seen in a real browser run against the sandbox on 2026-11-16
(tests_browser/test_matrixbook_real_sandbox.py, docs/research/liteapi-payment.md): LiteAPI's wrapper, Stripe (js, m.stripe.network, b.stripecdn.com, r.stripe.com, merchant-ui-api),
Stripe's captcha (hcaptcha.com) and Amazon Pay's button (apay-us.amazon.com). They are LiteAPI's to change, so a report-only run is how to see a change before enforcing.
Hotel photos come from many https hosts (img-src https:); styles may be inline (the pages use style attributes).
"""

PATH_PREFIX = "/plan/matrix"
HEADER = "content-security-policy-report-only"
STRIPE = "https://js.stripe.com https://m.stripe.network https://b.stripecdn.com https://r.stripe.com https://merchant-ui-api.stripe.com https://api.stripe.com"
HCAPTCHA = "https://hcaptcha.com https://*.hcaptcha.com"
LITEAPI = "https://payment-wrapper.liteapi.travel"
AMAZON = "https://apay-us.amazon.com"
POLICY = "; ".join((
    "default-src 'self'",
    f"script-src 'self' {LITEAPI} {STRIPE} {HCAPTCHA} {AMAZON}",
    f"frame-src {STRIPE} {HCAPTCHA}",
    f"connect-src 'self' {LITEAPI} {STRIPE} {HCAPTCHA} {AMAZON}",
    f"style-src 'self' 'unsafe-inline' {LITEAPI} https://b.stripecdn.com {HCAPTCHA}",
    "img-src 'self' data: https:",
    "font-src 'self' https://b.stripecdn.com",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
))


def applies(path: str) -> bool:
    return path == PATH_PREFIX or path.startswith(PATH_PREFIX + "/")
