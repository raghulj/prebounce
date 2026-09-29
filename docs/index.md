# prebounce documentation

> Pre-alpha. Offline checks, DNS lookup, scoring and the `Verifier` API are implemented.
> Mailbox probing (SMTP probing, proxies, probe agent) is not implemented yet; those pages describe
> the planned design.

- [Getting started](getting-started.md): install and first call
- [Pipeline](pipeline.md): the nine stages of one `verify()` call
- [Results](results.md): result object, verdicts, send recommendations, reasons, pending
- [Configuration](configuration.md): settings and host callbacks
- [SMTP probing](smtp-probing.md): the mailbox conversation, catch-all, greylisting, provider limits
- [Proxies](proxies.md): keeping your application's IP out of it
- [Disposable domains](disposable-domains.md): sources, refresh, merge rules
- [Comparison](comparison.md): how the plan differs from other tools
- [Responsible use](responsible-use.md): etiquette, ethics, legal notes
- [Roadmap](roadmap.md): milestones v0.1 to v1.0
- [Design decisions](design-decisions.md): why it is shaped this way
