# Security policy

prebounce is pre-alpha. Please report vulnerabilities in the design or the code responsibly.

## Reporting

Do not open a public issue. Use GitHub's private vulnerability reporting
("Security" tab, "Report a vulnerability", a GitHub security advisory) on this repository.

Please include a description, steps to reproduce and the affected version. You can expect an
acknowledgement within a reasonable time; this is a volunteer-run project.

## Scope

Of particular interest once implemented: SMTP command injection through crafted addresses,
server-side request forgery through the probe agent, credential leakage from proxy settings,
and denial of service through hostile mail server responses.
