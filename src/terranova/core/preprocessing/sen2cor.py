"""Sen2Cor subprocess wrapper.

ESA's L1C → L2A atmospheric correction.  Sen2Cor is distributed as a
standalone Python application; we shell out to its ``L2A_Process`` entry
point.  Users supply the Sen2Cor install path once via :class:`Settings`.

This module is a planning surface; the implementation is deferred until
we see real demand.  The shape is recorded here so the public API can be
designed against it.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class Sen2CorResult:
    l2a_safe_path: Path  # the .SAFE directory Sen2Cor writes
    log_path: Path
    elapsed_seconds: float


def run_sen2cor(
    l1c_safe_path: Path,
    *,
    sen2cor_root: Path,
    out_dir: Path | None = None,
    resolution: int = 10,
    extra_args: list[str] | None = None,
) -> Sen2CorResult:
    """Run Sen2Cor on an L1C ``.SAFE`` directory.

    Parameters
    ----------
    l1c_safe_path
        The L1C product, e.g. ``S2A_MSIL1C_..._.SAFE``.
    sen2cor_root
        Where Sen2Cor is installed.  We expect ``bin/L2A_Process`` (Linux)
        or ``L2A_Process.bat`` (Windows) inside this directory.
    out_dir
        Where to write the L2A output.  Defaults to ``l1c_safe_path.parent``.
    resolution
        10 / 20 / 60 — corresponds to Sen2Cor's ``--resolution``.
    extra_args
        Additional flags forwarded to ``L2A_Process``.
    """
    import platform
    import time

    l1c_safe_path = Path(l1c_safe_path)
    sen2cor_root = Path(sen2cor_root)
    out_dir = Path(out_dir) if out_dir else l1c_safe_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    exe_name = "L2A_Process.bat" if platform.system() == "Windows" else "L2A_Process"
    exe = sen2cor_root / "bin" / exe_name
    if not exe.exists():
        raise FileNotFoundError(f"Sen2Cor not found at {exe}")

    log_path = out_dir / f"{l1c_safe_path.stem}_sen2cor.log"
    cmd = [
        str(exe),
        str(l1c_safe_path),
        "--resolution",
        str(resolution),
        "--output_dir",
        str(out_dir),
        *(extra_args or []),
    ]
    started = time.perf_counter()
    with log_path.open("w", encoding="utf-8") as log:
        proc = subprocess.run(
            cmd,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        )
    elapsed = time.perf_counter() - started
    if proc.returncode != 0:
        raise RuntimeError(
            f"Sen2Cor failed with exit {proc.returncode}; see log at {log_path}"
        )

    # L2A SAFE is conventionally L1C name with MSIL1C → MSIL2A.
    l2a_name = l1c_safe_path.name.replace("MSIL1C", "MSIL2A")
    l2a_path = out_dir / l2a_name
    return Sen2CorResult(l2a_safe_path=l2a_path, log_path=log_path, elapsed_seconds=elapsed)
