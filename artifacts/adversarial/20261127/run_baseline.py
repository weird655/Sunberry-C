#!/usr/bin/env python3
"""Run all baseline checks specified in ADVERSARIAL_TESTING_GEMINI.md
Saves all outputs to artifacts/adversarial/20261127/baseline/
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
BASE_OUT = os.path.join(ROOT, "artifacts", "adversarial", "20261127", "baseline")
os.makedirs(BASE_OUT, exist_ok=True)

STEPS = [
    ("check_coverage", [sys.executable, "tools/check.py", "--coverage"]),
    ("fuzz_1000", [sys.executable, "tools/fuzz.py", "--iterations", "1000", "--seed", "20261127"]),
    ("propgen_300", [sys.executable, "tools/propgen.py", "--count", "300", "--seed", "20261127"]),
    ("runcheck_300", [sys.executable, "tools/runcheck.py", "--count", "300", "--seed", "20261127"]),
    ("difftest", [sys.executable, "tools/difftest.py"]),
]


def run():
    print("=== RUNNING BASELINE SUITE ===")
    results = {}
    for name, cmd in STEPS:
        print(f"\n[*] Running: {' '.join(cmd)}")
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        log_file = os.path.join(BASE_OUT, f"{name}.log")
        with open(log_file, "w", encoding="utf-8") as fp:
            fp.write(f"CMD: {' '.join(cmd)}\nEXIT: {p.returncode}\n\nSTDOUT:\n{p.stdout}\n\nSTDERR:\n{p.stderr}\n")
        print(f"    Exit code: {p.returncode}")
        print(f"    Output tail: {p.stdout.strip().splitlines()[-1] if p.stdout.strip() else 'No stdout'}")
        if p.stderr.strip():
            print(f"    Stderr tail: {p.stderr.strip().splitlines()[-1]}")
        results[name] = p.returncode

    print("\n=== BASELINE SUMMARY ===")
    all_ok = True
    for name, rc in results.items():
        status = "PASS" if rc == 0 else f"FAIL ({rc})"
        print(f"  [{status}] {name}")
        if rc != 0:
            all_ok = False

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(run())
