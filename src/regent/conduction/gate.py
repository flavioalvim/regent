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
             linkage: str, timeout: float = 1800.0, runner=None) -> dict:
    root = Path(root)
    declared_text = Path(declared_in).read_text(encoding="utf-8")
    if command not in declared_text:
        raise ProvenanceError(
            f"gate command not declared verbatim in {declared_in}")

    evidence = EvidenceSet(Path(artifact),
                           {"full": Path(str(artifact) + "-FULL.log")})
    evidence.precheck()
    if runner is None:
        runner = SubprocessRunner()

    result = runner.run(["bash", "-c", command], cwd=str(root), timeout=timeout)
    output = result.output
    output_bytes = len(output.encode("utf-8"))
    truncated = output_bytes > TAIL_LIMIT

    if result.timed_out:
        outcome = "TIMEOUT"
    elif result.exit_code == 0:
        outcome = "GREEN"
    else:
        outcome = "RED"

    if truncated:
        evidence.write_sibling("full", output)  # integral output first
        body = (f"[truncated: full output is {output_bytes} bytes — see "
                f"{evidence.siblings['full'].name}; tail follows]\n"
                + output[-TAIL_LIMIT:])
    else:
        body = output
    evidence.write_main(header(outcome, result.exit_code, linkage,
                               command=command, output_bytes=output_bytes,
                               truncated=truncated), body)

    return {"ok": outcome == "GREEN", "outcome": outcome,
            "exit_code": result.exit_code, "artifact": str(evidence.main)}
