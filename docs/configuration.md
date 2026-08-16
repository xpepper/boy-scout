# Configuration reference

There is almost nothing to configure, and that is deliberate. What gets
recorded is Claude's judgment, not a threshold, so there is no dial that would
make it record better or worse.

The plugin auto-creates `.claude/boy-scout-config.json` with defaults the first
time the Stop hook runs in a project. You can also write the file yourself
beforehand. User values are merged over the defaults section by section, so a
partial file is fine: anything you leave out keeps its default.

Full defaults:

```json
{
  "session": {
    "triage_threshold": 20
  }
}
```

## `session`

| Key | Default | What it does |
|-----|---------|--------------|
| `triage_threshold` | `20` | When the open (non-dismissed) backlog has reached this many items, the Stop hook appends a "backlog has grown" nudge to its summary. The nudge only ever rides along with an actual new-findings summary, so it cannot turn into a nag on idle stops. |

Raise it if you are happy carrying a longer list; lower it to be told sooner.
Setting it very high effectively turns the nudge off, which is a decision to
let the backlog grow unremarked — the failure mode the plugin exists to
prevent.

## What used to be here

Earlier versions shipped a `detection` section configuring static detectors
(`patterns`, `sensitivity`, `ignore_paths`, `ignore_tests`) that ran on every
file write. That channel has been removed: it reported what a linter reports,
which is exactly what `record-opportunity` is told to drop rather than record.
[How it works](how-it-works.md) has the reasoning.

An existing config file with a `detection` section keeps working. The section
is ignored, and can be deleted.
