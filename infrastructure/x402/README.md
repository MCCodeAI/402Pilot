# x402 Integration Witness — Local Stack

This directory contains the **local-only** stack used by the 402Pilot
integration witness. It is **not** used by the benchmark. The benchmark
(everything reported in the paper) runs against frozen replay; this
stack exists so we can demonstrate that the same `PaymentExecutor`
contract is satisfiable on a real x402 protocol round-trip.

## What gets started

| Service           | Role                                                         | Port  |
|-------------------|--------------------------------------------------------------|-------|
| `anvil`           | Local EVM fork (Foundry). Provides USDC + mainnet state.     | 8545  |
| `facilitator`     | FastAPI service using the upstream Python `x402` SDK.        | 4021  |
| `resource-server` | FastAPI app with x402 middleware. Provider stand-in.         | 8000  |

All three run on a private docker-compose network; only the host ports
above are exposed to localhost.

## Setup

1.  Copy `.env.example` to `.env` and fill in `MAINNET_FORK_RPC_URL`
    with any reliable mainnet RPC (Alchemy, Infura, public node — Anvil
    only reads at startup, nothing is sent back upstream).

2.  Bring the stack up:

    ```bash
    docker compose up -d
    docker compose ps        # all three services should be "running / healthy"
    ```

3.  Sanity-check the resource server:

    ```bash
    curl -s http://localhost:8000/healthz
    # {"status":"ok"}
    ```

## Running the witness

From the repo root:

```bash
./scripts/x402_witness.sh
```

That script wraps `docker compose up -d` → `python scripts/run_x402_witness.py`
→ `docker compose down`. The Python script prints one line per round to
stdout and never writes to `results/`.

## Running the integration test

```bash
pytest tests/integration/test_x402_roundtrip.py -m integration -v
```

The test is gated behind the `X402_INTEGRATION_TEST=1` opt-in and is
**skipped by default** in normal `pytest` runs. The buyer wallet must be
funded first, either by running `scripts/witness_smoke.sh` or by calling
`python infrastructure/x402/fund_buyer.py`.

```bash
X402_INTEGRATION_TEST=1 pytest tests/integration/test_x402_roundtrip.py -v -s
```

## Runtime Images

| Image                                       | Tag                          |
|---------------------------------------------|------------------------------|
| `ghcr.io/foundry-rs/foundry`                | `latest`                     |
| `python` (facilitator/resource-server base) | `3.11-slim`                  |

When changing the runtime images, update both `docker-compose.yml` and
this table so reviewers can reproduce the same stack.

## Wallet layout

All keys are Anvil test accounts. Safe to commit because every Anvil
node generates the same well-known set; never use these on a live
network.

| Role                  | Account index | Purpose                                  |
|-----------------------|---------------|------------------------------------------|
| Buyer (witness signer)| 0             | Signs `PAYMENT-SIGNATURE` payloads       |
| Seller (`PAY_TO`)     | 1             | Receives USDC per round                  |
| Facilitator signer    | 9             | Pays gas for settlement transactions     |

## Notes on the `X402PaymentExecutor`

The executor (`pilot402/runtime/x402_executor.py`) speaks to this stack
via the upstream `x402` Python SDK. If a future SDK release renames the
client classes or the FastAPI middleware, the two single places to
update are:

* `pilot402/runtime/x402_executor.py` → `_build_payment_client`
* `infrastructure/x402/resource_server.py` → the imports at the top

The rest of the code is SDK-agnostic.
