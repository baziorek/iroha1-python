import os

import setuptools

with open('README.md', 'r') as readme_file:
    long_description = readme_file.read()

# The version placeholder is substituted by the release pipeline
# (see .jenkinsci/linux-build-wheels.groovy). When it is not substituted
# (e.g. local installs), fall back to the IROHA_PYPI_VERSION environment
# variable or a local development version.
version = '{{ PYPI_VERSION }}'
if '{{ PYPI_VERSION }}' in version:
    version = os.environ.get('IROHA_PYPI_VERSION', '0.0.0.dev0')

setuptools.setup(
    name='iroha',
    version=version,
    description='Python library for Hyperledger Iroha',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Soramitsu Co Ltd',
    author_email='admin@soramitsu.co.jp',
    license='Apache-2.0',
    url='https://github.com/hyperledger/iroha-python',
    packages=setuptools.find_packages(
        exclude=['dist', 'build', '*.pyc', '.DS_Store',
                 '.vscode',  '.idea', '__pycache__', '*.bak']),
    python_requires='>=3.10',
    install_requires=[
        'protobuf>=7.35.1,<8',
        'grpcio>=1.85.3',
        'pynacl>=1.5.0'
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Operating System :: OS Independent'
    ],
    project_urls={
        "Jenkins": "https://jenkins.soramitsu.co.jp/",
        "Nexus": "https://nexus.iroha.tech/",
        "Documentation": "https://iroha.readthedocs.io/en/latest/",
        "Doxygen": "https://docs.iroha.tech/",
        "Source Code": "https://github.com/hyperledger/iroha-python",
    }
)
