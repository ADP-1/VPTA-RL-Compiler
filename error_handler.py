"""
VPTA-RL Error Handler
=====================
Centralised error reporting and recovery helpers used by both the lexer
and the parser.

Error Recovery Strategies implemented here:
  1. Panic Mode        – skip tokens until a synchronisation point.
  2. Synchronisation   – resume at a known-safe token (;, IF, PRIORITY…).
  3. Error Productions – parser calls `synchronize()` on rule boundaries.
  4. Error Insertion   – `expect()` helper virtually inserts a missing token.
"""

from dataclasses import dataclass, field
from typing import List, Set, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from lexer import Token


# ---------------------------------------------------------------------------
# Error severity
# ---------------------------------------------------------------------------
class Severity:
    LEXICAL  = "LEXICAL"
    SYNTAX   = "SYNTAX"
    WARNING  = "WARNING"


# ---------------------------------------------------------------------------
# Compiler error record
# ---------------------------------------------------------------------------
@dataclass
class CompilerError:
    severity: str
    message:  str
    line:     int
    column:   int

    def __str__(self):
        return (
            f"[{self.severity} ERROR] "
            f"Line {self.line}, Col {self.column}: {self.message}"
        )


# ---------------------------------------------------------------------------
# Error reporter
# ---------------------------------------------------------------------------
class ErrorReporter:
    """
    Accumulates all errors produced during compilation.
    Passed by reference to both Lexer and Parser.
    """

    def __init__(self):
        self._errors: List[CompilerError] = []

    # ------------------------------------------------------------------
    def lexical(self, message: str, line: int, col: int):
        self._errors.append(CompilerError(Severity.LEXICAL, message, line, col))

    def syntax(self, message: str, line: int, col: int):
        self._errors.append(CompilerError(Severity.SYNTAX, message, line, col))

    def warning(self, message: str, line: int, col: int):
        self._errors.append(CompilerError(Severity.WARNING, message, line, col))

    # ------------------------------------------------------------------
    @property
    def errors(self) -> List[CompilerError]:
        return list(self._errors)

    @property
    def has_errors(self) -> bool:
        return any(
            e.severity in (Severity.LEXICAL, Severity.SYNTAX)
            for e in self._errors
        )

    @property
    def count(self) -> int:
        return len(self._errors)

    # ------------------------------------------------------------------
    def print_all(self):
        if not self._errors:
            print("No errors detected.")
            return
        for e in self._errors:
            print(e)
        print(f"\n{self.count} error(s) found.")

    def summary(self) -> str:
        lex  = sum(1 for e in self._errors if e.severity == Severity.LEXICAL)
        syn  = sum(1 for e in self._errors if e.severity == Severity.SYNTAX)
        warn = sum(1 for e in self._errors if e.severity == Severity.WARNING)
        return (
            f"Compilation finished — "
            f"{lex} lexical error(s), "
            f"{syn} syntax error(s), "
            f"{warn} warning(s)."
        )


# ---------------------------------------------------------------------------
# Synchronisation token sets (used by the parser)
# ---------------------------------------------------------------------------
# A rule always starts with one of these keywords
RULE_START_KEYWORDS: Set[str] = {
    "IF", "PRIORITY", "DENY", "ALLOW",
}

# Panic-mode sync: skip until we see one of these
SYNC_TOKENS: Set[str] = {
    ";",           # statement terminator
    *RULE_START_KEYWORDS,
}
