# LiteAPI payment form, margin, voucher and cancel (F-274, read and probed 2026-11-16)

Docs moved from docs.liteapi.travel to docs.nuitee.com (301). Sources: [user payment](https://docs.nuitee.com/docs/user-payment), [prebook](https://docs.nuitee.com/reference/post_rates-prebook), [book](https://docs.nuitee.com/reference/post_rates-book), [cancel](https://docs.nuitee.com/reference/put_bookings-bookingid), [rates](https://docs.nuitee.com/reference/post_hotels-rates), [vouchers guide](https://docs.nuitee.com/docs/vouchers-api-guide), [create voucher](https://docs.nuitee.com/reference/post_vouchers). "Probed" means recorded against the sandbox with `scripts/probe_liteapi_pay.py` (fixtures: `tests/fixtures/liteapi_pay/`).

## The payment form (User Payment SDK)
- Prebook with `usePaymentSdk: true`; the answer carries `secretKey` and `transactionId` (a new pair on every prebook; LiteAPI cannot return them later, so we save them at once).
- Script: `https://payment-wrapper.liteapi.travel/dist/liteAPIPayment.js?v=a1`. Global `LiteAPIPayment`; `new LiteAPIPayment({publicKey, secretKey, targetElement, returnUrl, appearance, options})` then `.handlePayment()`.
- `publicKey` is the string `"live"` or `"sandbox"`, matching the API key's environment (it is a name, not a secret). `secretKey` is the prebook's. `targetElement` is a CSS selector of an empty element the SDK fills.
- Read from the script itself: it POSTs `{publicKey}` to `payment-wrapper.liteapi.travel/config`, then loads the provider's own CSS and JS (Stripe elements, in iframes) named by that answer. So the card fields are LiteAPI's and Stripe's, never ours, and the hosts that serve script are LiteAPI's wrapper and its provider's.
- There is no documented success callback. After payment the browser is redirected to `returnUrl` (we give it `/plan/matrix/book/return?token=...`), which finishes the booking. The provider may add `payment_intent`, `payment_intent_client_secret` and `redirect_status` to it; we read none of them and ask LiteAPI instead (a book with an unpaid transaction is refused: HTTP 400, code 2014 "payment not completed", probed).
- Sandbox test card: 4242 4242 4242 4242, any 3-digit CVV, any future expiry.
- Nuitée is the merchant of record for the card charge; the integrator sends the guest's confirmation. Invoice PDF: `GET https://api.wlbl.cloud/v1/invoices/{bookingId}?attachment&key=...` (not used).

## Prebook (`POST https://book.liteapi.travel/v3.0/rates/prebook`)
- Body: `offerId`, `usePaymentSdk`, optional `voucherCode`. Answer `data`: `prebookId`, `price`, `currency`, `suggestedSellingPrice`, `priceDifferencePercent` (0 unless a substitute rate was found), `cancellationChanged`, `boardChanged`, `transactionId`, `secretKey`, `paymentTypes` (a sandbox prebook lists `NUITEE_PAY`, `TRANSACTION_ID`, `ACC_CREDIT_CARD`, `WALLET`), and `sellingPriceToUser`.
- Probed: without a voucher `sellingPriceToUser` equals `price` (340.10). With a 10% voucher `price` stays 340.10, `voucherCode` is echoed, `voucherTotalAmount` is the discount (34.01) and `sellingPriceToUser` is what the guest's card pays (306.09). A code that is wrong, off or expired is HTTP 400, code 4002, "The voucher code you entered is not valid: CODE".
- Prebook has no margin parameter: the price is fixed by the offer, so the margin belongs on the rates request that made the offer.

## Margin (`margin` on `POST /hotels/rates`)
- A number, a percentage that overrides the account's markup for that request. Probed on the sandbox: `retailRate.total` = net x (1 + margin/100) (340.10 at 0, 374.11 at 10, 391.08 at 15), and `suggestedSellingPrice` is at least net x 1.15 and follows the margin once it is higher.
- At `margin: 16` the retail rate (what the guest pays) and `suggestedSellingPrice` (the public price the square shows) were **equal to the cent for 10 of 11 hotels and a cent apart for the rest** (`margin.json`: 394.48 and 394.48, 1046.34 and 1046.33). At 15 the retail rate was up to $2 under the public price. So GitAway sends `margin: 16` on every stay search with a live key (`liteapi.MARGIN`, `LITEAPI_MARGIN` to change it). The sandbox key is searched without one (its retail rate is what it shows).
- The commission field in the answer is our earnings on the booking.

## Book (`POST https://book.liteapi.travel/v3.0/rates/book`)
- Body: `prebookId`, `holder` (name, email, phone), `guests[]` (`occupancyNumber`, names, email), `clientReference` (ours, the idempotency key), `payment: {method: "TRANSACTION_ID", transactionId}`. Answer: `bookingId`, `status` CONFIRMED, `cancellationPolicies.refundableTag` RFN or NRFN, `price`.
- Unpaid transaction: HTTP 400, code 2014 (probed). The same `clientReference` twice: 4005.

## Vouchers
- `POST https://da.liteapi.travel/vouchers` with a sandbox or a live key. Required: `voucher_code`, `discount_type` ("percentage" only), `discount_value`, `minimum_spend`, `maximum_discount_amount`, `usages_limit`, `currency`, `validity_start`, `validity_end` (dates), `status`; optional `guest_id`, `description`, `terms_and_conditions`, `budget`. `PUT /vouchers/:id` (the same body) switches one off; `GET /vouchers` lists them. Sandbox bookings do not count toward `usages_limit`.
- Applied as `voucherCode` on prebook with `usePaymentSdk: true`. The guest's card pays the discounted amount; LiteAPI's attached card covers the discount, so it comes out of our margin. Book re-checks the voucher (HTTP 400, codes 40033 to 40037) and returns without charging.

## Cancel (`PUT https://book.liteapi.travel/v3.0/bookings/{bookingId}`)
- Answer `data`: `bookingId`, `status` (`CANCELLED` fully refunded, `CANCELLED_WITH_CHARGES` when non-refundable or past the deadline), `refund_amount`, `cancellation_fee`, `currency`. Probed: a non-refundable sandbox booking cancels with 200, CANCELLED_WITH_CHARGES, refund 0, fee 340.10; asking again repeats the same answer; an unknown id is 404, code 4008. A refundable rate's answer is not recorded (the sandbox offered none), the docs' shape is used in `cancel_refundable.json`.
- Sandbox 429s a burst of calls: the probe waits 2 seconds between them.
