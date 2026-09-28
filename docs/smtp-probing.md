# SMTP probing (planned)

The library connects to the recipient's mail server as a sender would, asks whether it would
accept mail for the address, and disconnects **before any message is sent**. `DATA` is never issued.

## The conversation

    S: 220 mx.example-mail.com ESMTP
    C: EHLO verify.yourdomain.example
    S: 250 ... STARTTLS
    C: STARTTLS
    C: MAIL FROM:<probe@yourdomain.example>
    S: 250 2.1.0 OK
    C: RCPT TO:<jane@example.com>
    S: 250 2.1.5 OK
    C: RCPT TO:<random-unlikely-name@example.com>   (catch-all test)
    S: 550 5.1.1 No such user
    C: RSET
    C: QUIT

## Scenarios

| Scenario | Server behaviour | Outcome |
|---|---|---|
| Mailbox exists | real accepted, random refused | deliverable |
| No such user | 550 5.1.1 | undeliverable |
| Catch-all | both accepted | risky, `accept_all` |
| Greylisted | 450 4.2.0 | pending, retry later |
| Mailbox full | 552 5.2.2 | risky, `mailbox_full` |
| Prober blocked | 554 5.7.1 client blocked | unknown, `prober_blocked` |

## Catch-all detection

A random, implausible local part on the same domain is probed. Accepted means the domain accepts
everything and the first answer proves nothing. Outcomes: accepted, refused, inconclusive, not run.

## Greylisting

A temporary refusal returns `pending`. The host retries after several minutes from the same IP,
sender and recipient. See [results](results.md).

## Security gateways

Gateways (Proofpoint, Mimecast, Barracuda and similar) accept every address and reject later. They
are recognised from mail server names and reported as accept-all.

## Provider limits

Yahoo, Outlook.com and Microsoft 365 answer probes unreliably; the library reports risky/unknown
rather than guess.

## Spam traps

Traps are secret by design and cannot be confirmed. The library reports *risk signals* only: typo
domain, recently re-registered domain, blocklisted domain.

## Blocked probers

A refusal of the client (blocklisted IP) says nothing about the address. It is never reported as
"invalid"; the proxy is rested and the host is alerted through the result.
