## Finding: CLI crashes with unhandled UnicodeDecodeError on binary/non-UTF-8 input

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
