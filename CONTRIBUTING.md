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

## Tests

```bash
python3 -m pytest tests/
```

`pytest` is the only test dependency, and it is dev-only: the plugin itself
stays zero-dependency at runtime.

## Debugging

Running the hooks by hand is covered in [docs/development.md](docs/development.md).
