#!/usr/bin/env python3
#
# Copyright Soramitsu Co., Ltd. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Download the Iroha shared model proto files into the schema folder."""

import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))

BASE_URL = 'https://raw.githubusercontent.com/hyperledger/iroha/master/shared_model/schema/'

FILES = [
    'block.proto',
    'commands.proto',
    'endpoint.proto',
    'primitive.proto',
    'proposal.proto',
    'qry_responses.proto',
    'queries.proto',
    'transaction.proto'
]

for file in FILES:
    print(file)
    data = urllib.request.urlopen(BASE_URL + file)
    print('\tdownloading')
    with open(os.path.join(HERE, '..', 'schema', file), 'wb') as out:
        out.write(data.read())
        out.flush()
    print('\tsaved')

print('Done.')
