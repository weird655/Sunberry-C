## Finding: CLI crashes with unhandled PermissionError/IsADirectoryError when passing directory without --build

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
