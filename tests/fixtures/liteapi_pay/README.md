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

Recorded through the real payment form in a real browser (2026-11-16, the sandbox test card, a sandbox voucher of 10%; `tests_browser/test_zz_real_sandbox.py` was the scratch run, not kept):
- `prebook_sdk_refundable.json`, `prebook_voucher_refundable.json`: a refundable San Diego stay (free until Dec 10, $148.88 from then, the whole $520.66 from Dec 11). The voucher prebook: price 520.66, voucherTotalAmount 52.06, sellingPriceToUser 468.60.
- `book_transaction_id.json`: the TRANSACTION_ID book after the card paid (`paymentStatus: succeeded`, the voucher in it). Its account `feed` and `userId` are scrubbed.
- `cancel_refundable.json`: that booking's cancel: CANCELLED, refund_amount 520.66 (the undiscounted price: the card paid 468.60), fee 0.

**Not recorded:** an invoice, 3-D Secure, a card that is declined.
