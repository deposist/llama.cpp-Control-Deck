# Security Policy

## Supported Versions

The project is pre-1.0. Security fixes are applied to the default branch.

## Reporting a Vulnerability

Please do not open a public issue for vulnerabilities that could expose local
systems, API keys, private prompts, or network services.

Preferred reporting path:

1. Open a private GitHub security advisory for this repository.
2. Include a concise description, reproduction steps, affected files, and impact.
3. Include whether the service was bound to `127.0.0.1`, `0.0.0.0`, or another
   interface.

If private advisories are unavailable, contact the repository owner through
their GitHub profile and avoid sharing exploit details publicly.

## Security Notes

- `llama-server` and the Ollama-compatible proxy are intended for trusted local
  environments by default.
- Binding to `0.0.0.0` exposes the service on the local network. Use a firewall,
  VPN, reverse proxy authentication, or another access-control layer.
- The built-in proxy does not provide full authentication by itself.
- Do not publish `config.json`, logs, API keys, private model paths, or prompt
  data in issues.
