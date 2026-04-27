<div align="center">
    <img src="./media/logo.webp" alt="Rimi logo" width="160" height="160"/>
    <h1>rimi</h1>
    <h3><em>A CLI for Rimi e-store.</em></h3>
</div>

<p align="center">
    <strong>Interact with Rimi products, favorites, cart, checkout, wallet, and account data from the command line or an AI agent workflow.</strong>
</p>

<p align="center">
    <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12%2B-blue.svg" alt="Python 3.12+"/></a>
    <a href="https://docs.astral.sh/uv/"><img src="https://img.shields.io/badge/package%20manager-uv-4c8bf5.svg" alt="uv"/></a>
    <a href="./LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License"/></a>
</p>

---

## What Is This?

`rimi` is a command-line interface for `www.rimi.ee`, covering product browsing, favorites, cart, checkout, orders, account profile, and Rimi Money flows.

This project is not an official Rimi client. It sends HTTP requests to Rimi's public website using the same kinds of request shapes a browser session uses.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## Install

Install from the GitHub repository:

```bash
uv tool install rimi --from git+https://github.com/alex-j-b/rimi-cli.git
```

## Authentication

Authenticated commands use a secure local session on your computer. For the operational details, see `AGENTS.md`.

AI coding agents working with the CLI can capture and persist authenticated browser sessions securely on the local machine without exposing credentials in chat.

## Usage

Inspect the command tree:

```bash
rimi --help
rimi products --help
rimi cart show --help
```

Catalog examples:

```bash
rimi products categories
rimi products list --category-id SH-6-6-3 --page 1 --page-size 80 --sort priceunit-desc
rimi products get 4006297
```

Authenticated account/cart examples:

```bash
rimi account whoami
rimi account profile
rimi cart show
rimi cart update-item 4006297 --quantity 2
```

Favorites examples:

```bash
rimi favorites categories
rimi favorites list --category-id SH-12 --page 0
rimi favorites add 4006297
rimi favorites remove 4006297
```

Checkout and wallet examples:

```bash
rimi checkout time-slots --date 2026-05-01
rimi checkout choose-time-slot <time-id>
rimi checkout prices --cart-id <cart-id>
rimi checkout payment-methods --cart-id <cart-id>
rimi wallet balance
rimi wallet apply 3.71
rimi orders current
```

Every command also supports:

```bash
--raw              # print the unprocessed response body
--output <path>    # write raw output to a file; only valid with --raw
```

## Commands

| Area      | Commands                                                                                          |
| --------- | ------------------------------------------------------------------------------------------------- |
| Account   | `account whoami`, `account profile`                                                               |
| Cart      | `cart show`, `cart update-item`, `cart recommendations`                                           |
| Checkout  | `checkout time-slots`, `checkout choose-time-slot`, `checkout prices`, `checkout payment-methods` |
| Favorites | `favorites categories`, `favorites list`, `favorites add`, `favorites remove`                     |
| Orders    | `orders current`                                                                                  |
| Products  | `products categories`, `products list`, `products get`                                            |
| Wallet    | `wallet balance`, `wallet apply`                                                                  |

Public catalog commands may work without a signed-in session. Commands that read or mutate account, favorites, cart, checkout, orders, or wallet state require valid headers from your own signed-in Rimi session.

## Development

Clone the repository and install it as an editable uv tool:

```bash
git clone https://github.com/<owner>/<repo>.git rimi
cd rimi
uv tool install --editable .
```

Run the CLI from the working tree without installing it globally:

```bash
uv run rimi --help
python -m www_rimi_ee --help
```

Command definitions live under `commands/<command>/command.yaml`, with request shaping in `processors/pre.py`, output shaping in `processors/post.py`, fixture evidence in `fixtures/`, and approved JSON contracts in `goldens/`.

## Tests

Install dev/test dependencies, run the offline contract tests, and check formatting/linting:

```bash
uv sync --extra dev
uv run --extra dev python -m pytest -q
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
```

Run one command's contract test:

```bash
uv run --extra dev python -m pytest -q commands/products_list/tests/test_command.py
```

Replay one command from fixtures:

```bash
AUTOCLI_TEST_MODE=true rimi products categories --replay
```

The offline contract tests replay captured fixtures and compare post-processed JSON against approved goldens. They should not need live Rimi access.

## Privacy And Security

- Authenticated requests depend on headers you provide through the system keyring or the `PLAYWRIGHT_HEADERS_JSON` process environment override.
- Treat browser cookies, authorization headers, CSRF/XSRF tokens, cart IDs, order IDs, and profile data as secrets.
- Use this project only with accounts and sessions you are authorized to access, and review Rimi's current terms before automation.

## Built With AutoCLI

This project was built with [AutoCLI](https://github.com/alex-j-b/autocli), a toolkit for creating editable site-specific CLIs.

## License

MIT License. See [LICENSE](./LICENSE).
