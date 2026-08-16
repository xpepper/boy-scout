# Contributing

`main` is protected: direct pushes are not accepted, only pull requests.
Before a PR can merge:

- All 4 CI matrix jobs must pass (`pytest` on ubuntu-latest and macos-latest,
  against Python 3.10 and 3.12).
- The branch must be up to date with `main` (GitHub will ask you to update it
  if it is behind).

No specific reviewer approval count is enforced. That keeps the gate meaningful
without requiring self-approval on a single-maintainer repo.

Windows is deliberately not tested or supported: the plugin uses `fcntl` for
file locking, which does not exist there.

## Running the plugin on itself

The fastest way to see a change behave is to install this checkout as a plugin
in this repository, scoped to you alone:

```bash
claude plugin marketplace add ./ --scope local
claude plugin install boy-scout@boy-scout --scope local -y
```

That points Claude Code at the working tree, so edits take effect on the next
session with no reinstall. It writes `.claude/settings.local.json`, which is
gitignored because it stores an absolute path to your checkout.

To check what Claude Code actually loaded:

```bash
claude plugin validate .            # the manifests
claude plugin validate skills       # and agents, commands
claude plugin details boy-scout@boy-scout   # inventory and token cost
```

To remove it again:

```bash
claude plugin marketplace remove boy-scout
```

## Tests

```bash
python3 -m pytest tests/
```

`pytest` is the only test dependency, and it is dev-only: the plugin itself
stays zero-dependency at runtime.

## Debugging

Running the hooks by hand is covered in [docs/development.md](docs/development.md).
