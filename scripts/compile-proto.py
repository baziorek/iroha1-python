#!/usr/bin/env python3
#
# Copyright Soramitsu Co., Ltd. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Compile the Iroha protobuf schema into Python modules.

Requires grpcio-tools (see dev-requirements.txt). The generated *_pb2.py
files are checked into the repository; run this script only when the
schema/*.proto files change.
"""

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROTO_PATH = os.path.join(HERE, '..', 'schema')
OUT_DIR = os.path.join(HERE, '..', 'iroha')

PROTOS = sorted(
    os.path.join(PROTO_PATH, f)
    for f in os.listdir(PROTO_PATH) if f.endswith('.proto')
)
SERVICE_PROTO = os.path.join(PROTO_PATH, 'endpoint.proto')


def compile_proto(proto):
    cmd = [
        sys.executable, '-m', 'grpc_tools.protoc',
        '--proto_path=' + PROTO_PATH,
        '--python_out=' + OUT_DIR,
    ]
    if proto == SERVICE_PROTO:
        cmd.append('--grpc_python_out=' + OUT_DIR)
    cmd.append(proto)
    subprocess.run(cmd, check=True)


def fix_imports():
    """Turn absolute sibling imports (``import foo_pb2 as foo__pb2``)
    emitted by protoc into relative ones (``from . import ...``)."""
    pattern = re.compile(r'^import ([a-z_0-9]+_pb2)( as [a-zA-Z_0-9]+)?',
                         re.MULTILINE)
    for name in os.listdir(OUT_DIR):
        if not (name.endswith('_pb2.py') or name.endswith('_pb2_grpc.py')):
            continue
        path = os.path.join(OUT_DIR, name)
        with open(path) as f:
            content = f.read()
        fixed = pattern.sub(r'from . import \1\2', content)
        if fixed != content:
            with open(path, 'w') as f:
                f.write(fixed)


def main():
    for proto in PROTOS:
        print('compiling', os.path.basename(proto))
        compile_proto(proto)
    fix_imports()
    print('Done.')


if __name__ == '__main__':
    main()
