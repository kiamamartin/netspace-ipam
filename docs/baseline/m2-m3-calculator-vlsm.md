# M2 + M3 Gate Evidence — Subnet Calculation Engine & VLSM Allocation

Date: 2026-10-23 · Recorded per `MILESTONES.md` §2-M2 and §2-M3.
Statuses after evidence: **M2 PASS** · **M3 PASS** (mirrored in
`docs/quality/milestone-status.json`).

## Test-path substitutions (documented, per "or documented equivalent")

The roadmap names `backend/tests/unit/…`, `backend/tests/regression/test_m3_scenario.py`.
The repository keeps tests **flat under `backend/tests/`**; no directory move was
performed (operator files preserved). Substituted equivalents:

| Roadmap path | Used instead | Result |
| --- | --- | --- |
| `pytest backend/tests/unit/test_subnet_calculator.py -v` | `pytest tests/test_subnet_calculator.py -v` + new `tests/test_calculator_vectors.py -v` | 55 + 14 passed |
| `pytest backend/tests/unit/test_vlsm_allocator.py backend/tests/regression/test_m3_scenario.py -v` | `pytest tests/test_vlsm_allocator.py -v` + new `tests/test_m3_scenario.py -v` | all passed, 180 total |

## M2 — acceptance criteria → evidence (executed 2026-10-23)

| AC | Evidence |
| --- | --- |
| 001 parse/validate v4+v6 | `test_parse_valid_cidr`, `test_parse_rejects_malformed[192.168.1.0/33, ::/129, …]`, `test_family_mismatch_rejected` |
| 002 v4 properties | `test_ipv4_slash24_details` (hardcoded: mask/broadcast/range), vector `192.168.10.0/24` |
| 003 /31, /32 | `test_slash31_point_to_point`, `test_slash32_host_route` + vectors `10.1.2.3/31`, `172.16.0.9/32` |
| 004 /127, /128 | NEW `test_slash127_point_to_point`, `test_ipv6_slash128` + vectors |
| 005 reject invalid inputs | malformed parametrized cases, `test_min_prefix_rejects_zero_hosts` |
| 006 containment/overlap/parent-fit | `test_alignment_and_containment`, `test_overlap_detection`, NEW `test_overlap_misaligned_crosscheck` |
| 007 /0 boundaries, no overflow | NEW `test_ipv4_slash0_boundary` (2³², no enumeration), `test_ipv6_slash0_boundary` (2¹²⁸ via arbitrary-precision int) |
| 008 established library + own validation | engine delegates arithmetic to Python `ipaddress` (`app/services/subnet_calculator.py` module docstring), app-specific policies layered on top |
| 009 known vectors + independent reference | NEW `tests/test_calculator_vectors.py`: hardcoded vectors AND a pure bit-math reference (integer shift/mask, **no `ipaddress`**) computing network/broadcast/mask/first/last/usable; every engine output must equal BOTH |
| 010 not self-agreeing | See 009 — the reference shares neither code nor oracle with the engine; it caught one of my own drafted vector values (`2001:db8::/64` last address) during authoring, i.e. it genuinely disagrees when the expectation is wrong |

## M3 — mandatory regression scenario (executed)

`tests/test_m3_scenario.py` (NEW), 11 tests, printed allocation table:

```
Department      Prefix  Network            Broadcast          Usable  Efficiency
Administration  /25     192.168.10.0       192.168.10.127     126     126 >= 100
ICT             /26     192.168.10.128     192.168.10.191      62      62 >=  50
Finance         /27     192.168.10.192     192.168.10.223      30      30 >=  25
Management      /28     192.168.10.224     192.168.10.239      14      14 >=  10
                                                remaining: 192.168.10.240–.255 (16)
```

- Non-overlapping, inside the /24, aligned, correct network/broadcast/usable
  semantics — `test_allocation_table`, `test_network_broadcast_semantics`,
  `test_no_overlaps`, `test_prefix_aligned_and_contained`.
- Deterministic ("M3-AC-009"): `test_identical_input_identical_output` — full-plan
  equality over repeat runs and over reordered input.
- Summary (`M3-AC-010`): allocated 240/256, remaining 16 in one contiguous range.
- **Rejection test (M3-AC-007/008)**: `test_insufficient_capacity_rejected` —
  two 200-host workloads in a /24 and three 60-host workloads in a /25 both raise
  `VLSMError` *before* any allocation is returned; structured error asserted.
  During authoring my first counter-example ("two 60-host in /25") was
  mathematically possible (2×/26) and the engine correctly accepted it — the test
  now uses a genuinely impossible combination.

## Full-suite evidence

| Command | Result |
| --- | --- |
| `pytest -q` (backend, whole suite) | **180 passed** (was 155 pre-M2; +14 vectors, +11 scenario) |
| `ruff check .` | All checks passed |
| front-end refactor gates (same session) | smoke all PASS, oxlint 0/0, build exit 0 |

Fixes made during M2/M3 authoring were all in the NEW tests (reference-implementation
 bugs, import hygiene, schema-name mismatches) — no product code was changed and no
 assertion was weakened; failures surfaced mismatches between my own expectations and
 the verified engine, resolved by correcting the tests.

## Known deviations

- `MILESTONES.md` §4–§7 still truncated operator-side (does not affect M2/M3 criteria).
- Test directories remain flat; both substitutions are recorded above and in
  `docs/baseline/m2-m3-calculator-vlsm.md` so future gates can either adopt the
  documented equivalence or formally reorganize with authorization.
