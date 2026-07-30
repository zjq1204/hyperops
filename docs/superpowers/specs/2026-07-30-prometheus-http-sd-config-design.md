# Prometheus HTTP SD Config Generation

## Goal

Generate a directly usable Prometheus HTTP SD configuration from the actual
HyperOps access origin and the active database Token, without hard-coded hosts,
ports, or a separately managed Token file.

## URL Generation

- The browser-facing reverse proxy must preserve the complete incoming Host
  header, including a non-default port such as `18080`.
- Django continues to build the public base URL from the request scheme and
  forwarded Host.
- The generated URL therefore follows the current access origin automatically:
  IP, domain, HTTP or HTTPS, and optional port.
- No HyperOps source code or environment default hard-codes port `18080` for
  HTTP SD URL generation.

## Token Generation

- The generated YAML uses `authorization.credentials` with the currently
  active database Token.
- The YAML no longer uses `authorization.credentials_file`.
- The configuration endpoint remains restricted to monitoring administrators.
- The normal configuration summary continues to expose only a masked preview;
  the full Token is exposed only as part of the explicitly opened YAML preview.
- Rotating the Token immediately changes future YAML previews. Existing
  Prometheus configuration must be copied again and Prometheus reloaded.

## User Experience

- The YAML preview remains the single copy action for a complete working
  configuration.
- The Token management dialog explains that rotation invalidates the Token
  embedded in an existing Prometheus configuration.
- The UI does not add a second URL input or a hard-coded deployment address.

## Verification

- API tests assert that forwarded Host and protocol values appear in all HTTP
  SD URLs.
- API tests assert that the current Token is embedded and the Token file option
  is absent.
- Nginx configuration validation confirms that the complete Host header is
  forwarded.
- Browser verification confirms the live preview contains `:18080` and the
  current Token while no frontend error is logged.
