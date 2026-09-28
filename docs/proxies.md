# Probe IP addresses and proxies (planned)

The mail server being probed judges one IP address. That should not be your application's IP, so
a block or blocklisting cannot affect your own mail or reputation. Many hosts also block port 25
outright.

## Approach

Connect to a SOCKS5 proxy on an ordinary port (for example 1080); the proxy makes the port-25
connection. Your host never needs port 25.

    your app  --(1080)-->  SOCKS5 proxy  --(25)-->  recipient mail server

## The PTR / HELO rule

Some large providers expect the connecting IP's reverse DNS to resolve back to the same IP and the
HELO name to match. On a proxy you do not own you cannot set reverse DNS, so you must use the
vendor's advertised HELO name. This is why general-purpose proxy networks generally do not work,
even where port 25 is open.

## Options

| Option | Port 25 | Reverse DNS / HELO | Notes |
|---|---|---|---|
| Verification-focused SOCKS5 pools (e.g. proxy25.com) | built for it | vendor-provided; use their HELO | Ask about dedicated vs shared IPs, terms of use, uptime. Pricing unconfirmed here. |
| Your own extra IPs on a rented server | after provider unblock (varies) | you control both | Best long-term reputation control; retire blocklisted IPs |
| Leased IP block or bring-your-own IPs | depends on host | if the host allows | Only at high volume |
| General proxy networks (Bright Data, Oxylabs, Decodo, IPRoyal, Webshare, SOAX) | usually blocked or restricted | no | Not suitable |
| Residential proxies | blocked | no | Never; see [responsible use](responsible-use.md) |

Vendor terms change; verify current details yourself.

## Planned behaviour

- `SMTP_PROXIES` takes a list of SOCKS5 proxies, each with its own HELO and sender.
- Routing by destination provider: one proxy for one provider, another for a different one.
- Health tracking through the host cache: a proxy refused as "blocked" is rested, the next is used.
- Greylist retries reuse the first attempt's proxy.
- SOCKS support comes from the optional `socks` extra; the core stays dependency-free.
- Scheduled blocklist checks of your probe IPs are a job the host runs.
