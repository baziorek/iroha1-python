"""Integration tests against a live Iroha node over the Torii gRPC API.

These tests are skipped unless the environment provides:

* ``IROHA_HOST_ADDR`` — Torii endpoint, e.g. ``127.0.0.1:50051``
* ``IROHA_ADMIN_PRIVATE_KEY`` — hex-encoded private key of an account that
  exists in the network and has administrative permissions

Optional:

* ``IROHA_ADMIN_ACCOUNT_ID`` — defaults to ``admin@test``
* ``IROHA_DOMAIN_ID`` — domain used for created entities, defaults to ``test``

The defaults match the genesis block shipped in ``docker/iroha/``.
"""

import os
import threading
import time
import uuid

import pytest
from nacl.signing import SigningKey

from iroha import Iroha, IrohaCrypto, IrohaGrpc

HOST = os.environ.get('IROHA_HOST_ADDR')
ADMIN_ID = os.environ.get('IROHA_ADMIN_ACCOUNT_ID', 'admin@test')
ADMIN_KEY = os.environ.get('IROHA_ADMIN_PRIVATE_KEY')
DOMAIN_ID = os.environ.get('IROHA_DOMAIN_ID', 'test')

pytestmark = pytest.mark.skipif(
    not (HOST and ADMIN_KEY),
    reason='Set IROHA_HOST_ADDR and IROHA_ADMIN_PRIVATE_KEY to run '
           'integration tests')

COMMIT_TIMEOUT = 30


def unique_name(prefix='it'):
    return '{}{}'.format(prefix, uuid.uuid4().hex[:10])


@pytest.fixture(scope='module')
def client():
    return Iroha(ADMIN_ID), IrohaGrpc(HOST)


def send_and_wait(net, transaction, timeout=COMMIT_TIMEOUT):
    """Sign with the admin key, submit and wait for a terminal status."""
    IrohaCrypto.sign_transaction(transaction, ADMIN_KEY)
    net.send_tx(transaction)
    last = None
    for status in net.tx_status_stream(transaction, timeout=timeout):
        last = status
        if status[0] in ('COMMITTED', 'REJECTED', 'MST_EXPIRED'):
            break
    assert last is not None, 'no transaction status received'
    assert last[0] == 'COMMITTED', 'transaction not committed: {}'.format(last)
    return last


def signed_query(iroha, name, private_key=ADMIN_KEY, **kwargs):
    query = iroha.query(name, **kwargs)
    IrohaCrypto.sign_query(query, private_key)
    return query


def test_create_account_and_query(client):
    iroha, net = client
    name = unique_name()
    account_id = '{}@{}'.format(name, DOMAIN_ID)
    private_key = IrohaCrypto.private_key()
    public_key = IrohaCrypto.derive_public_key(private_key)

    tx = iroha.transaction([iroha.command(
        'CreateAccount', account_name=name, domain_id=DOMAIN_ID,
        public_key=public_key)])
    send_and_wait(net, tx)

    query = signed_query(iroha, 'GetAccount', account_id=account_id)
    response = net.send_query(query)
    account = response.account_response.account
    assert account.account_id == account_id
    assert account.domain_id == DOMAIN_ID
    assert account.quorum == 1


def test_asset_transfer_flow(client):
    iroha, net = client
    asset_name = unique_name('coin')
    asset_id = '{}#{}'.format(asset_name, DOMAIN_ID)

    txs = [
        iroha.transaction([iroha.command(
            'CreateAsset', asset_name=asset_name, domain_id=DOMAIN_ID,
            precision=2)]),
        iroha.transaction([iroha.command(
            'AddAssetQuantity', asset_id=asset_id, amount='100.0')]),
    ]
    for tx in txs:
        send_and_wait(net, tx)

    # recipient account
    recipient = unique_name('rcp')
    recipient_id = '{}@{}'.format(recipient, DOMAIN_ID)
    private_key = IrohaCrypto.private_key()
    tx = iroha.transaction([iroha.command(
        'CreateAccount', account_name=recipient, domain_id=DOMAIN_ID,
        public_key=IrohaCrypto.derive_public_key(private_key))])
    send_and_wait(net, tx)

    tx = iroha.transaction([iroha.command(
        'TransferAsset', src_account_id=ADMIN_ID,
        dest_account_id=recipient_id, asset_id=asset_id,
        amount='5.5', description='integration test')])
    send_and_wait(net, tx)

    query = signed_query(iroha, 'GetAccountAssets',
                         account_id=recipient_id)
    response = net.send_query(query)
    assets = response.account_assets_response.account_assets
    assert len(assets) == 1
    assert assets[0].asset_id == asset_id
    assert assets[0].balance == '5.5'


def test_sha2_signed_query(client):
    """Queries signed with a PyNaCl (ed25519/sha2) key are accepted."""
    iroha, net = client
    query = iroha.query('GetPeers')
    IrohaCrypto.sign_query(query, SigningKey.generate())
    response = net.send_query(query)
    assert response is not None


def test_blocks_stream_receives_committed_block(client):
    """FetchCommits yields a block once a new transaction is committed."""
    iroha, net = client
    query = iroha.blocks_query()
    IrohaCrypto.sign_query(query, ADMIN_KEY)
    stream = net.send_blocks_stream_query(query)

    received = {}

    def read_block():
        for block_response in stream:
            received['block'] = block_response
            return

    reader = threading.Thread(target=read_block, daemon=True)
    reader.start()
    time.sleep(1)  # let the stream RPC establish

    tx = iroha.transaction([iroha.command(
        'SetAccountDetail', account_id=ADMIN_ID,
        key='it_key', value='it_value')])
    IrohaCrypto.sign_transaction(tx, ADMIN_KEY)
    net.send_tx(tx)

    reader.join(timeout=COMMIT_TIMEOUT)
    assert 'block' in received, 'no block received on the stream'
    response = received['block']
    assert response.WhichOneof('response') == 'block_response'
    block = response.block_response.block
    transactions = block.block_v1.payload.transactions
    assert any(
        tx.payload.reduced_payload.commands[0]
        .set_account_detail.key == 'it_key'
        for tx in transactions)
