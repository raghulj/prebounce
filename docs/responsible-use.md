# Responsible use

Mailbox probing touches other people's mail servers and concerns personal data. This page is
guidance, **not legal advice**.

## Probing etiquette (defaults)

- Identify yourself honestly: a real HELO name whose reverse DNS matches your IP, and a real sender
  address on a domain you control, with a contact page.
- Limit connections per mail server via the rate limiter; back off on every temporary refusal.
- Reuse one connection for several addresses at the same domain.
- **Never send `DATA`.** Nothing is ever delivered.
- Stop probing a server that blocks you; do not rotate IPs to evade a block.

## Things this project will not support

- Residential proxies, or any network of devices whose owners have not clearly consented.
- Evading blocklists or rate limits, or spoofing another organisation's identity.
- Harvesting: verifying addresses to build lists you have no basis to hold.

## Privacy and GDPR

An email address is personal data. If you verify addresses of people in the EU or UK you need a
lawful basis (for example legitimate interest in keeping your own list accurate), should minimise
what you store, respect retention limits and erasure requests, and check any proxy or agent
provider is a suitable processor. Cached results and raw server replies may contain personal data.
Take advice for your jurisdiction.

## Limits of the result

A verdict is evidence, not certainty. Do not use it as the sole basis for decisions that
significantly affect people.
