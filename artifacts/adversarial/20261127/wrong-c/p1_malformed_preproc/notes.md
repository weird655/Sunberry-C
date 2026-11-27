## Finding: Lexer passes through malformed preprocessor directives, generating uncompilable C

- Severity: P1
- Commit: d9c2e76
- Command: python sigilc.py input.sigil -o out.c && gcc -std=c99 out.c
- Input: #inclu$e <stdio.h>
- Expected: Lexer/Parser rejects invalid preprocessor directive with line/column diagnostic
- Actual: Silently accepted and emitted as `#inclu$e <stdio.h>`, causing GCC build error
- Repro: compile_source('#inclu$e <stdio.h>\ni4 main(v.) { r; 0; }', 'test.sigil')
- Suspected area: sigilc_core/lexer.py:325-333
- Evidence: See generated.c and gcc.txt
- Is it a known limitation? no
