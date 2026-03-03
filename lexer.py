"""
VPTA-RL Lexical Analyzer
========================
Tokenizes Vehicle-Priority and Toll Adjustment Rule Language source code.

Implements:
  - Maximal Munch (longest match via combined regex)
  - Rule priority (order of TOKEN_PATTERNS)
  - Keyword vs Identifier resolution via symbol table
  - Panic-mode error recovery for illegal characters
  - End-of-line recovery for unterminated string literals
"""

import re
from dataclasses import dataclass
from typing import List, Tuple, Optional


# ---------------------------------------------------------------------------
# Token types
# ---------------------------------------------------------------------------
class TT:
    """Token type constants."""
    # Literals
    NUM_INT        = "NUM_INT"
    NUM_FLOAT      = "NUM_FLOAT"
    STRING         = "STRING"
    BOOL           = "BOOL"
    # Words
    KEYWORD        = "KEYWORD"
    IDENTIFIER     = "IDENTIFIER"
    # Operators
    RELOP          = "RELOP"
    ARITH          = "ARITH"
    ASSIGN         = "ASSIGN"
    # Structure
    DELIM          = "DELIM"
    # Errors
    LEXICAL_ERROR  = "LEXICAL_ERROR"
    UNTERM_STRING  = "UNTERM_STRING"
    # Sentinel
    EOF            = "EOF"


# ---------------------------------------------------------------------------
# Keywords
# ---------------------------------------------------------------------------
KEYWORDS = {
    "PRIORITY", "IF", "THEN", "ELSE",
    "SET", "SIGNAL", "DENY", "ALLOW", "ENTRY",
    "AND", "OR", "NOT",
    "VEHICLE_CLASS", "TRUE", "FALSE",
    "GREEN", "RED", "YELLOW",
}

BOOL_LITERALS = {"TRUE", "FALSE"}

# ---------------------------------------------------------------------------
# Token dataclass
# ---------------------------------------------------------------------------
@dataclass
class Token:
    type:    str
    value:   str
    line:    int
    column:  int

    def __repr__(self):
        return f"Token({self.type:<20} | {self.value!r:<25} | line {self.line}, col {self.column})"


# ---------------------------------------------------------------------------
# Lexer error
# ---------------------------------------------------------------------------
@dataclass
class LexError:
    message: str
    line:    int
    column:  int

    def __str__(self):
        return f"[LEXICAL ERROR] Line {self.line}, Col {self.column}: {self.message}"


# ---------------------------------------------------------------------------
# Token pattern table  (order = priority)
# ---------------------------------------------------------------------------
_RAW_PATTERNS: List[Tuple[str, str]] = [
    ("COMMENT",       r"//[^\n]*"),                 # single-line comment
    ("WHITESPACE",    r"[ \t\r\n]+"),               # whitespace
    ("UNTERM_STRING", r'"[^"\n]*$'),                # unterminated string (EOL)
    ("STRING",        r'"[^"\n]*"'),                # valid string literal
    ("NUM_FLOAT",     r"\d+\.\d+"),                 # float  (before INT)
    ("NUM_INT",       r"\d+"),                      # integer
    ("RELOP",         r"==|!=|<=|>=|<|>"),          # relational (longest first)
    ("ASSIGN",        r"="),                        # assignment
    ("ARITH",         r"[+\-*/]"),                  # arithmetic
    ("DELIM",         r"[;()]"),                    # delimiters
    ("WORD",          r"[a-zA-Z_][a-zA-Z0-9_]*"),  # keyword or identifier
    ("UNKNOWN",       r"."),                        # catch-all → error
]

_MASTER_RE = re.compile(
    "|".join(f"(?P<{name}>{pat})" for name, pat in _RAW_PATTERNS),
    re.MULTILINE,
)


# ---------------------------------------------------------------------------
# Lexer
# ---------------------------------------------------------------------------
class Lexer:
    """
    Tokenise a VPTA-RL source string.

    Usage
    -----
    lex = Lexer(source)
    tokens, errors = lex.tokenize()
    """

    def __init__(self, source: str):
        self._source     = source
        self._tokens:    List[Token]    = []
        self._errors:    List[LexError] = []
        self._line:      int = 1
        self._line_start: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def tokenize(self) -> Tuple[List[Token], List[LexError]]:
        """
        Scan the full source and return (token_list, error_list).
        Error recovery: illegal chars and unterminated strings are logged
        and scanning continues (panic mode).
        """
        for mo in _MASTER_RE.finditer(self._source):
            kind  = mo.lastgroup
            value = mo.group()
            col   = mo.start() - self._line_start + 1

            # ── housekeeping ──────────────────────────────────────────
            if kind == "WHITESPACE":
                newlines = value.count("\n")
                if newlines:
                    self._line += newlines
                    self._line_start = mo.start() + value.rfind("\n") + 1
                continue

            if kind == "COMMENT":
                continue   # silently discard

            # ── error recovery ────────────────────────────────────────
            if kind == "UNTERM_STRING":
                self._errors.append(LexError(
                    f"Unterminated string literal: {value!r} "
                    f"(missing closing '\"')",
                    self._line, col,
                ))
                # Recovery: emit a STRING token anyway so the parser can
                # continue (end-of-line acts as implicit closing quote).
                self._tokens.append(Token(TT.UNTERM_STRING, value,
                                          self._line, col))
                continue

            if kind == "UNKNOWN":
                self._errors.append(LexError(
                    f"Illegal character {value!r}",
                    self._line, col,
                ))
                # Panic mode: skip the character and resume
                continue

            # ── keyword / identifier resolution ───────────────────────
            if kind == "WORD":
                if value in BOOL_LITERALS:
                    kind = TT.BOOL
                elif value in KEYWORDS:
                    kind = TT.KEYWORD
                else:
                    kind = TT.IDENTIFIER

            # ── map internal names to public token types ───────────────
            type_map = {
                "STRING":    TT.STRING,
                "NUM_FLOAT": TT.NUM_FLOAT,
                "NUM_INT":   TT.NUM_INT,
                "RELOP":     TT.RELOP,
                "ASSIGN":    TT.ASSIGN,
                "ARITH":     TT.ARITH,
                "DELIM":     TT.DELIM,
            }
            tok_type = type_map.get(kind, kind)
            self._tokens.append(Token(tok_type, value, self._line, col))

        # Sentinel
        self._tokens.append(Token(TT.EOF, "", self._line, 0))
        return self._tokens, self._errors

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------
    def print_tokens(self):
        for tok in self._tokens:
            print(repr(tok))

    def print_errors(self):
        for err in self._errors:
            print(err)
