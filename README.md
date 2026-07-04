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
- `server.cnf` — OpenSSL config used to generate the CSR (not required when `only_key: true`)

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
only_key: false       # optional: generate only a private key, no CSR
```

`only_key` is optional and defaults to `false`. When set to `true`, the directory does
not need a `server.cnf` and the tool only creates the private key. No CSR is generated,
but the tool still pauses so you can copy the key; the temporary key file is securely
erased when the script finishes (unless `--no-cleanup` is used).

ECC keys are generated with `openssl genpkey -algorithm EC` and written in PKCS#8
format (`-----BEGIN PRIVATE KEY-----`).

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

Create a virtual environment and install the package:

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install git+https://github.com/InsonusK/csr-factory.git
```

Or in editable mode while developing:

```bash
git clone https://github.com/InsonusK/csr-factory.git
cd csr-factory
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 3. Run `create-csr`

```bash
# Uses ./servers by default
so
# Or point to a different directory
create-csr /path/to/servers

# Customize the directory for temporary private key files
create-csr /path/to/servers --tmp-key-dir /secure/place

# Enable debug logging
create-csr /path/to/servers -v

# Keep temporary private key files after processing
create-csr /path/to/servers --no-cleanup
```

The tool will:

1. Read every `meta.yaml` under the servers directory.
2. Show a menu: all servers, by tag, or by server name.
3. For each selected server:
   - Generate a private key with the configured algorithm.
   - Save it to `<tmp-key-dir>/<name>.key` so you can copy it to a password manager.
   - Wait for you to press Enter.
   - Generate the CSR in `servers/<name>/request.csr`.
   - Securely erase and remove the temporary private key.

Use `--no-cleanup` to keep all temporary private key files after processing.
Servers with `only_key: true` always keep their key files and do not generate a CSR.

Named key files prevent bulk generation from overwriting a previous server's key
before you have a chance to copy it. The temporary key is also removed if you
interrupt the script (`Ctrl+C`).

---

## Add to another project

### Using `pyproject.toml`

```toml
[project]
dependencies = [
    "csr-factory @ git+https://github.com/InsonusK/csr-factory.git",
]
```

Pin to a specific version when possible:

```toml
[project]
dependencies = [
    "csr-factory @ git+https://github.com/InsonusK/csr-factory.git@v0.1.0",
]
```

### Using `requirements.txt`

Create a `requirements.txt` in your project:

```txt
csr-factory @ git+https://github.com/InsonusK/csr-factory.git
```

Pin to a specific version when possible:

```txt
csr-factory @ git+https://github.com/InsonusK/csr-factory.git@v0.1.0
```

Then create a virtual environment and install the dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Direct install

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install git+https://github.com/InsonusK/csr-factory.git
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
make repo-init
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
