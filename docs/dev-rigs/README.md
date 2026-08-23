# Dev rigs — concurrency forensics (bon-resena)

Standalone reproduction instruments, deliberately in `docs/` (not vendored, no publish needed).

- `resena-repro.sh` — two concurrent writers on one prefix against a scratch Dolt server; prints LOST ids. Pre-fix it lost 42/60; item-grain writes hold it at 0.
- `resena-experiment2.sh` — one writer + a raw-SQL reader loop; prints the distribution of observed row counts. Any count below the seeded 60 proves fractured reads (Dolt sql-server serving in-flight transaction state to plain reads).

The CI-sized versions of these properties live in `tests/test_dolt_integration.py::TestItemGrainWrites`.
