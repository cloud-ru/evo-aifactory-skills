# Cloud.ru Account Setup

> **Name:** cloudru-account-setup
> **Description:** Create a Cloud.ru service account, Foundation Models API key, and IAM access key (CP_CONSOLE_KEY_ID/CP_CONSOLE_SECRET). Use when the user needs to bootstrap Cloud.ru API access from scratch.
> **Required tools:** `python3`
> **Required pip:** `httpx`
> **Required pip (browser flow):** `playwright`

## What this skill does

Creates a Cloud.ru service account and the credentials needed for Cloud.ru services:
1. **Foundation Models API key** (`CLOUD_RU_FOUNDATION_MODELS_API_KEY`) — for the Foundation Models API.
2. **IAM access key** (`CP_CONSOLE_KEY_ID` + `CP_CONSOLE_SECRET`) — for IAM token-based authentication used by ML Inference, VM, Managed RAG, AI Agents, and other Cloud.ru services.
3. **Service roles** — automatically attached to the SA (on create or via PATCH for an existing SA): `managed_rag.admin` + `ai-agents.admin` (umbrella role covering agents/systems/mcp-servers/prompts/workflows). Required by `cloudru-managed-rag` and `cloudru-ai-agents`.

After a successful run the user will have all credentials ready to use.

## When to use

- The user wants to set up Cloud.ru API access from scratch.
- The user needs a new service account or API key for Cloud.ru Foundation Models.
- The user needs `CP_CONSOLE_KEY_ID` and `CP_CONSOLE_SECRET` for ML Inference or other IAM-authenticated services.
- The user mentions Cloud.ru onboarding, registration, or bootstrap.

## Browser-assisted flow (recommended)

This flow opens a real browser window. The user only needs to log in — everything else is automated.

### Step 1: Install playwright (one-time)

```bash
pip install playwright && playwright install chromium
```

### Step 2: Run the browser login script

```bash
python3 ./scripts/browser_login.py
```

This opens a Chromium window with the Cloud.ru login page. The user logs in and navigates to their project. The script automatically:
- detects when the user reaches a project page
- extracts the project URL, project_id, and customer_id from the URL
- extracts the bearer token from the browser's localStorage
- outputs a JSON with all extracted values to stdout

Example output:
```json
{
  "project_url": "https://console.cloud.ru/projects/abc-123?customerId=def-456",
  "token": "eyJ...",
  "project_id": "abc-123",
  "customer_id": "def-456"
}
```

> **Security note:** The JSON output contains a short-lived IAM bearer token. Do not redirect stdout to a log file or share the output. The token expires in ~5 minutes but should be treated as sensitive until then.

If the script times out (default 180s), pass `--timeout 300` for more time.

### Step 3: Run the bootstrap script with extracted values

Take the `project_url` and `token` from Step 2 and pass them to the bootstrap script:

```bash
python3 ./scripts/cloudru_account_bootstrap.py \
  --project-url '<project_url from step 2>' \
  --token '<token from step 2>'
```

Add `--customer-id '<customer_id>'` if it was not extracted from the URL (null in the JSON).

### Step 4: Read the result

The bootstrap script outputs JSON with:
- the created service account
- the Foundation Models API key (including the secret)
- the IAM access key (`key_id` and `secret`)
- a `credentials_summary` with all env var values

## Manual / no-browser flow

If the user already has the project URL and token (or doesn't want to use the browser script):

```bash
python3 ./scripts/cloudru_account_bootstrap.py \
  --project-url '<project-url>' \
  --project-id '<project-id>' \
  --customer-id '<customer-id>' \
  --token '<bearer-token>'
```

The token can be extracted manually by opening the browser DevTools console on console.cloud.ru and running:
```javascript
JSON.parse(localStorage["oidc.user:https://id.cloud.ru/auth/system/:e95a1db5-a61c-425b-ae62-26d3a7e224f7"])["access_token"]
```

## Access key creation (CP_CONSOLE_KEY_ID / CP_CONSOLE_SECRET)

The bootstrap script also creates an **access key** for IAM authentication. This is a separate credential from the Foundation Models API key.

To skip access key creation (e.g. if the user only needs Foundation Models), pass `--skip-access-key`.

To customize the access key, use:
- `--access-key-description` (default: `ml-inference-access-key`)
- `--access-key-ttl` (default: 30 days)

## Safe handling

- Treat the returned API key and access key as secrets.
- Show them only when the user explicitly needs them.
- Prefer moving them immediately into env vars or secret storage.
- Do not paste raw keys into config files unless the user asked for plaintext.

## What to return after a successful run

1. The created service account ID.
2. The Foundation Models API key ID and secret (for `CLOUD_RU_FOUNDATION_MODELS_API_KEY`).
3. The IAM access key credentials (for `CP_CONSOLE_KEY_ID` and `CP_CONSOLE_SECRET`).
4. The project ID (for `PROJECT_ID`).
5. A summary of which env vars to set:
   ```
   export CLOUD_RU_FOUNDATION_MODELS_API_KEY=<api_key_secret>
   export CP_CONSOLE_KEY_ID=<access_key_key_id>
   export CP_CONSOLE_SECRET=<access_key_secret>
   export PROJECT_ID=<project_id>
   ```
6. Next step: tell the user they can now use Cloud.ru Foundation Models, ML Inference, and VM skills.
