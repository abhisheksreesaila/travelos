# LiteAPI payment-SDK recordings (F-274)

Recorded 2026-11-16 against LiteAPI's **sandbox** with `scripts/probe_liteapi_pay.py` (San Diego, 3 nights, 2 adults and kids 7 and 10). The key is never written and every
`secretKey` is replaced by the placeholder `[secretKey]`. The guest is made up (example.com).

Real answers:
- `prebook_sdk.json`: usePaymentSdk true gives `secretKey`, `transactionId` and `sellingPriceToUser`.
- `prebook_voucher.json`: a sandbox voucher of 10%. `voucherCode`, `voucherTotalAmount` 34.01 is the discount, `price` stays 340.10, `sellingPriceToUser` 306.09 is what the guest pays.
- `prebook_bad_voucher.json`: HTTP 400, code 4002.
- `book_unpaid.json`: TRANSACTION_ID for a payment never made, HTTP 400, code 2014 "payment not completed".
- `book_nonrefundable.json`: a booking (its rate is non-refundable).
- `cancel_nonrefundable.json`: 200, CANCELLED_WITH_CHARGES, refund 0, fee 340.10.
- `cancel_unknown.json`: 404, code 4008.
- `margin.json`: the same search with no margin and with `margin: 16`, the retail rate and `suggestedSellingPrice` of 11 hotels. At 16 they are equal to the cent.

**Hand-shaped, not recorded:** `cancel_refundable.json` (the docs' fully refundable answer, status CANCELLED and a refund_amount; the sandbox offered no refundable rate to cancel).

**Not recorded:** a TRANSACTION_ID book after a real card payment. It needs LiteAPI's payment form in a browser (sandbox test card 4242 4242 4242 4242).
