# Benchmark

Each case calls `fake_benchmark()` three times; the tables show the median. Generation runs inside
the database, so network latency does not affect the numbers. Raw results are in `benchmarks/`.

Reproduce with `python scripts/benchmark.py --label <name> --host "<description>"`.

## Deployed database (Neon)

- Host: Neon free plan, Render free web service in front
- PostgreSQL: 16.15 (df8277c)
- Date: 2026-10-30
- Seed: 2024

| Locale | Users | Markov bio | Median users/sec |
|---|---:|---|---:|
| de_DE | 1,000 | no | 4,524 |
| de_DE | 10,000 | no | 4,450 |
| de_DE | 100,000 | no | 4,558 |
| de_DE | 1,000 | yes | 1,845 |
| de_DE | 10,000 | yes | 1,863 |
| en_US | 1,000 | no | 4,342 |
| en_US | 10,000 | no | 4,500 |
| en_US | 100,000 | no | 4,531 |
| en_US | 1,000 | yes | 1,963 |
| en_US | 10,000 | yes | 1,891 |

## Local

- Host: Apple M3, PostgreSQL in Docker
- PostgreSQL: 16.15
- Date: 2026-10-30
- Seed: 2024

| Locale | Users | Markov bio | Median users/sec |
|---|---:|---|---:|
| de_DE | 1,000 | no | 4,154 |
| de_DE | 10,000 | no | 4,735 |
| de_DE | 100,000 | no | 4,538 |
| de_DE | 1,000 | yes | 1,040 |
| de_DE | 10,000 | yes | 944 |
| en_US | 1,000 | no | 2,414 |
| en_US | 10,000 | no | 3,858 |
| en_US | 100,000 | no | 4,582 |
| en_US | 1,000 | yes | 1,900 |
| en_US | 10,000 | yes | 1,865 |
