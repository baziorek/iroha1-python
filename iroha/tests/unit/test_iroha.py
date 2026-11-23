"""Unit tests for Iroha transaction/query factory methods and crypto helpers."""

import binascii

import pytest
from google.protobuf.timestamp_pb2 import Timestamp
from nacl.signing import SigningKey

from iroha import Iroha, IrohaCrypto, IrohaGrpc, ed25519_sha2
from iroha import endpoint_pb2
from iroha import primitive_pb2
from iroha import queries_pb2
from iroha import transaction_pb2

CREATOR = 'admin@test'
PRIVATE_KEY = 'f101537e319568c765b2cc89698325604991dca57b9716b58016b253506cab70'
PUBLIC_KEY = '313a07e6384776ed95447710d15e59148473ccfc052a681317a72a69f2a49910'

SHA2_PRIVATE_KEY = SigningKey(
    b'\x99\xfe\x89i\xac\xda\xfb\t\xbf\xdd\x00F7\x0e/\xa2X\x0b\x0c%\x91\xa266%%\r\xa1Mw\x1bc')
SHA2_PUBLIC_KEY = ('ed0120' + binascii.hexlify(
    SHA2_PRIVATE_KEY.verify_key._key).decode('utf-8'))


def make_transaction(iroha=None):
    iroha = iroha or Iroha(CREATOR)
    command = iroha.command('CreateDomain', domain_id='domain',
                            default_role='user')
    return iroha.transaction([command])


def make_query(iroha=None, name='GetAccount', **kwargs):
    iroha = iroha or Iroha(CREATOR)
    kwargs.setdefault('account_id', 'account@domain')
    return iroha.query(name, **kwargs)


class TestCamelCase:
    @pytest.mark.parametrize('camel, snake', [
        ('CreateDomain', 'create_domain'),
        ('AddAssetQuantity', 'add_asset_quantity'),
        ('CompareAndSetAccountDetail', 'compare_and_set_account_detail'),
        ('SetSettingValue', 'set_setting_value'),
        ('GetAccountTransactions', 'get_account_transactions'),
    ])
    def test_conversion(self, camel, snake):
        assert Iroha._camel_case_to_snake_case(camel) == snake


class TestCommand:
    def test_create_domain(self):
        command = Iroha.command('CreateDomain', domain_id='domain',
                                default_role='user')
        assert command.WhichOneof('command') == 'create_domain'
        assert command.create_domain.domain_id == 'domain'
        assert command.create_domain.default_role == 'user'

    def test_transfer_asset(self):
        command = Iroha.command(
            'TransferAsset',
            src_account_id='src@domain',
            dest_account_id='dest@domain',
            asset_id='coin#domain',
            amount='10.0',
            description='payment')
        assert command.WhichOneof('command') == 'transfer_asset'
        assert command.transfer_asset.asset_id == 'coin#domain'
        assert command.transfer_asset.amount == '10.0'

    def test_create_role_permissions(self):
        command = Iroha.command(
            'CreateRole', role_name='role',
            permissions=[
                primitive_pb2.RolePermission.Value('can_create_role'),
                primitive_pb2.RolePermission.Value('can_append_role'),
            ])
        assert command.WhichOneof('command') == 'create_role'
        assert list(command.create_role.permissions) == [
            primitive_pb2.RolePermission.Value('can_create_role'),
            primitive_pb2.RolePermission.Value('can_append_role'),
        ]

    def test_add_peer(self):
        peer = primitive_pb2.Peer(address='127.0.0.1:4000',
                                  peer_key='peerkey')
        command = Iroha.command('AddPeer', peer=peer)
        assert command.WhichOneof('command') == 'add_peer'
        assert command.add_peer.peer.address == '127.0.0.1:4000'
        assert command.add_peer.peer.peer_key == 'peerkey'

    def test_unknown_command(self):
        with pytest.raises(AttributeError):
            Iroha.command('NoSuchCommand')


class TestTransaction:
    def test_defaults(self):
        tx = make_transaction()
        payload = tx.payload.reduced_payload
        assert payload.creator_account_id == CREATOR
        assert payload.quorum == 1
        assert len(payload.commands) == 1
        assert payload.commands[0].WhichOneof('command') == 'create_domain'

    def test_explicit_parameters(self):
        iroha = Iroha()
        command = iroha.command('CreateDomain', domain_id='d',
                                default_role='user')
        tx = iroha.transaction([command], quorum=2,
                               creator_account=CREATOR, created_time=12345)
        payload = tx.payload.reduced_payload
        assert payload.creator_account_id == CREATOR
        assert payload.quorum == 2
        assert payload.created_time == 12345

    def test_no_creator_account(self):
        with pytest.raises(AssertionError):
            Iroha().transaction(
                [Iroha.command('CreateDomain', domain_id='d',
                               default_role='user')])

    def test_now_is_milliseconds(self):
        before = Iroha.now()
        tx = make_transaction()
        after = Iroha.now()
        created_time = tx.payload.reduced_payload.created_time
        assert before <= created_time <= after


class TestQuery:
    def test_get_account(self):
        query = make_query()
        assert query.payload.WhichOneof('query') == 'get_account'
        assert query.payload.get_account.account_id == 'account@domain'
        meta = query.payload.meta
        assert meta.creator_account_id == CREATOR
        assert meta.query_counter == 1

    def test_query_counter_and_time(self):
        query = make_query(counter=42, created_time=999)
        assert query.payload.meta.query_counter == 42
        assert query.payload.meta.created_time == 999

    def test_empty_query(self):
        query = Iroha(CREATOR).query('GetPeers')
        assert query.payload.WhichOneof('query') == 'get_peers'
        assert query.payload.get_peers is not None

    def test_get_transactions_hashes(self):
        query = Iroha(CREATOR).query(
            'GetTransactions', tx_hashes=['aa' * 32, 'bb' * 32])
        assert query.payload.WhichOneof('query') == 'get_transactions'
        assert list(query.payload.get_transactions.tx_hashes) == [
            'aa' * 32, 'bb' * 32]

    def test_pagination_meta(self):
        first_tx_time = Timestamp(seconds=1000)
        last_tx_time = Timestamp(seconds=2000)
        query = Iroha(CREATOR).query(
            'GetAccountTransactions',
            account_id='account@domain',
            page_size=10,
            first_tx_hash='cc' * 32,
            first_tx_time=first_tx_time,
            last_tx_time=last_tx_time,
            first_tx_height=5,
            last_tx_height=50,
            ordering_sequence=[
                [queries_pb2.kCreatedTime, queries_pb2.kAscending],
                [queries_pb2.kPosition, queries_pb2.kDescending],
            ])
        meta = query.payload.get_account_transactions.pagination_meta
        assert meta.page_size == 10
        assert meta.first_tx_hash == 'cc' * 32
        assert meta.first_tx_time == first_tx_time
        assert meta.last_tx_time == last_tx_time
        assert meta.first_tx_height == 5
        assert meta.last_tx_height == 50
        sequence = meta.ordering.sequence
        assert [(f.field, f.direction) for f in sequence] == [
            (queries_pb2.kCreatedTime, queries_pb2.kAscending),
            (queries_pb2.kPosition, queries_pb2.kDescending),
        ]

    def test_no_creator_account(self):
        with pytest.raises(AssertionError):
            Iroha().query('GetAccount', account_id='account@domain')


class TestBlocksQuery:
    def test_blocks_query(self):
        query = Iroha(CREATOR).blocks_query(counter=7, created_time=42)
        assert query.meta.creator_account_id == CREATOR
        assert query.meta.query_counter == 7
        assert query.meta.created_time == 42


class TestBatch:
    def test_atomic_batch(self):
        iroha = Iroha(CREATOR)
        txs = [make_transaction(iroha) for _ in range(2)]
        Iroha.batch(txs, atomic=True)
        for tx in txs:
            batch = tx.payload.batch
            assert batch.type == transaction_pb2.Transaction.Payload.BatchMeta.ATOMIC
            assert len(batch.reduced_hashes) == 2

    def test_ordered_batch(self):
        iroha = Iroha(CREATOR)
        txs = [make_transaction(iroha) for _ in range(2)]
        Iroha.batch(txs, atomic=False)
        for tx in txs:
            assert tx.payload.batch.type == \
                transaction_pb2.Transaction.Payload.BatchMeta.ORDERED


class TestIrohaGrpc:
    def test_default_address(self):
        client = IrohaGrpc()
        assert client._address == '127.0.0.1:50051'

    def test_custom_address(self):
        client = IrohaGrpc('localhost:4000', timeout=5)
        assert client._address == 'localhost:4000'
        assert client._timeout == 5


class TestCrypto:
    def test_private_key_format(self):
        key = IrohaCrypto.private_key()
        assert isinstance(key, bytes)
        assert len(binascii.unhexlify(key)) == 32

    @pytest.mark.parametrize('key', [PRIVATE_KEY, PRIVATE_KEY.encode()])
    def test_derive_public_key_sha3(self, key):
        assert IrohaCrypto.derive_public_key(key) == PUBLIC_KEY.encode()

    def test_derive_public_key_sha2(self):
        assert IrohaCrypto.derive_public_key(SHA2_PRIVATE_KEY) == SHA2_PUBLIC_KEY

    def test_sign_and_verify_sha3(self):
        tx = make_transaction()
        IrohaCrypto.sign_transaction(tx, PRIVATE_KEY)
        assert len(tx.signatures) == 1
        signature = tx.signatures[0]
        assert signature.public_key == PUBLIC_KEY
        assert IrohaCrypto.is_signature_valid(tx, signature)
        assert not IrohaCrypto.is_sha2_signature_valid(tx, signature)

    def test_sha2_signature_invalid(self):
        query = make_query()
        IrohaCrypto.sign_query(query, SHA2_PRIVATE_KEY)
        query.payload.meta.query_counter = 100
        assert not IrohaCrypto.is_sha2_signature_valid(query,
                                                       query.signature)

    def test_sign_and_verify_sha2(self):
        tx = make_transaction()
        IrohaCrypto.sign_transaction(tx, SHA2_PRIVATE_KEY)
        signature = tx.signatures[0]
        assert signature.public_key == SHA2_PUBLIC_KEY
        assert IrohaCrypto.is_sha2_signature_valid(tx, signature)

    def test_sign_transaction_multiple_keys(self):
        tx = make_transaction()
        IrohaCrypto.sign_transaction(tx, PRIVATE_KEY, SHA2_PRIVATE_KEY)
        assert len(tx.signatures) == 2

    def test_sign_transaction_no_keys(self):
        with pytest.raises(AssertionError):
            IrohaCrypto.sign_transaction(make_transaction())

    def test_sign_query(self):
        query = make_query()
        IrohaCrypto.sign_query(query, PRIVATE_KEY)
        assert query.signature.public_key == PUBLIC_KEY
        assert IrohaCrypto.is_signature_valid(query, query.signature)

    def test_signature_invalid_after_modification(self):
        tx = make_transaction()
        IrohaCrypto.sign_transaction(tx, PRIVATE_KEY)
        signature = tx.signatures[0]
        tx.payload.reduced_payload.quorum = 2
        assert not IrohaCrypto.is_signature_valid(tx, signature)

    def test_reduced_hash(self):
        tx = make_transaction()
        reduced_hash = IrohaCrypto.reduced_hash(tx)
        assert isinstance(reduced_hash, bytes)
        assert len(binascii.unhexlify(reduced_hash)) == 32
        assert IrohaCrypto.reduced_hash(tx) == reduced_hash

    def test_hash_and_payload(self):
        tx = make_transaction()
        assert len(IrohaCrypto.hash(tx)) == 32
        assert IrohaCrypto.get_payload_to_be_signed(tx) == \
            tx.payload.SerializeToString()

    def test_hash_blocks_query_meta(self):
        query = Iroha(CREATOR).blocks_query()
        assert len(IrohaCrypto.hash(query)) == 32
        assert IrohaCrypto.get_payload_to_be_signed(query) == \
            query.meta.SerializeToString()

    def test_unknown_message_type(self):
        signature = primitive_pb2.Signature()
        with pytest.raises(RuntimeError):
            IrohaCrypto.get_payload_to_be_signed(signature)

    def test_unsupported_key_type(self):
        with pytest.raises(RuntimeError):
            IrohaCrypto._signature(make_transaction(), 12345)

    def test_parse_tx_status(self):
        response = endpoint_pb2.ToriiResponse(
            tx_status=endpoint_pb2.COMMITTED, tx_hash='ab' * 32)
        name, code, error_code = IrohaGrpc._parse_tx_status(response)
        assert name == 'COMMITTED'
        assert code == endpoint_pb2.COMMITTED
        assert error_code == 0
