#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_imports.py — Verifica import del package mouldgraph/
============================================================
Usa solo stdlib. Non avvia GUI. Non modifica file.
Exit code 0 = OK, exit code 1 = errore.

Utilizzo:
  python verify_imports.py
"""

import sys
import os
import compileall
import py_compile
import importlib
import traceback

ROOT = os.path.dirname(os.path.abspath(__file__))
PKG_DIR = os.path.join(ROOT, "mouldgraph")

OK = "\u2705"
FAIL = "\u274c"
SKIP = "\u23ed️"

errors = []


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


# ------------------------------------------------------------------ #
# 1. Compilazione bytecode di tutti i .py in mouldgraph/             #
# ------------------------------------------------------------------ #
section("1. compileall — mouldgraph/")
success = compileall.compile_dir(PKG_DIR, quiet=2, force=True)
if success:
    print(f"{OK} compileall OK")
else:
    print(f"{FAIL} compileall FAILED")
    errors.append("compileall failed")

# ------------------------------------------------------------------ #
# 2. py_compile file per file                                         #
# ------------------------------------------------------------------ #
section("2. py_compile — file per file")
for fname in sorted(os.listdir(PKG_DIR)):
    if fname.endswith(".py"):
        fpath = os.path.join(PKG_DIR, fname)
        try:
            py_compile.compile(fpath, doraise=True)
            print(f"{OK} {fname}")
        except py_compile.PyCompileError as e:
            print(f"{FAIL} {fname}: {e}")
            errors.append(f"py_compile: {fname}")

# ------------------------------------------------------------------ #
# 3. Import moduli stdlib-only (constants, log_parsers, csv_parsers)  #
# ------------------------------------------------------------------ #
section("3. Import moduli stdlib-only")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

CORE_MODULES = ["constants", "log_parsers", "csv_parsers"]
for mod in CORE_MODULES:
    full = f"mouldgraph.{mod}"
    try:
        importlib.import_module(full)
        print(f"{OK} {full}")
    except Exception:
        print(f"{FAIL} {full}")
        traceback.print_exc()
        errors.append(f"import error: {full}")

# ------------------------------------------------------------------ #
# 4. Import moduli opzionali (widgets, pdf_reports)                   #
#    Solo se le dipendenze sono installate                            #
# ------------------------------------------------------------------ #
section("4. Import moduli opzionali (se dipendenze disponibili)")

OPTIONAL_DEPS = {
    "mouldgraph.widgets": ["customtkinter"],
    "mouldgraph.pdf_reports": ["matplotlib", "numpy"],
}

for mod, deps in OPTIONAL_DEPS.items():
    missing = []
    for dep in deps:
        try:
            importlib.import_module(dep)
        except ImportError:
            missing.append(dep)

    if missing:
        print(f"{SKIP} {mod} — dipendenze mancanti: {', '.join(missing)}")
    else:
        try:
            importlib.import_module(mod)
            print(f"{OK} {mod}")
        except Exception:
            print(f"{FAIL} {mod}")
            traceback.print_exc()
            errors.append(f"import error: {mod}")

# ------------------------------------------------------------------ #
# 5. Riepilogo                                                        #
# ------------------------------------------------------------------ #
section("Riepilogo")
if errors:
    print(f"{FAIL} {len(errors)} errore/i rilevato/i:")
    for e in errors:
        print(f"   - {e}")
    sys.exit(1)
else:
    print(f"{OK} Tutti i controlli superati. Package mouldgraph/ integro.")
    sys.exit(0)
