# Cal integration assessment — October 28, 2026

The original `https://cal.com/docs/self-hosting` link returned 404 during inspection. Current official documentation identifies [Cal.diy](https://www.cal.diy/) as the open-source, self-hosted community edition spun out of Cal.com. This is the candidate environment for an owned, invented-data installation.

The [reschedule API](https://cal.com/docs/api-reference/v2/bookings/reschedule-a-booking) accepts a timestamp and can return a new booking UID / reschedule relationship. It is not equivalent to setting a weekday in Iris. The [booking creation implementation](https://github.com/calcom/cal.diy/blob/main/packages/features/bookings/lib/handleNewBooking/createBooking.ts) is a candidate path to inspect in a pinned checkout, not a verified universal interception point.

Before enabling Cal writes:

1. Pin an upstream version and provision a local isolated instance. Disable outbound email, calendar delivery, workflows and payment integrations. Use invented addresses under example.test.
2. Enumerate UI/tRPC, REST, reschedule, cancel, message/workflow, and direct persistence paths. Trace side effects as well as booking rows. A webhook after saving cannot enforce the permission.
3. Normalize target ID, full timestamp/time zone, price representation and operation into the generic permission schema. Preserve original identity when rescheduling creates another booking UID.
4. Put the permission check and version comparison inside the transaction that writes the authoritative Cal database. An external preflight followed by an unguarded Cal API call has a race and is insufficient.
5. Route or deny every alternate write path available to the agent. Prove wrong record, protected price, stale version and forbidden email/cancel cannot save or trigger side effects through UI, Enter and direct HTTP.
6. Run the same held-out tasks against the pinned integration and document exactly which operations are covered.

At inspection time there was no local Cal checkout in Projects, and Docker Desktop's Linux engine was not running. No Cal writes have been intercepted or claimed as protected. Iris currently serves both desks, as the fallback allowed by AGENTS.md. Keep that statement visible in the submission until integration tests prove otherwise.
