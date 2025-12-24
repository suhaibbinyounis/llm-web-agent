# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do NOT** open a public issue
2. Email the maintainer directly with details
3. Include steps to reproduce if possible
4. Allow reasonable time for a fix before disclosure

## Security Considerations

### Credential Handling

- API keys are stored as `SecretStr` and never logged
- Use the `CredentialVault` for storing sensitive data
- Environment variables are preferred over config files for secrets

### Browser Automation

- The agent can interact with any website you authorize
- Use the `PolicyEngine` to restrict domains and actions
- Enable `SensitiveDetector` to redact PII from logs

### Data Privacy

- Run reports can contain screenshots with sensitive data
- Use the redaction features before sharing logs
- Review the `control/` module for compliance options
