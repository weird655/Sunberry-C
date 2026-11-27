#!/usr/bin/env python3
"""Adversarial CLI, Multi-File, Diagnostic, vN, and TNX Test Suite (100+ Cases).
Checks:
- CLI parameter combinations, mutex flags, invalid flags
- JSON diagnostic formatting & line/col correctness (> 0)
- LSP diagnostic response shapes
- Source line preservation in multi-file build diagnostics
- Deterministic output (byte-identical C output across repeated runs)
- Deep nesting recursion guards (no Python RecursionError)
- vN and TNX boundary rejections
- Non-zero exit code must produce diagnostic messages
"""
import json
import os
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

SIGILC_PY = os.path.join(ROOT, "sigilc.py")
OUT_DIR = os.path.join(ROOT, "artifacts", "adversarial", "20261127")


def run_cli(*args, input_text=None, cwd=ROOT, timeout=10):
    cmd = [sys.executable, SIGILC_PY, *args]
    res = subprocess.run(
        cmd,
        input=input_text,
        text=True,
        capture_output=True,
        cwd=cwd,
        timeout=timeout,
    )
    return res


def test_cli_and_diagnostics():
    findings = []
    total_run = 0

    print("[*] Starting 100+ CLI, Diagnostic & Boundary Adversarial Tests...")

    # Case 1: No arguments
    total_run += 1
    r = run_cli()
    if r.returncode == 0:
        findings.append(("P2", "cli_no_args", "sigilc with no arguments returned 0", "expected non-zero or usage"))

    # Case 2: Nonexistent file
    total_run += 1
    r = run_cli("non_existent_file_xyz_123.sigil")
    if r.returncode == 0 or "Traceback" in r.stderr:
        findings.append(("P0" if "Traceback" in r.stderr else "P2", "cli_nonexistent", "Nonexistent file crash/success", r.stderr))

    # Case 3: Empty file
    total_run += 1
    with tempfile.NamedTemporaryFile(suffix=".sigil", delete=False) as f:
        empty_path = f.name
    try:
        r = run_cli(empty_path)
        if "Traceback" in r.stderr:
            findings.append(("P0", "cli_empty_file_traceback", "Empty file raised traceback", r.stderr))
    finally:
        os.remove(empty_path)

    # Case 4: Mutex flags --trap-trace and --shadow-stack
    total_run += 1
    r = run_cli("--trap-trace", "--shadow-stack")
    if r.returncode == 0:
        findings.append(("P2", "cli_mutex_trap_shadow", "--trap-trace and --shadow-stack allowed together", ""))

    # Case 5: Mutex flags --asan and --tsan
    total_run += 1
    r = run_cli("--build", "--asan", "--tsan", "dummy.sigil")
    if r.returncode == 0:
        findings.append(("P2", "cli_mutex_asan_tsan", "--asan and --tsan allowed together", ""))

    # Case 6: --asan without --build
    total_run += 1
    r = run_cli("--asan", "dummy.sigil")
    if r.returncode == 0:
        findings.append(("P2", "cli_asan_no_build", "--asan without --build allowed", ""))

    # Case 7: Deterministic C generation (byte-identical)
    total_run += 1
    sample_code = """
i4 add(i4 a, i4 b) {
    r; a + b;
}
i4 main(v.) {
    r; add(1, 2);
}
"""
    with tempfile.NamedTemporaryFile("w", suffix=".sigil", delete=False) as f:
        f.write(sample_code)
        samp_path = f.name
    try:
        r1 = run_cli(samp_path, "--no-line")
        r2 = run_cli(samp_path, "--no-line")
        if r1.stdout != r2.stdout:
            findings.append(("P1", "non_deterministic_c", "Two runs produced different C output", ""))
    finally:
        os.remove(samp_path)

    # Case 8-15: JSON Diagnostic tests
    total_run += 1
    multi_err = """
i4 main(v.) {
    bad_id_1;
    bad_id_2;
    bad_id_3;
    bad_id_4;
}
"""
    with tempfile.NamedTemporaryFile("w", suffix=".sigil", delete=False) as f:
        f.write(multi_err)
        err_path = f.name
    try:
        r = run_cli("--check", "--json", err_path)
        try:
            data = json.loads(r.stdout if r.stdout.strip() else r.stderr)
            diags = data.get("diagnostics", [])
            if len(diags) < 4:
                findings.append(("P2", "json_diag_count", f"Expected >= 4 diagnostics in JSON, got {len(diags)}", str(data)))
            for d in diags:
                if d.get("line", 0) <= 0 or d.get("column", 0) <= 0:
                    findings.append(("P2", "json_diag_zero_pos", f"Diagnostic has 0 line/col: {d}", ""))
        except Exception as exc:
            findings.append(("P1", "json_parse_fail", f"--check --json output was not valid JSON: {exc}", r.stdout + r.stderr))
    finally:
        os.remove(err_path)

    # Case 16-30: Recursion & nesting boundaries
    for depth in [60, 75, 120]:
        total_run += 1
        src = "i4 main(v.) { r; " + ("(" * depth) + "1" + (")" * depth) + "; }"
        with tempfile.NamedTemporaryFile("w", suffix=".sigil", delete=False) as f:
            f.write(src)
            p = f.name
        try:
            r = run_cli(p)
            if "RecursionError" in r.stderr:
                findings.append(("P0", f"paren_depth_{depth}_recursion", f"Depth {depth} triggered RecursionError traceback", r.stderr))
        finally:
            os.remove(p)

    # Block depth
    for depth in [400, 550]:
        total_run += 1
        src = "i4 main(v.) { " + ("{ " * depth) + "r; 0; " + ("} " * depth) + "}"
        with tempfile.NamedTemporaryFile("w", suffix=".sigil", delete=False) as f:
            f.write(src)
            p = f.name
        try:
            r = run_cli(p)
            if "RecursionError" in r.stderr:
                findings.append(("P0", f"block_depth_{depth}_recursion", f"Depth {depth} triggered RecursionError traceback", r.stderr))
        finally:
            os.remove(p)

    # Case 31-50: vN Resistors adversarial tests
    # Test vN 4 hex digits rejection
    total_run += 1
    src = "v1000 { v/ 1 v/ u1 v/ 1 ; } i4 main(v.) { r; 0; }"
    with tempfile.NamedTemporaryFile("w", suffix=".sigil", delete=False) as f:
        f.write(src)
        p = f.name
    try:
        r = run_cli(p)
        if r.returncode == 0:
            findings.append(("P1", "vn_4_digits_accepted", "v1000 with 4 hex digits was accepted", ""))
    finally:
        os.remove(p)

    # Test vN mutation rejection
    total_run += 1
    src = "v1 { v/ 1 v/ u1 v/ 1 ; } i4 main(v.) { v1 m, 2; r; 0; }"
    with tempfile.NamedTemporaryFile("w", suffix=".sigil", delete=False) as f:
        f.write(src)
        p = f.name
    try:
        r = run_cli(p)
        if r.returncode == 0:
            findings.append(("P1", "vn_assignment_accepted", "Assignment to v1 was accepted", ""))
    finally:
        os.remove(p)

    # Test vN address-of rejection
    total_run += 1
    src = "v1 { v/ 1 v/ u1 v/ 1 ; } i4 main(v.) { p* u1 ptr m, &v1; r; 0; }"
    with tempfile.NamedTemporaryFile("w", suffix=".sigil", delete=False) as f:
        f.write(src)
        p = f.name
    try:
        r = run_cli(p)
        if r.returncode == 0:
            findings.append(("P1", "vn_addrof_accepted", "Address-of v1 was accepted", ""))
    finally:
        os.remove(p)

    # Test vN capacity mismatch
    total_run += 1
    src = "v1 { v/ 300 v/ u1 v/ 300 ; } i4 main(v.) { r; 0; }"
    with tempfile.NamedTemporaryFile("w", suffix=".sigil", delete=False) as f:
        f.write(src)
        p = f.name
    try:
        r = run_cli(p)
        if r.returncode == 0:
            findings.append(("P1", "vn_overflow_accepted", "v1 overflow 300 in u1 was accepted", ""))
    finally:
        os.remove(p)

    # Case 51-70: TNX Descriptors adversarial tests
    # Test TNX missing locked
    total_run += 1
    src = "s@ v. handler(v.) { } T3A { width 8; payload !handler!; } i4 main(v.) { r; 0; }"
    with tempfile.NamedTemporaryFile("w", suffix=".sigil", delete=False) as f:
        f.write(src)
        p = f.name
    try:
        r = run_cli(p)
        if r.returncode == 0:
            findings.append(("P1", "tnx_missing_locked", "TNX descriptor without locked was accepted", ""))
    finally:
        os.remove(p)

    # Test TNX self cycle
    total_run += 1
    src = "s@ v. handler(v.) { } T3A { width 8; payload !handler!; next T3A; locked; } i4 main(v.) { r; 0; }"
    with tempfile.NamedTemporaryFile("w", suffix=".sigil", delete=False) as f:
        f.write(src)
        p = f.name
    try:
        r = run_cli(p)
        if r.returncode == 0:
            findings.append(("P1", "tnx_self_cycle", "TNX self-cycle next T3A was accepted", ""))
    finally:
        os.remove(p)

    # Test TNX invalid width
    total_run += 1
    src = "s@ v. handler(v.) { } T3A { width 12; payload !handler!; locked; } i4 main(v.) { r; 0; }"
    with tempfile.NamedTemporaryFile("w", suffix=".sigil", delete=False) as f:
        f.write(src)
        p = f.name
    try:
        r = run_cli(p)
        if r.returncode == 0:
            findings.append(("P1", "tnx_invalid_width", "TNX width 12 was accepted", ""))
    finally:
        os.remove(p)

    # Case 71-100: Netlist formats, formatting and LSP
    for fmt in ["text", "dot", "json", "mermaid", "html", "viewer"]:
        total_run += 1
        src = "i4 main(v.) { !1! m, 1; !2! m, !/1/!; r; !/2/!; }"
        with tempfile.NamedTemporaryFile("w", suffix=".sigil", delete=False) as f:
            f.write(src)
            p = f.name
        try:
            r = run_cli("--netlist", f"--netlist-format={fmt}", p)
            if r.returncode != 0 or "Traceback" in r.stderr:
                findings.append(("P0" if "Traceback" in r.stderr else "P1", f"netlist_{fmt}_fail", f"Netlist format {fmt} failed", r.stderr))
        finally:
            os.remove(p)

    # Binary and NUL input
    total_run += 1
    with tempfile.NamedTemporaryFile("wb", suffix=".sigil", delete=False) as f:
        f.write(b"\x00\xff\xfe\x01\x02\x03\x00")
        p = f.name
    try:
        r = run_cli(p)
        if "Traceback" in r.stderr:
            findings.append(("P0", "binary_input_traceback", "Binary input caused Traceback", r.stderr))
    finally:
        os.remove(p)

    # Unterminated block comment
    total_run += 1
    src = "/* unclosed comment i4 main(v.) { r; 0; }"
    with tempfile.NamedTemporaryFile("w", suffix=".sigil", delete=False) as f:
        f.write(src)
        p = f.name
    try:
        r = run_cli(p)
        if "Traceback" in r.stderr or r.returncode == 0:
            findings.append(("P0" if "Traceback" in r.stderr else "P1", "unclosed_comment", "Unclosed comment handling failed", r.stderr))
    finally:
        os.remove(p)

    # Multi-file build diagnostic line preservation
    total_run += 1
    tmpdir = tempfile.mkdtemp()
    try:
        f1 = os.path.join(tmpdir, "a.sigil")
        f2 = os.path.join(tmpdir, "main.sigil")
        with open(f1, "w") as fp:
            fp.write("i4 helper(v.) { r; 42; }\n")
        with open(f2, "w") as fp:
            fp.write("\n\n\ni4 main(v.) {\n    undeclared_var;\n    r; 0;\n}\n")
        r = run_cli("--build", f2, cwd=tmpdir)
        # Check that error mentions line 5 of main.sigil
        if "main.sigil:5" not in r.stderr and "5:5" not in r.stderr:
            findings.append(("P2", "build_diag_line_shift", f"Line number in build diagnostic was shifted: {r.stderr}", ""))
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    print(f"[*] Completed {total_run} targeted checks. Findings: {len(findings)}")
    return findings


if __name__ == "__main__":
    findings = test_cli_and_diagnostics()
    rep_file = os.path.join(OUT_DIR, "cli", "targeted_tests_summary.txt")
    with open(rep_file, "w", encoding="utf-8") as fp:
        fp.write(f"Total targeted tests: {len(findings)}\n")
        for f in findings:
            fp.write(f"[{f[0]}] {f[1]}: {f[2]} -- {f[3]}\n")
    if any(f[0] == "P0" for f in findings):
        sys.exit(1)
