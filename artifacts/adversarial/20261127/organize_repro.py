#!/usr/bin/env python3
"""Organize minimal repro cases and artifacts for Round 1 report."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
OUT_DIR = os.path.join(ROOT, "artifacts", "adversarial", "20261127")

# Repro 1: P0 Nonexistent file
d1 = os.path.join(OUT_DIR, "crashes", "p0_cli_nonexistent")
os.makedirs(d1, exist_ok=True)
with open(os.path.join(d1, "command.txt"), "w", encoding="utf-8") as f:
    f.write("python sigilc.py nonexistent_file.sigil\n")
p1 = subprocess.run([sys.executable, "sigilc.py", "nonexistent_file.sigil"], cwd=ROOT, capture_output=True, text=True)
with open(os.path.join(d1, "stderr.txt"), "w", encoding="utf-8") as f:
    f.write(p1.stderr)
with open(os.path.join(d1, "exit.txt"), "w", encoding="utf-8") as f:
    f.write(str(p1.returncode))
with open(os.path.join(d1, "notes.md"), "w", encoding="utf-8") as f:
    f.write("""## Finding: CLI crashes with unhandled FileNotFoundError on nonexistent input file

- Severity: P0
- Commit: d9c2e76
- Command: python sigilc.py nonexistent_file.sigil
- Input: Nonexistent file path
- Expected: Clean stderr message "error: 'nonexistent_file.sigil' is not a file or directory" with exit code != 0
- Actual: Python traceback (FileNotFoundError: [Errno 2] No such file or directory)
- Repro: Run `python sigilc.py <nonexistent-file>`
- Suspected area: sigilc_core/cli.py:162
- Evidence: See stderr.txt
- Is it a known limitation? no
""")

# Repro 2: P0 Binary / non-UTF8 input
d2 = os.path.join(OUT_DIR, "crashes", "p0_cli_binary_utf8")
os.makedirs(d2, exist_ok=True)
bin_path = os.path.join(d2, "input.sigil")
with open(bin_path, "wb") as f:
    f.write(b"\x00\xff\xfe\x01\x02")
with open(os.path.join(d2, "command.txt"), "w", encoding="utf-8") as f:
    f.write(f"python sigilc.py {bin_path}\n")
p2 = subprocess.run([sys.executable, "sigilc.py", bin_path], cwd=ROOT, capture_output=True, text=True)
with open(os.path.join(d2, "stderr.txt"), "w", encoding="utf-8") as f:
    f.write(p2.stderr)
with open(os.path.join(d2, "exit.txt"), "w", encoding="utf-8") as f:
    f.write(str(p2.returncode))
with open(os.path.join(d2, "notes.md"), "w", encoding="utf-8") as f:
    f.write("""## Finding: CLI crashes with unhandled UnicodeDecodeError on binary/non-UTF-8 input

- Severity: P0
- Commit: d9c2e76
- Command: python sigilc.py <binary-file>
- Input: File containing non-UTF-8 bytes (e.g. 0xff 0xfe)
- Expected: Clean stderr message "error: invalid UTF-8 encoding in '<file>'" without Python traceback
- Actual: Python traceback (UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff...)
- Repro: Create file with binary bytes and invoke sigilc
- Suspected area: sigilc_core/cli.py:162-163
- Evidence: See stderr.txt
- Is it a known limitation? no
""")

# Repro 3: P0 Directory argument without --build
d3 = os.path.join(OUT_DIR, "crashes", "p0_cli_directory")
os.makedirs(d3, exist_ok=True)
with open(os.path.join(d3, "command.txt"), "w", encoding="utf-8") as f:
    f.write("python sigilc.py tools\n")
p3 = subprocess.run([sys.executable, "sigilc.py", "tools"], cwd=ROOT, capture_output=True, text=True)
with open(os.path.join(d3, "stderr.txt"), "w", encoding="utf-8") as f:
    f.write(p3.stderr)
with open(os.path.join(d3, "exit.txt"), "w", encoding="utf-8") as f:
    f.write(str(p3.returncode))
with open(os.path.join(d3, "notes.md"), "w", encoding="utf-8") as f:
    f.write("""## Finding: CLI crashes with unhandled PermissionError/IsADirectoryError when passing directory without --build

- Severity: P0
- Commit: d9c2e76
- Command: python sigilc.py tools
- Input: Existing directory path without specifying --build
- Expected: Clean error message "error: 'tools' is a directory; use --build to compile projects"
- Actual: Python traceback (PermissionError / IsADirectoryError)
- Repro: Run `python sigilc.py <directory-name>`
- Suspected area: sigilc_core/cli.py:162
- Evidence: See stderr.txt
- Is it a known limitation? no
""")

# Repro 4: P1 Malformed preprocessor passthrough
d4 = os.path.join(OUT_DIR, "wrong-c", "p1_malformed_preproc")
os.makedirs(d4, exist_ok=True)
src_code = "#inclu$e <stdio.h>\n\ni4 main(v.) {\n    r; 0;\n}\n"
with open(os.path.join(d4, "input.sigil"), "w", encoding="utf-8") as f:
    f.write(src_code)
with open(os.path.join(d4, "command.txt"), "w", encoding="utf-8") as f:
    f.write("python sigilc.py input.sigil -o out.c && gcc -std=c99 out.c\n")
import sigilc
c_out = sigilc.compile_source(src_code, "test.sigil")
with open(os.path.join(d4, "generated.c"), "w", encoding="utf-8") as f:
    f.write(c_out)
p4 = subprocess.run(["gcc", "-std=c99", "-fsyntax-only", "-x", "c", "-"], input=c_out, text=True, capture_output=True)
with open(os.path.join(d4, "gcc.txt"), "w", encoding="utf-8") as f:
    f.write(p4.stderr)
with open(os.path.join(d4, "notes.md"), "w", encoding="utf-8") as f:
    f.write("""## Finding: Lexer passes through malformed preprocessor directives, generating uncompilable C

- Severity: P1
- Commit: d9c2e76
- Command: python sigilc.py input.sigil -o out.c && gcc -std=c99 out.c
- Input: #inclu$e <stdio.h>
- Expected: Lexer/Parser rejects invalid preprocessor directive with line/column diagnostic
- Actual: Silently accepted and emitted as `#inclu$e <stdio.h>`, causing GCC build error
- Repro: compile_source('#inclu$e <stdio.h>\\ni4 main(v.) { r; 0; }', 'test.sigil')
- Suspected area: sigilc_core/lexer.py:325-333
- Evidence: See generated.c and gcc.txt
- Is it a known limitation? no
""")

print("[*] Repro artifacts successfully created.")
