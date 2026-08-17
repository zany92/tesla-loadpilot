# Security policy

## No secrets in this repository - ever

This repository must never contain, in any file or commit history:

- WiFi credentials, ESPHome API encryption keys, OTA passwords,
  fallback-AP passwords;
- the **UDP meter key** (the XXTEA key protecting the meter → charger
  link - whoever holds it can forge the measurements the wallbox acts on);
- private IP addresses, MAC addresses, or entity ids of a real
  installation;
- tokens or credentials of any kind.

Mechanics:

- every ESPHome YAML references secrets via `!secret` only;
- `esphome/secrets.yaml.example` documents the required keys with dummy
  values; the real `secrets.yaml` is listed in `.gitignore` and never
  committed;
- reference/example configs are sanitised (placeholders such as
  `<IP_NOEUD_BORNE>`); when copying anything from a live installation,
  re-apply the sanitisation - never assume it carries over.

**If a secret ever lands in a commit**: treat it as compromised. Rotate it
at the source (new WiFi password, regenerate the ESPHome API key, new UDP
key on *both* nodes, new OTA password), then rewrite/remove the offending
history before any push. Rotation comes first; history cleanup second.

## Threat model of the UDP meter link

The meter → charger measurement link is broadcast on the LAN. It is
protected by ESPHome `packet_transport` encryption (**XXTEA**, key hashed
SHA-256) with **rolling code** (anti-replay, flash-persisted). Without the
key, forging the measurements published to the wallbox from the LAN is not
possible; replayed packets are rejected. Defence in depth, not a
substitute for a sane LAN: keep the key secret and rotate it if in doubt.

Fail-safe posture: if the measurement chain is silenced or tampered into
silence, the charger node publishes the main-breaker value → zero margin →
**charging blocked**. The failure mode of the system is "no charge", never
"uncontrolled charge".

## Reporting a vulnerability

Please **do not open a public issue** for security-relevant findings
(anything enabling measurement forgery, bypass of the fail-safe, or
extraction of secrets). Use GitHub's **private vulnerability reporting**
("Report a vulnerability" on the Security tab) so the report stays
private while it is assessed. You should get a first response within a
week. Coordinated disclosure appreciated: give us a reasonable window to
ship a fix before publishing details.

Electrical-safety caveat: this project supervises a 230 V charging
appliance. Software mitigations never replace the electrical protections
(breakers, RCDs) of the installation - see the safety warnings in the
README and [`docs/INSTALL_FR.md`](docs/INSTALL_FR.md).
