# hello-flash, deployed from a fresh clone

Cycle 6's stranger test: clone the repo into an empty directory, follow only the
written documentation, and see whether `hello-flash` actually deploys. The point
was not the app — it had been measured in Cycle 3 — but whether
[GETTING-STARTED.md](../../GETTING-STARTED.md) was true.

It was not, in three places. All three are recorded in
[FINDINGS.md](../../FINDINGS.md) under Cycle 6 and fixed in the docs.

| | |
|---|---|
| Endpoint | `jayf2t4qi40v9r` |
| Worker | `c3f77aa3932f`, the same one for all four requests |
| Cold start | **50.624 s** |
| Warm | 0.492 s, 0.284 s, 0.295 s |
| Cost | **$0.0062291667**, settled |

`balance-settle.log` is the whole reason this directory exists as evidence rather
than as a sentence. The endpoint was deleted before the first read, and the
charge did not post until the fifth — five identical readings across three
minutes, all of them the opening balance. A shorter settle rule would have
recorded this task as free.
