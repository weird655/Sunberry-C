## Finding: CLI crashes with unhandled FileNotFoundError on nonexistent input file

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
