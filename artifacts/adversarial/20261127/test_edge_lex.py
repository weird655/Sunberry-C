#!/usr/bin/env python3
"""Edge lexical and syntactic fuzzing."""
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

import sigilc

edge_inputs = [
    '\\',
    '\\n',
    '\'',
    '\"',
    '0x',
    '0b',
    '0x1p',
    '1e',
    '1e+',
    '1.2.3',
    '09',
    '0778',
    '!',
    '!/',
    '!/1',
    '!/1/',
    '!/1/!',
    '!>1',
    '!>1<',
    '!>1<!',
    '!<+',
    '!<+cat',
    '!<+cat+',
    '!<+cat+>',
    '!v',
    '!vG!',
    '!v1234!',
    'v1 {',
    'v1 { v/ 1 }',
    'v1 { v/ 1 v/ u1 }',
    'v1 { v/ 1 v/ u1 v/ 1 }',
    'T',
    'T0',
    'T0A',
    'T0A {',
    'T0A { width',
    'T0A { width 8;',
    'T0A { width 8; payload',
    'a@(',
    'a@(alias)',
    's{',
    'u{',
    'e{',
    'w~ (',
    'i? (',
    's? (',
    'r;',
    'o!',
    'p*',
    'c@',
    'f^ (',
    't! (',
    '#',
    '#line',
    '#define',
    '#define 123',
    '#define FOO',
    '#include',
    '#include <',
    '#include "abc',
    '#pragma',
]

crashes = []
for inp in edge_inputs:
    try:
        sigilc.compile_source(inp, "edge.sigil")
    except (sigilc.LexerError, sigilc.ParseError, sigilc.SemanticError):
        pass
    except Exception as exc:
        crashes.append((inp, type(exc).__name__, str(exc)))

print(f"Tested {len(edge_inputs)} edge inputs. Uncaught exceptions: {len(crashes)}")
for inp, t, e in crashes:
    print(f"CRASH on {repr(inp)}: {t} -> {e}")

if crashes:
    sys.exit(1)
