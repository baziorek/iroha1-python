"""Unit tests for iroha.genesis markdown rendering."""

from iroha import genesis


def _genesis_json():
    return {
        "block_v1": {
            "payload": {
                "transactions": [{
                    "payload": {
                        "reducedPayload": {
                            "commands": [
                                {"createDomain": {
                                    "domainId": "test",
                                    "defaultRole": "user"}},
                                {"createRole": {
                                    "roleName": "admin",
                                    "permissions": ["can_create_account",
                                                    "can_transfer"]}},
                                {"createAccount": {
                                    "accountName": "admin",
                                    "domainId": "test"}},
                                {"appendRole": {
                                    "accountId": "admin@test",
                                    "roleName": "admin"}},
                                {"createAsset": {
                                    "assetName": "coin",
                                    "domainId": "test",
                                    "precision": 2}},
                            ]}}}]}}}


def test_genesis_markdown_tables():
    md = genesis.genesis_markdown_from_json(_genesis_json())

    assert "## Domains" in md
    assert "| test | user |" in md

    assert "## Assets" in md
    assert "| coin#test | 2 |" in md

    assert "## Roles" in md
    assert "can_create_account" in md
    assert "can_transfer" in md

    assert "## Accounts" in md
    # admin@test gets the domain default role (user) plus appended admin
    assert "| admin@test | user, admin |" in md
    # permissions of both roles are merged
    assert "can_create_account" in md.split("## Accounts")[1]


def test_genesis_markdown_empty_block():
    md = genesis.genesis_markdown_from_json({"block_v1": {}})
    assert "## Domains" in md
    assert "## Accounts" in md
