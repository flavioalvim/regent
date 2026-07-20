#!/usr/bin/env python3
"""Appends the CURRENT template hashes to templates/MANIFEST.json (release step).

Run after editing any seeded template so hosts on the previous version keep
upgrading cleanly. Idempotent: already-listed hashes are not duplicated.
"""

import hashlib
import json
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "src" / "regent" / "templates"
MANIFEST = TEMPLATES / "MANIFEST.json"


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    changed = False
    for path in sorted(TEMPLATES.rglob("SKILL.md")):
        rel = str(path.relative_to(TEMPLATES))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        known = manifest.setdefault(rel, [])
        if digest not in known:
            known.append(digest)
            changed = True
            print(f"added {rel}: {digest}")
    if changed:
        MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
    else:
        print("manifest already current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
