"""
VPTA-RL Compiler Front-End
==========================
Entry point.  Runs the full front-end pipeline:
  1. Lexical Analysis  (Lexer)
  2. Parsing           (Parser → AST)
  3. Error Reporting   (ErrorReporter)

Usage
-----
  python main.py <source_file.vpta>
  python main.py --demo          # run built-in demo
"""

import sys
import argparse
from pathlib import Path

from lexer         import Lexer, TT
from parser        import Parser
from error_handler import ErrorReporter


# ---------------------------------------------------------------------------
# Demo source (used when --demo flag is passed)
# ---------------------------------------------------------------------------
DEMO_SOURCE = """\
// ── Emergency vehicle override ────────────────────────────────────────────
PRIORITY VEHICLE_CLASS == "AMBULANCE" SET SIGNAL GREEN ;
PRIORITY VEHICLE_CLASS == "FIRE_TRUCK" SET SIGNAL GREEN ;
PRIORITY VEHICLE_CLASS == "POLICE" SET SIGNAL GREEN ;

// ── Dynamic toll adjustment based on congestion ────────────────────────────
IF congestion_level > 80 AND vehicle_class == "HEAVY"
    THEN toll_fee = toll_fee * 1.5 ;

// ── Night-time discount ────────────────────────────────────────────────────
IF time_of_day >= 22 OR time_of_day <= 6
    THEN toll_fee = toll_fee * 0.75 ;

// ── Deny overloaded vehicles ───────────────────────────────────────────────
DENY VEHICLE_CLASS == "OVERLOADED" ENTRY lane_id ;

// ── Allow electric vehicles with reduced toll ──────────────────────────────
IF vehicle_class == "ELECTRIC" THEN toll_fee = toll_fee * 0.5 ;

// ── Complex condition with ELSE branch ────────────────────────────────────
IF congestion_level > 90 AND vehicle_class == "LIGHT"
    THEN toll_fee = toll_fee * 1.2
    ELSE toll_fee = toll_fee * 1.0 ;

// ── Intentional error for recovery demo ───────────────────────────────────
IF speed > 120 AND @ illegal_char THEN SET SIGNAL RED ;
"""


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
def compile_source(source: str, filename: str = "<input>", verbose: bool = True):
    """
    Run lexer → parser on *source*.
    Returns (ast, reporter).
    """
    reporter = ErrorReporter()

    # ── Stage 1: Lexical Analysis ─────────────────────────────────────
    if verbose:
        print(f"\n{'─' * 60}")
        print(f"  VPTA-RL Compiler Front-End  |  {filename}")
        print(f"{'─' * 60}")
        print("\n[Stage 1] Lexical Analysis …")

    lexer = Lexer(source)
    tokens, lex_errors = lexer.tokenize()

    # Forward lexer errors to the shared reporter
    for err in lex_errors:
        reporter.lexical(err.message, err.line, err.column)

    if verbose:
        _print_tokens(tokens)

    # ── Stage 2: Parsing ──────────────────────────────────────────────
    if verbose:
        print("\n[Stage 2] Parsing …")

    # Strip the EOF sentinel before passing to parser
    parser = Parser(tokens, reporter)
    ast = parser.parse()

    if verbose:
        print("\n[Stage 2] AST:")
        print(repr(ast))

    # ── Stage 3: Error Summary ────────────────────────────────────────
    if verbose:
        print(f"\n{'─' * 60}")
        if reporter.has_errors:
            print("\n[Error Report]")
            reporter.print_all()
        else:
            print("\n✓ No errors detected.")
        print(f"\n{reporter.summary()}")
        print(f"{'─' * 60}\n")

    return ast, reporter


# ---------------------------------------------------------------------------
# Token pretty-printer
# ---------------------------------------------------------------------------
def _print_tokens(tokens):
    print()
    header = f"  {'TOKEN TYPE':<22} {'LEXEME':<28} {'LINE':>4}  {'COL':>4}"
    print(header)
    print("  " + "─" * (len(header) - 2))
    for tok in tokens:
        if tok.type == TT.EOF:
            break
        print(f"  {tok.type:<22} {tok.value!r:<28} {tok.line:>4}  {tok.column:>4}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="VPTA-RL Compiler Front-End",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("source_file", nargs="?", help=".vpta source file to compile")
    ap.add_argument("--demo",    action="store_true", help="Run built-in demo program")
    ap.add_argument("--quiet",   action="store_true", help="Suppress token table output")
    args = ap.parse_args()

    if args.demo:
        compile_source(DEMO_SOURCE, filename="<demo>", verbose=not args.quiet)
        return

    if not args.source_file:
        ap.print_help()
        sys.exit(1)

    path = Path(args.source_file)
    if not path.exists():
        print(f"Error: file not found: {path}")
        sys.exit(1)

    source = path.read_text(encoding="utf-8")
    _, reporter = compile_source(source, filename=str(path), verbose=not args.quiet)

    sys.exit(1 if reporter.has_errors else 0)


if __name__ == "__main__":
    main()
