---
name: ibb-secret-management
description: Defines secret handling rules for IBB Insurance Portal. Use when editing environment variables, config, CI secrets, Bitrix24 integration, JWT, cookies, SMTP, database, Redis, password reset, one-time login, or token handling.
---

# IBB Secret Management Skill

## Purpose

Use this skill to prevent secrets from being committed, logged, exposed in errors, or stored in plaintext.

IBB Insurance Portal integrates with Bitrix24 and handles authentication. Secrets must be managed strictly.

## Secret types

Treat the following as secrets:

- Bitrix24 webhook URL;
- Bitrix24 access token;
- database password;
- Redis password;
- JWT secret;
- cookie secret;
- SMTP password;
- SMTP token;
- password reset token;
- one-time login token;
- refresh token;
- access token;
- private keys;
- CI deployment keys;
- backup credentials.

## Repository rules

Never commit:

- `.env`;
- `.env.local`;
- `.env.production`;
- `.env.staging`;
- real secrets in YAML;
- real secrets in Docker Compose;
- real secrets in README;
- real secrets in test fixtures.

Allowed:

- `.env.example` with placeholders only.

Example:

```env
BITRIX_WEBHOOK_URL=replace_me
DATABASE_URL=postgresql://user:password@localhost:5432/db
JWT_SECRET=replace_me
SMTP_PASSWORD=replace_me
```

Do not put real values into `.env.example`.

## CI rules

CI must use encrypted secret storage.

Examples:

- GitHub Actions Secrets;
- GitLab CI variables;
- secure deployment secret store.

CI logs must not print secrets.

Do not echo environment variables.

Bad:

```bash
echo $BITRIX_WEBHOOK_URL
```

Good:

```bash
test -n "$BITRIX_WEBHOOK_URL"
```

## Secret scanning

Use secret scanning in CI.

Recommended:

```bash
gitleaks detect --source .
```

CI must fail if secrets are detected.

## Application config rules

Load secrets from environment variables.

Do not hardcode secrets in source code.

Do not expose secrets to frontend.

Frontend must never receive:

- Bitrix24 webhook URL;
- backend JWT secret;
- SMTP credentials;
- database URL;
- Redis URL;
- cookie secret.

All Bitrix24 calls must go through backend.

## Logging rules

Never log secrets.

Never log:

- authorization headers;
- cookies;
- access tokens;
- refresh tokens;
- reset tokens;
- one-time login tokens;
- webhook URLs;
- database URLs with password;
- SMTP password;
- JWT secret.

If configuration validation fails, show only sanitized config key name.

Bad:

```python
logger.error(f"Invalid DATABASE_URL: {database_url}")
```

Good:

```python
logger.error("config_invalid", extra={"key": "DATABASE_URL", "error_code": "CONFIG_INVALID"})
```

## Token storage rules

Password reset tokens and one-time login tokens must be stored only as hashes.

Do not store plaintext token.

Do not log plaintext token.

Do not send token to third-party monitoring.

Recommended fields:

- token_hash;
- user_id;
- expires_at;
- used_at;
- created_at.

## Password rules

Never store plaintext passwords.

Never log passwords.

Store only password hash.

Use strong hashing:

- Argon2id preferred;
- bcrypt acceptable with proper cost.

## Cookie rules

Refresh tokens must be stored in secure, httpOnly cookies.

Use:

- Secure;
- HttpOnly;
- SameSite;
- proper expiration;
- server-side revocation on logout, password change, and user block.

## Bitrix24 rules

Bitrix24 webhook URL is a secret.

Never expose it to browser.

Never log it.

Never store it in frontend.

Never include it in error messages.

If Bitrix24 request fails, log only:

- bitrix_deal_id;
- status_code;
- error_code;
- request_id.

## Acceptance criteria

This skill is satisfied when:

- no real secrets are committed;
- `.env.example` contains placeholders only;
- CI secret scanning is enabled;
- secrets are loaded from environment variables;
- secrets are not exposed to frontend;
- tokens are stored as hashes where applicable;
- secrets are not logged;
- Bitrix24 webhook URL is backend-only.
