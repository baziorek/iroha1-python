#
# Copyright Soramitsu Co., Ltd. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Render a genesis block as Markdown summary tables.

Parses the transactions of a genesis block and produces Markdown tables
for domains, assets, roles and accounts (with resolved permissions),
e.g. for documentation or quick inspection of a network's initial state.

CLI usage::

    python -m iroha.genesis genesis.block.json > genesis.md
"""

import json
import sys

from google.protobuf import json_format

from . import block_pb2
from . import primitive_pb2

_ROLE_NAMES = primitive_pb2.RolePermission.DESCRIPTOR.values_by_number


def _md_table(name, header, rows):
    lines = [f"## {name}", "", "| " + " | ".join(header) + " |",
             "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |"
              for row in rows]
    return "\n".join(lines) + "\n\n"


def genesis_markdown(block):
    """Return Markdown tables describing the genesis block contents.

    :param block: a ``block_pb2.Block`` instance
    :returns: Markdown text with Domains, Assets, Roles and Accounts tables
    """
    domains = {}
    roles = {}
    accounts = {}
    assets = []

    domain_rows = []
    role_rows = []

    if block.HasField("block_v1"):
        payload = block.block_v1.payload
    else:
        payload = block.payload

    for tx in payload.transactions:
        for com in tx.payload.reduced_payload.commands:
            if com.HasField("create_domain"):
                c = com.create_domain
                domains[c.domain_id] = c.default_role
                domain_rows.append([c.domain_id, c.default_role])
            elif com.HasField("create_role"):
                c = com.create_role
                perms = [_ROLE_NAMES[p].name for p in c.permissions]
                roles[c.role_name] = perms
                role_rows.append([c.role_name, ", ".join(perms)])
            elif com.HasField("create_asset"):
                c = com.create_asset
                assets.append(
                    [f"{c.asset_name}#{c.domain_id}", c.precision])
            elif com.HasField("create_account"):
                c = com.create_account
                acc_id = f"{c.account_name}@{c.domain_id}"
                def_role = domains.get(c.domain_id)
                perms = set(roles.get(def_role, ()))
                accounts[acc_id] = ([def_role] if def_role else [], perms)
            elif com.HasField("append_role"):
                c = com.append_role
                acc = accounts.get(c.account_id)
                if acc:
                    acc[0].append(c.role_name)
                    acc[1].update(roles.get(c.role_name, ()))

    account_rows = [
        [acc, ", ".join(roles_acc), ", ".join(sorted(perms))]
        for acc, (roles_acc, perms) in accounts.items()
    ]

    return (
        _md_table("Domains", ["Domain id", "Default Role"], domain_rows)
        + _md_table("Assets", ["Asset id", "Precision"], assets)
        + _md_table("Roles", ["Role Name", "Permissions"], role_rows)
        + _md_table("Accounts", ["Account id", "Roles", "All permissions"],
                    account_rows)
    )


def genesis_markdown_from_json(text):
    """Parse a genesis block JSON document and return Markdown tables.

    :param text: JSON string (or already-parsed dict) of a serialized block
    """
    block = json_format.Parse(
        json.dumps(text) if isinstance(text, dict) else text,
        block_pb2.Block(),
        ignore_unknown_fields=True)
    return genesis_markdown(block)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("Usage: python -m iroha.genesis <genesis-block.json>",
              file=sys.stderr)
        return 1
    with open(argv[0]) as f:
        print(genesis_markdown_from_json(f.read()), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
