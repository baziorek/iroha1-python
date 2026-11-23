# iroha-python (Iroha 1.x fork)

[![CI](https://github.com/baziorek/iroha1-python/actions/workflows/ci.yml/badge.svg)](https://github.com/baziorek/iroha1-python/actions/workflows/ci.yml)

Python client library for **Hyperledger Iroha 1.x** — a fork of the
[upstream `hyperledger/iroha-python`](https://github.com/hyperledger/iroha-python)
(`iroha1-main` branch), maintained for the Iroha 1 protocol.

This fork keeps the exact same wire protocol and public API
(`Iroha`, `IrohaCrypto`, `IrohaGrpc` — commands, queries, transactions,
signatures), but modernizes the package so it works on current Python
versions and toolchains:

- dependencies updated to current releases (`protobuf` 7.x, `grpcio` 1.85+,
  `PyNaCl` 1.5+), protobuf stubs regenerated — **no schema or API changes**
- packaging fixed (`pip install iroha` works again, `grpcio` dependency
  declared, `python_requires>=3.10`)
- test suite expanded from 2 to **52 tests**: unit tests plus integration
  tests that run against a real Iroha node in CI
- GitHub Actions CI: unit tests on Python 3.10–3.13, dockerized
  `hyperledger/iroha:1.6.0` integration job, package build, pip-audit
- bug fix: `is_sha2_signature_valid` no longer raises on invalid input

Looking for the node itself? Check out the reanimated Iroha 1 C++
implementation: [`baziorek/iroha1-cpp`](https://github.com/baziorek/iroha1-cpp).

## Requirements

- Python 3.10 or newer
- A running Iroha 1.x node — see [Getting an Iroha node](#getting-an-iroha-node)

## Installation

> **Note:** the `iroha` package on PyPI is the *upstream*
> `hyperledger/iroha-python` release — it is not published from this fork
> (yet). To get this modernized version, install it from GitHub:

```bash
pip install git+https://github.com/baziorek/iroha1-python.git@iroha1-main
```

(Any ref works after `@` — e.g. a feature branch — if you want to try an
unmerged change.)

…or from a local clone:

```bash
git clone https://github.com/baziorek/iroha1-python
cd iroha1-python
pip install -e .
```

Both routes install the same public API (`Iroha`, `IrohaCrypto`,
`IrohaGrpc`) — the fork differs only in refreshed dependencies, packaging
fixes and tests.

## Getting an Iroha node

This library talks to an Iroha **1.x** node over gRPC (Torii, port 50051).
You need one of:

- **Official image** — `docker/docker-compose.yaml` brings up a ready-made
  single-node network with Postgres using
  [`hyperledger/iroha:1.6.0`](https://github.com/hyperledger/iroha):

  ```bash
  cd docker && docker compose up -d
  ```

- **Reanimated Iroha 1 fork** — the C++ node maintained alongside this
  library at [`baziorek/iroha1-cpp`](https://github.com/baziorek/iroha1-cpp)
  publishes a Docker image to GHCR (public, multi-arch):

  ```bash
  docker pull ghcr.io/baziorek/iroha1-cpp:iroha1-main
  ```

  Its CI also builds **AppImage** bundles as workflow artifacts, and the
  project documents building/running `irohad` from source.

- **Any other Iroha 1.x deployment** — point `IrohaGrpc` at its Torii
  address.

## Quick start

```python
from iroha import Iroha, IrohaCrypto, IrohaGrpc

iroha = Iroha('alice@test')
net = IrohaGrpc('127.0.0.1:50051')

alice_key = IrohaCrypto.private_key()
alice_tx = iroha.transaction(
    [iroha.command(
        'TransferAsset',
        src_account_id='alice@test',
        dest_account_id='bob@test',
        asset_id='bitcoin#test',
        description='test',
        amount='1'
    )]
)
IrohaCrypto.sign_transaction(alice_tx, alice_key)
net.send_tx(alice_tx)

for status in net.tx_status_stream(alice_tx):
    print(status)  # ('COMMITTED', 5, 0)
```

Every library method has a docstring in
[`iroha/iroha.py`](iroha/iroha.py).

## Examples

Runnable examples live in [`examples/`](examples). Each expects a node at
`IROHA_HOST_ADDR` (default `127.0.0.1:50051`) — `docker compose up` in
`docker/` provides one:

| Example | What it shows |
|---|---|
| [`tx-example.py`](examples/tx-example.py) | The basics: create asset/account, transfer, query balances |
| [`batch-example.py`](examples/batch-example.py) | Atomic and ordered batches of transactions submitted at once |
| [`mst-example.py`](examples/mst-example.py) | Multi-signature transactions requiring several keys |
| [`tx-ordering.py`](examples/tx-ordering.py) | Query pagination and custom result ordering |
| [`query-transactions.py`](examples/query-transactions.py) | Transaction history queries with time-range filters |
| [`blocks-query.py`](examples/blocks-query.py) | Fetching blocks one by one via `blocks_query` |
| [`infinite-blocks-stream.py`](examples/infinite-blocks-stream.py) | Subscribing to the live stream of newly committed blocks |
| [`add-syncing-peer.py`](examples/add-syncing-peer.py) | Adding a syncing peer to the network |
| [`tls-example.py`](examples/tls-example.py) | Connecting to Torii over TLS/mTLS |

A minimal transaction + query round-trip looks like this:

```python
from iroha import Iroha, IrohaCrypto, IrohaGrpc

iroha = Iroha('admin@test')
net = IrohaGrpc('127.0.0.1:50051')
admin_key = open('admin@test.priv').read().strip()  # hex private key

# send a transaction and wait for it to be committed
tx = iroha.transaction([
    iroha.command('SetAccountDetail',
                  account_id='admin@test', key='note', value='hello')
])
IrohaCrypto.sign_transaction(tx, admin_key)
net.send_tx(tx)
for status in net.tx_status_stream(tx):
    if status[0] == 'COMMITTED':
        break

# read it back with a signed query
query = iroha.query('GetAccountDetail', account_id='admin@test')
IrohaCrypto.sign_query(query, admin_key)
response = net.send_query(query)
print(response)
```

## Tests

```bash
pip install -e . -r dev-requirements.txt
pytest iroha/tests
```

- **Unit tests** (`iroha/tests/unit/`) run without external services and
  cover command/query factories, pagination, batches, and both signature
  schemes (ed25519/sha3 and ed25519/sha2).
- **Integration tests** (`iroha/tests/integration/`) are skipped unless a
  live node is provided:

```bash
IROHA_HOST_ADDR=127.0.0.1:50051 \
IROHA_ADMIN_PRIVATE_KEY=<hex private key of an admin account> \
pytest iroha/tests/integration
```

CI runs both: a pytest matrix on Python 3.10–3.13 and a job that brings up
`docker/docker-compose.yaml` (`hyperledger/iroha:1.6.0` + Postgres) before
running the full suite.

## Development

The checked-in `*_pb2.py` files are generated from `schema/*.proto`
(the Iroha shared model). To regenerate after a schema change:

```bash
pip install -r dev-requirements.txt
python scripts/download-schema.py   # optional: refresh schema/ from upstream
python scripts/compile-proto.py
```

## Links

- Upstream: <https://github.com/hyperledger/iroha-python> (`iroha1-main`)
- Iroha 1 node (reanimated): <https://github.com/baziorek/iroha1-cpp>
- Iroha 1.x: <https://github.com/hyperledger/iroha>
- Documentation: <https://iroha.readthedocs.io/en/latest/>
