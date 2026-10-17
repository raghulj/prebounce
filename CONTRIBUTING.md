# Contributing to prebounce

prebounce is pre-alpha. The most useful contributions right now are bug reports and review of
the documents in [`docs/`](docs/index.md): wrong assumptions, missing edge cases, better naming.
Open an issue before starting any implementation work so effort is not duplicated.

## Ground rules

- **Clean-room.** Do not copy code, data tables or test fixtures from projects with incompatible
  licences (for example AGPL-licensed verifiers). Ideas and public protocol behaviour (RFCs) are
  fine; text and code are not. If you have read such a project closely, say so in the PR.
- **No network in tests.** Unit tests must run offline. SMTP and DNS are exercised through fakes.
- **Use example addresses only** (`jane@example.com`), never real people's addresses.
- Be polite to mail servers. Nothing that sends `DATA` or evades rate limits will be merged.
  See [responsible use](docs/responsible-use.md).

## Development setup

Use a virtual environment of your choice, then:

    pip install -e ".[dev]"
    ruff check .
    mypy
    pytest

## Pull requests

Keep changes focused, add tests, update docs and `CHANGELOG.md`. By contributing you agree your
work is licensed under the MIT licence. Please follow the [Code of Conduct](CODE_OF_CONDUCT.md).
