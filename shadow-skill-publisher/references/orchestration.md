# Batch, Resume, and Monitor

Read this reference for repeated multi-Skill publishing or when a browser flow
has paused and must continue from durable state.

## Batch preparation

`batch` accepts a JSON manifest. Local preparation runs per entry so one blocked
channel does not erase successful attempts:

```json
{
  "entries": [
    {
      "source": "/absolute/path/to/skill",
      "channels": ["workbuddy", "xiaohongshu-red-skill"],
      "profile": "/absolute/path/to/private-profile.json"
    }
  ]
}
```

The command writes `batches/<batch-id>.json`. Its `confirmation_scope` lists
the exact attempt, channel, artifact SHA-256, and confirmation digest. Use
`authorize-batch <batch-id> --kind upload` only after presenting that complete
scope to the user. Submission authorization uses a newly generated receipt
after every plan has been finalized; an old or missing digest blocks the whole
batch instead of partially authorizing changed content.

## Resume

`resume` is read-only. It reconstructs the target URL, account alias, artifact,
fields, confirmation digests, expected next state, and fallback from SQLite.
Treat this packet as the sole browser handoff input. Login or platform walls
pause the attempt without changing its stored state.

The user-facing `artifact_path` remains redacted. On the same machine, resolve
the exact upload target from `artifact_relative_path` beneath the selected
publisher home; this stable locator avoids exposing a private home directory
while keeping browser handoff deterministic.

## Monitor

`monitor` accepts an array of read-only platform observations:

```json
[
  {
    "run_id": "<attempt-id>",
    "channel": "workbuddy",
    "event": "approved",
    "raw_status": "审核通过",
    "product_id": "<platform-id>"
  }
]
```

Each event must be a documented lifecycle event and satisfy the same source
version, platform ID, public URL, and authorization boundaries as `record`.
Unchanged observations produce `notification_required=false` and no ledger
write. Real transitions atomically update SQLite and
`state/publishing-ledger.md`; notify the user only for those transitions or a
new blocker.
