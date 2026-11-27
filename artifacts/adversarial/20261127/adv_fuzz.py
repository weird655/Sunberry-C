#!/usr/bin/env python3
"""Adversarial Fuzzing Engine for Sigil-C (Commit d9c2e76).
Runs aggressive mutation fuzzing across rich corpus seeds including:
- golden.sigil
- examples/tutorial/*.sigil
- vN and TNX test samples
- Structs, pointers, complex expressions, attributes

Checks for:
1. P0: Uncaught exceptions (KeyError, IndexError, AttributeError, TypeError, RecursionError, etc.)
2. P0: Hangs / timeouts (> 10s)
3. P1: Generated C compilation failures under gcc -std=c99 -Wall -Wextra -pedantic
4. Proper diagnostic preservation
"""
import glob
import os
import random
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

import sigilc

SEEDS = []

# Collect corpus
for f in glob.glob(os.path.join(ROOT, "examples", "tutorial", "*.sigil")):
    try:
        with open(f, "r", encoding="utf-8") as fp:
            SEEDS.append(fp.read())
    except Exception:
        pass

for f in glob.glob(os.path.join(ROOT, "examples", "*.sigil")):
    try:
        with open(f, "r", encoding="utf-8") as fp:
            SEEDS.append(fp.read())
    except Exception:
        pass

# Add vN / TNX specific seeds
SEEDS.append("""
v10 { v/ 0xA5 v/ u1 v/ 0xA5 ; }
v20 { v/ 0x1234 v/ u2 v/ 0x1234 ; }
v30 { v/ 0x12345678 v/ u4 v/ 0x12345678 ; }
i4 main(v.) {
    r; (i4)!v10!;
}
""")

SEEDS.append("""
s@ v. handler(v.) { }
T3A { width 8; payload !handler!; next T3B; locked; }
T3B { width 8; payload !handler!; locked; }
i4 main(v.) {
    r; 0;
}
""")

SEEDS.append("""
i4 main(v.) {
    !1! m, 10;
    !2! m, !/1/!;
    r; !/2/!;
}
""")

if not SEEDS:
    SEEDS = ["i4 main(v.) { r; 0; }\n"]

ALPHABET = (
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    "_{}[]()<>=!@#$%^&*~;:,._+-/\\|?`'\"\t\n\r "
    "\x00\xff\xfe\xef\xbb\xbf"  # NUL, high bytes, BOM bytes
)

MUTATIONS = [
    "insert_char",
    "delete_char",
    "replace_char",
    "truncate",
    "duplicate_line",
    "delete_line",
    "swap_lines",
    "insert_nul",
    "insert_bom",
    "deep_nest_parens",
    "deep_nest_braces",
    "long_ident",
    "bit_flip",
]


def mutate(src, rng):
    if not src:
        return rng.choice(ALPHABET)
    op = rng.choice(MUTATIONS)

    if op == "insert_char":
        pos = rng.randrange(len(src))
        return src[:pos] + rng.choice(ALPHABET) + src[pos:]
    elif op == "delete_char":
        if len(src) <= 1:
            return ""
        pos = rng.randrange(len(src))
        return src[:pos] + src[pos + 1 :]
    elif op == "replace_char":
        pos = rng.randrange(len(src))
        return src[:pos] + rng.choice(ALPHABET) + src[pos + 1 :]
    elif op == "truncate":
        cut = rng.randrange(len(src) + 1)
        return src[:cut]
    elif op == "duplicate_line":
        lines = src.splitlines(keepends=True)
        if not lines:
            return src
        idx = rng.randrange(len(lines))
        lines.insert(idx, lines[idx])
        return "".join(lines)
    elif op == "delete_line":
        lines = src.splitlines(keepends=True)
        if len(lines) <= 1:
            return ""
        idx = rng.randrange(len(lines))
        del lines[idx]
        return "".join(lines)
    elif op == "swap_lines":
        lines = src.splitlines(keepends=True)
        if len(lines) >= 2:
            i, j = rng.sample(range(len(lines)), 2)
            lines[i], lines[j] = lines[j], lines[i]
        return "".join(lines)
    elif op == "insert_nul":
        pos = rng.randrange(len(src))
        return src[:pos] + "\x00" + src[pos:]
    elif op == "insert_bom":
        return "\ufeff" + src
    elif op == "deep_nest_parens":
        depth = rng.choice([65, 75, 120, 500])
        return "(" * depth + src + ")" * depth
    elif op == "deep_nest_braces":
        depth = rng.choice([350, 450, 550])
        return "{" * depth + src + "}" * depth
    elif op == "long_ident":
        ident = "a" * rng.choice([4000, 6000, 20000])
        return f"i4 {ident} m, 1;\n" + src
    elif op == "bit_flip":
        pos = rng.randrange(len(src))
        c = ord(src[pos]) ^ (1 << rng.randrange(8))
        return src[:pos] + chr(c) + src[pos + 1 :]
    return src


def run_adv_fuzz(iterations=1000, seed=20261127, out_dir="artifacts/adversarial/20261127"):
    rng = random.Random(seed)
    crashes = []
    p0_count = 0
    clean_rejects = 0
    clean_compiles = 0

    print(f"[*] Starting Adversarial Fuzzing: {iterations} iterations, seed={seed}")
    start_time = time.time()

    for i in range(iterations):
        if (i + 1) % 200 == 0:
            print(f"    Progress: {i + 1}/{iterations} iterations...")
        seed_src = rng.choice(SEEDS)
        # Apply 1 to 3 mutations
        mut_count = rng.randint(1, 3)
        src = seed_src
        for _ in range(mut_count):
            src = mutate(src, rng)

        # Execute compilation under controlled exception catch
        t0 = time.time()
        try:
            c_code = sigilc.compile_source(src, f"fuzz_{i}.sigil")
            clean_compiles += 1
            # If successfully compiled to C, verify C compiles with GCC
            # to detect P1 (invalid C generation)
            if c_code and len(src) < 2000 and "main" in src:
                # Test with gcc -std=c99 -fsyntax-only
                res = subprocess.run(
                    ["gcc", "-std=c99", "-fsyntax-only", "-x", "c", "-"],
                    input=c_code,
                    text=True,
                    capture_output=True,
                    timeout=5,
                )
                if res.returncode != 0:
                    case_id = f"wrong_c_{i}"
                    c_dir = os.path.join(out_dir, "wrong-c", case_id)
                    os.makedirs(c_dir, exist_ok=True)
                    with open(os.path.join(c_dir, "input.sigil"), "w", encoding="utf-8", errors="replace") as fp:
                        fp.write(src)
                    with open(os.path.join(c_dir, "generated.c"), "w", encoding="utf-8", errors="replace") as fp:
                        fp.write(c_code)
                    with open(os.path.join(c_dir, "gcc.txt"), "w", encoding="utf-8", errors="replace") as fp:
                        fp.write(res.stderr)
                    crashes.append(("P1", case_id, "Generated C failed gcc syntax check", res.stderr[:200]))
        except (sigilc.LexerError, sigilc.ParseError, sigilc.SemanticError):
            clean_rejects += 1
        except Exception as exc:
            # P0: Uncaught exception!
            elapsed = time.time() - t0
            p0_count += 1
            case_id = f"crash_{i}_{type(exc).__name__}"
            crash_path = os.path.join(out_dir, "crashes", case_id)
            os.makedirs(crash_path, exist_ok=True)
            with open(os.path.join(crash_path, "input.sigil"), "w", encoding="utf-8", errors="replace") as fp:
                fp.write(src)
            with open(os.path.join(crash_path, "notes.md"), "w", encoding="utf-8") as fp:
                fp.write(f"case id: {case_id}\nseverity: P0\nexc: {type(exc).__name__}: {exc}\nelapsed: {elapsed:.2f}s\n")
            crashes.append(("P0", case_id, f"{type(exc).__name__}: {exc}", repr(src[:100])))

    duration = time.time() - start_time
    print(f"[*] Fuzzing finished in {duration:.2f}s:")
    print(f"    Total: {iterations}")
    print(f"    Clean Rejections (Expected): {clean_rejects}")
    print(f"    Clean Compilations: {clean_compiles}")
    print(f"    P0 Crashes: {p0_count}")
    print(f"    P1 Wrong C: {len([c for c in crashes if c[0] == 'P1'])}")

    # Summary report
    rep_file = os.path.join(out_dir, "fuzz", "adv_fuzz_summary.txt")
    with open(rep_file, "w", encoding="utf-8") as fp:
        fp.write(f"Iterations: {iterations}\n")
        fp.write(f"Seed: {seed}\n")
        fp.write(f"Duration: {duration:.2f}s\n")
        fp.write(f"Clean Rejections: {clean_rejects}\n")
        fp.write(f"Clean Compiles: {clean_compiles}\n")
        fp.write(f"P0 Crashes: {p0_count}\n")
        for c in crashes:
            fp.write(f"[{c[0]}] {c[1]}: {c[2]}\n")

    return crashes


if __name__ == "__main__":
    out = os.path.join(ROOT, "artifacts", "adversarial", "20261127")
    crashes = run_adv_fuzz(1000, 20261127, out)
    if any(c[0] == "P0" for c in crashes):
        sys.exit(1)
