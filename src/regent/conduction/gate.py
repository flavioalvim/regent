"""`regent gate run` — mechanized gate execution (PLAN-003).

The gate command is NEVER invented by regent: it must appear VERBATIM in the
plan artifact referenced by --declared-in (provenance is checked, not
trusted). Full output is always preserved: <=200 KiB inline in the artifact;
above that, header+tail with DECLARED truncation plus the integral output in
<artifact>-FULL.log, all under one atomic evidence-set contract.
"""

from __future__ import annotations

from pathlib import Path

from .evidence import EvidenceSet, header
from .process import SubprocessRunner

TAIL_LIMIT = 200 * 1024


class ProvenanceError(Exception):
    pass


def run_gate(root: Path, *, command: str, declared_in: Path, artifact: Path,
             linkage: str, timeout: float = 1800.0, runner=None, cancel=None) -> dict:
    root = Path(root)
    if not command.strip():
        raise ProvenanceError("empty gate command is never declared")
    declared_text = Path(declared_in).read_text(encoding="utf-8",
                                                errors="replace")
    if command not in declared_text:
        raise ProvenanceError(
            f"gate command not declared verbatim in {declared_in}")

    evidence = EvidenceSet(Path(artifact),
                           {"full": Path(str(artifact) + "-FULL.log")})
    evidence.precheck()
    if runner is None:
        runner = SubprocessRunner()

    # ONE cleanup guard around execution + both publishes (see consult.py).
    try:
        result = runner.run(["bash", "-c", command], cwd=str(root),
                            timeout=timeout, cancel=cancel)
        raw = result.output_bytes
        output_bytes = len(raw)
        truncated = output_bytes > TAIL_LIMIT

        if result.timed_out:
            outcome = "TIMEOUT"
        elif result.exit_code == 0:
            outcome = "GREEN"
        else:
            outcome = "RED"

        if truncated:
            evidence.write_sibling("full", raw)  # integral RAW BYTES first
            tail = raw[-TAIL_LIMIT:].decode("utf-8", errors="replace")
            body = (f"[truncated: full output is {output_bytes} bytes — see "
                    f"{evidence.siblings['full'].name}; tail follows]\n" + tail)
        else:
            body = raw.decode("utf-8", errors="replace")
        evidence.write_main(header(outcome, result.exit_code, linkage,
                                   command=command, output_bytes=output_bytes,
                                   truncated=truncated), body)
    except BaseException:
        evidence.cleanup_orphans()
        raise

    return {"ok": outcome == "GREEN", "outcome": outcome,
            "exit_code": result.exit_code, "artifact": str(evidence.main)}
