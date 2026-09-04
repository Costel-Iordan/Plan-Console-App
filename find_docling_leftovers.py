#!/usr/bin/env python3
"""Report leftover files/folders from an interrupted `pip install docling`.

READ-ONLY: this script deletes nothing. It scans the locations where pip,
build backends (setuptools/wheel/hatchling) and docling's model cache leave
files behind, sizes them, and classifies each item as:

    SAFE      - pip/temp/build cache; deleting never breaks anything
    CHECK     - probably safe, but look at the item first
    INSTALLED - a real installed package (delete with pip uninstall, not by hand)

Usage:
    py find_docling_leftovers.py            # report only
    py find_docling_leftovers.py --json     # machine-readable output
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------- helpers
def dir_size(path: Path) -> int:
    total = 0
    try:
        for root, _dirs, files in os.walk(path, onerror=lambda e: None):
            for f in files:
                try:
                    total += (Path(root) / f).stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


def fmt(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:,.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n:,.1f} GB"


def mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def age_str(ts: float) -> str:
    if ts == 0:
        return "?"
    days = (time.time() - ts) / 86400
    return f"{days:.0f}d ago" if days >= 1 else "today"


# ------------------------------------------------------------- locations
def user_dirs():
    home = Path.home()
    localapp = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
    temp = Path(os.environ.get("TEMP", localapp / "Temp"))
    return home, localapp, temp


def scan_pip_temp(temp: Path):
    """pip leaves pip-* and tmp* dirs in %TEMP% when an install is killed."""
    prefixes = ("pip-", "tmp", "pip-unpack", "pip-install", "pip-build",
                "pip-modernize", "pip-req")
    found = []
    if not temp.is_dir():
        return found
    for entry in temp.iterdir():
        try:
            name = entry.name.lower()
        except OSError:
            continue
        if not any(name.startswith(p.lower()) for p in prefixes):
            continue
        # only report items touched in the last 30 days (old tmp* files are
        # just normal Windows temp noise)
        if name.startswith("tmp") and time.time() - mtime(entry) > 30 * 86400:
            continue
        found.append((entry, "SAFE",
                      "pip temp dir from an interrupted install"))
    return found


def scan_pip_cache(localapp: Path):
    cache = localapp / "pip" / "cache"
    if cache.exists():
        return [(cache, "SAFE",
                 "pip download/wheel cache - always safe to delete "
                 "(pip re-downloads on demand)")]
    return []


def scan_docling_caches(home: Path, localapp: Path):
    """docling model/artifact caches (downloaded ML models can be large)."""
    out = []
    for c in (home / ".cache" / "docling",
              home / ".cache" / "huggingface",
              localapp / "docling",
              home / ".docling"):
        if c.exists():
            out.append((c, "CHECK",
                        "docling/HuggingFace model cache - safe to delete "
                        "unless other ML tools share the HF cache"))
    return out


def scan_build_leftovers(home: Path):
    out = []
    for name in ("build", "dist", "*.egg-info"):
        pass
    # partial source checkouts / build dirs in the user profile
    for candidate in (home / "build", home / "docling",
                      home / "docling-serve", home / "docling-core"):
        if candidate.exists():
            out.append((candidate, "CHECK",
                        "possible source checkout/build dir in home - "
                        "inspect before deleting"))
    return out


def scan_site_packages():
    """Partially-installed docling packages in site-packages."""
    try:
        import importlib.util
        spec = importlib.util.find_spec("docling")
    except (ImportError, ValueError, ModuleNotFoundError):
        spec = None
    out = []
    candidates = ["docling", "docling_core", "docling_ibm_models",
                  "docling_parse", "docling_serve"]
    search_paths = []
    if spec and spec.submodule_search_locations:
        search_paths.extend(Path(p).parent for p in spec.submodule_search_locations)
    else:
        import site
        search_paths.extend(Path(p) for p in site.getsitepackages())
        search_paths.append(Path(site.getusersitepackages()))
    seen = set()
    for sp in search_paths:
        if not sp.is_dir() or sp in seen:
            continue
        seen.add(sp)
        for name in candidates:
            for entry in (sp / name,):
                if entry.exists():
                    out.append((entry, "INSTALLED",
                                "installed package - remove with "
                                f"`py -m pip uninstall {name.replace('_', '-')}` "
                                "or `pip uninstall docling`"))
        # stray dist-info from a killed install
        for entry in sp.glob("docling*dist-info"):
            out.append((entry, "INSTALLED",
                        "package metadata - remove via pip uninstall"))
    return out


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true", help="output JSON")
    args = ap.parse_args()

    home, localapp, temp = user_dirs()

    items = []
    items += scan_pip_temp(temp)
    items += scan_pip_cache(localapp)
    items += scan_docling_caches(home, localapp)
    items += scan_build_leftovers(home)
    items += scan_site_packages()

    report = []
    for path, safety, reason in items:
        size = dir_size(path) if path.is_dir() else path.stat().st_size
        report.append({
            "path": str(path),
            "size_bytes": size,
            "size": fmt(size),
            "safety": safety,
            "reason": reason,
            "last_modified": age_str(mtime(path)),
        })

    report.sort(key=lambda r: r["size_bytes"], reverse=True)
    total = sum(r["size_bytes"] for r in report if r["safety"] == "SAFE")

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    if not report:
        print("No docling/pip leftovers found. Nothing to clean up.")
        return 0

    print("Leftover files/folders from the interrupted docling install\n")
    for r in report:
        print(f"[{r['safety']:9}] {r['size']:>12}  {r['path']}")
        print(f"            modified {r['last_modified']} - {r['reason']}\n")

    print("-" * 70)
    print(f"Reclaimable right now (SAFE items): {fmt(total)}")
    print("\nRecommended cleanup commands (run manually after reviewing):")
    print("  py -m pip cache purge                 # pip download cache")
    print("  # delete the [SAFE] pip-* / tmp* dirs in %TEMP% listed above")
    print("  py -m pip uninstall docling docling-core docling-ibm-models "
          "docling-parse   # only if listed as INSTALLED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
