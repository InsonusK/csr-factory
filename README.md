# csr-factory

Generate private keys and Certificate Signing Requests (CSRs) for servers from a
directory of per-server configs.

This repository is both a reusable Python library and a command-line tool called
`create-csr`.

---

## Quick start

### 1. Create a `servers` directory

Each subdirectory represents one server and must contain:

- `meta.yaml` — server metadata
- `server.cnf` — OpenSSL config used to generate the CSR

Example:

```text
servers/
├── api1/
│   ├── meta.yaml
│   └── server.cnf
└── web1/
    ├── meta.yaml
    └── server.cnf
```

`meta.yaml` format:

```yaml
name: api1
tags:
  - api
  - prod
algorithm: ECC P-256  # rsa 2048 | rsa 4096 | ECC P-256 | ECC P-384
```

`server.cnf` is a standard OpenSSL request config, for example:

```ini
[ req ]
prompt = no
distinguished_name = req_dn

[ req_dn ]
O = Insonus
CN = api1.example.com
```

### 2. Install the library

From the repository:

```bash
pip install git+https://github.com/InsonusK/csr-factory.git
```

Or in editable mode while developing:

```bash
git clone https://github.com/InsonusK/csr-factory.git
cd csr-factory
pip install -e ".[dev]"
```

### 3. Run `create-csr`

```bash
# Uses ./servers by default
create-csr

# Or point to a different directory
create-csr /path/to/servers

# Customize the temporary private key path
create-csr /path/to/servers --tmp-key /secure/place/private.key

# Enable debug logging
create-csr /path/to/servers -v
```

The tool will:

1. Read every `meta.yaml` under the servers directory.
2. Show a menu: all servers, by tag, or by server name.
3. For each selected server:
   - Generate a private key with the configured algorithm.
   - Save it to the temporary key path so you can copy it to a password manager.
   - Wait for you to press Enter.
   - Generate the CSR in `servers/<name>/request.csr`.
   - Remove the temporary private key.

The temporary key is also removed if you interrupt the script (`Ctrl+C`).

---

## Add to another project

Add the dependency to your project:

```bash
pip install git+https://github.com/InsonusK/csr-factory.git
```

Or in `pyproject.toml`:

```toml
[project]
dependencies = [
    "csr-factory @ git+https://github.com/InsonusK/csr-factory.git",
]
```

After installation the `create-csr` command is available in the environment.

You can also use the library from Python code:

```python
from pathlib import Path
from csr_factory.core import load_servers, generate_key, generate_csr

servers = load_servers(Path("servers"))
for server in servers:
    print(server.name, server.algorithm)
    # generate_key(server.algorithm, Path("tmp.key"))
    # generate_csr(Path("tmp.key"), server.config_path, server.csr_path)
```

---

## Development

Create a virtual environment and install in editable mode:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run the tests:

```bash
pytest
```

The test suite requires OpenSSL to be installed.

---

## CI

Tests run automatically via GitHub Actions on every pull request to `develop`
or `master`. See `.github/workflows/tests.yml`.

---

## AI skills

This project uses [ai-skills-manager](https://github.com/InsonusK/ai-skills-manager).

### Workspace init (Windows)

```bash
make aism-init
make aism-sync
```
