# Agent Auth (OPA + OpenFGA + LangChain)

A minimal secure AI agent demo that combines:

- **LangChain** for tool-calling agent behavior
- **OPA** for policy-based authorization (action/time rules)
- **OpenFGA** for relationship-based authorization (who can do what on which resource)

The app is implemented in `main.py` and demonstrates two tools (`read_file`, `create_pr`) protected by a combined authorization flow.

## What this project does

When the agent receives a request (for example: "read notes and create a PR"), each tool call is gated by:

1. **OPA check** (`check_opa`) → validates policy rules for the action
2. **OpenFGA check** (`check_fga`) → validates tuple-based permission for user/object/relation

Both checks must pass before the tool executes.

## Project structure

- `main.py` — app entrypoint, LLM + tools + authorization wiring
- `policy.rego` — OPA policy (`package agent.authz`)
- `model.fga` — OpenFGA authorization model
- `notes.txt` — sample file for `read_file` tool
- `pyproject.toml` — Python/dependency config (Python 3.13)

## Authorization model

### OPA (`policy.rego`)

- `read_file` is allowed
- `create_pr` is allowed only between `09:00` and `18:00`
- default is deny

Your code calls:

- `POST http://localhost:8181/v1/data/agent/authz`

This path maps to `package agent.authz` in Rego.

### OpenFGA (`model.fga`)

- `type file` has relation `reader`
- `type repo` has relations `viewer`, `editor`

In code:

- `read_file` requires relation `reader` on object `file:<filename>`
- `create_pr` requires relation `editor` on object `repo:<repo>`

## Prerequisites

- Python `3.13.x`
- `uv` installed
- Running OPA instance on `http://localhost:8181`
- Running OpenFGA instance on `http://localhost:8080`
- OpenFGA store + model already created, and tuple data loaded
- Gemini API key

## Docker quick start

### Start OPA

Use this (preferred):

```bash
docker run --rm -p 8181:8181 \
	--name opa \
	openpolicyagent/opa:latest \
	run --server --addr :8181
```

Equivalent shorter form:

```bash
docker run --rm -p 8181:8181 openpolicyagent/opa:latest run --server
```

Load your policy file into OPA so `POST /v1/data/agent/authz` resolves:

```bash
curl -X PUT http://localhost:8181/v1/policies/agent \
	-H "Content-Type: text/plain" \
	--data-binary @policy.rego
```

### Start OpenFGA

```bash
docker run --rm --name openfga \
	-p 8080:8080 \
	-p 8081:8081 \
	openfga/openfga:latest run
```

## Environment variables

Create `.env` in project root:

```env
GOOGLE_API_KEY=your_google_api_key
STORE_ID=your_openfga_store_id
MODEL_ID=your_openfga_authorization_model_id
```

## Install and run

```bash
uv sync
uv run main.py
```

Expected startup:

```text
🚀 Running Secure Agent...
```

## How tool authorization works

Each tool calls:

```python
asyncio.run(authorize(user, action, relation, object))
```

`authorize` does:

1. `check_opa(action)`
2. `await check_fga(user, relation, object)`

If either fails, execution is blocked with a clear error.

## Notes

- `create_pr` is currently a **mock** implementation and returns a success message.
- The OPA input time in `main.py` is currently hard-coded (`"20:00"`), which will block `create_pr` under the provided policy.
- OpenFGA client sessions are closed after each check to avoid unclosed session warnings.

## Next improvements

- Replace hard-coded time with real current time
- Add fast startup validation for missing `.env` values
- Replace mock `create_pr` with a real GitHub/Git provider integration
- Add tests for policy + relationship authorization behavior
