"""
VPTA-RL Recursive-Descent Parser
=================================
Implements the CFG defined in the assignment report and produces an AST.

Grammar (informal BNF):
  program         → rule_list EOF
  rule_list       → (rule ';')*
  rule            → priority_rule | if_rule | deny_allow_rule
  priority_rule   → PRIORITY condition SET SIGNAL signal_state
  if_rule         → IF condition THEN action [ELSE action]
  deny_allow_rule → (DENY | ALLOW) condition ENTRY IDENTIFIER
  condition       → or_cond
  or_cond         → and_cond  (OR  and_cond)*
  and_cond        → not_cond  (AND not_cond)*
  not_cond        → NOT not_cond | comparison | '(' condition ')'
  comparison      → expr relop expr
  action          → IDENTIFIER ASSIGN expr | SET SIGNAL signal_state
  expr            → term (('+' | '-') term)*
  term            → factor (('*' | '/') factor)*
  factor          → IDENTIFIER | NUM_INT | NUM_FLOAT | STRING
                  | BOOL | '(' expr ')'
  signal_state    → GREEN | RED | YELLOW
  relop           → == | != | < | > | <= | >=

Error recovery:
  - `expect()` calls `synchronize()` on mismatch (insertion strategy).
  - `synchronize()` advances until a SYNC_TOKEN is found (panic mode).
"""

from typing import List, Optional

from lexer import Token, TT
from ast_nodes import (
    Program, PriorityRule, IfRule, DenyAllowRule,
    AssignAction, SetSignalAction,
    BinaryCondition, NotCondition, Comparison,
    BinaryExpr, Identifier, NumLiteral, StringLiteral, BoolLiteral,
)
from error_handler import ErrorReporter, SYNC_TOKENS, RULE_START_KEYWORDS


_SIGNAL_STATES = {"GREEN", "RED", "YELLOW"}
_RELOPS        = {"==", "!=", "<", ">", "<=", ">="}


class ParseError(Exception):
    """Internal sentinel; always caught within the parser."""


class Parser:
    """
    Recursive-descent parser for VPTA-RL.

    Usage
    -----
    parser = Parser(tokens, reporter)
    ast    = parser.parse()
    """

    def __init__(self, tokens: List[Token], reporter: ErrorReporter):
        self._tokens   = tokens
        self._pos      = 0
        self._reporter = reporter

    # ===================================================================
    # Public entry point
    # ===================================================================
    def parse(self) -> Program:
        program = Program(line=self._peek().line)
        while not self._at_end():
            try:
                rule = self._rule()
                if rule is not None:
                    program.rules.append(rule)
                self._expect_delim(";")
            except ParseError:
                self._synchronize()   # panic-mode recovery
        return program

    # ===================================================================
    # Rules
    # ===================================================================
    def _rule(self):
        tok = self._peek()

        if self._is_keyword("PRIORITY"):
            return self._priority_rule()

        if self._is_keyword("IF"):
            return self._if_rule()

        if self._is_keyword("DENY") or self._is_keyword("ALLOW"):
            return self._deny_allow_rule()

        # Unknown rule start — emit error and let synchronize handle it
        self._error(
            f"Expected a rule starting with PRIORITY, IF, DENY, or ALLOW; "
            f"got {tok.value!r}",
            tok,
        )

    # -------------------------------------------------------------------
    def _priority_rule(self) -> PriorityRule:
        line = self._peek().line
        self._consume()                            # eat PRIORITY
        cond = self._condition()
        self._expect_keyword("SET")
        self._expect_keyword("SIGNAL")
        state = self._signal_state()
        return PriorityRule(line=line, condition=cond, signal_state=state)

    # -------------------------------------------------------------------
    def _if_rule(self) -> IfRule:
        line = self._peek().line
        self._consume()                            # eat IF
        cond = self._condition()
        self._expect_keyword("THEN")
        then_act = self._action()
        else_act = None
        if self._is_keyword("ELSE"):
            self._consume()                        # eat ELSE
            else_act = self._action()
        return IfRule(line=line, condition=cond,
                      then_action=then_act, else_action=else_act)

    # -------------------------------------------------------------------
    def _deny_allow_rule(self) -> DenyAllowRule:
        line = self._peek().line
        verb = self._peek().value                  # "DENY" or "ALLOW"
        self._consume()
        cond = self._condition()
        self._expect_keyword("ENTRY")
        lane_tok = self._expect_type(TT.IDENTIFIER, "lane identifier")
        return DenyAllowRule(line=line, verb=verb,
                             condition=cond, lane_id=lane_tok.value)

    # ===================================================================
    # Actions
    # ===================================================================
    def _action(self):
        if self._is_keyword("SET"):
            line = self._peek().line
            self._consume()                        # eat SET
            self._expect_keyword("SIGNAL")
            state = self._signal_state()
            return SetSignalAction(line=line, state=state)

        if self._check_type(TT.IDENTIFIER):
            line = self._peek().line
            name = self._consume().value
            self._expect_assign()
            expr = self._expr()
            return AssignAction(line=line, target=name, value=expr)

        tok = self._peek()
        self._error(f"Expected an action (SET SIGNAL or assignment); got {tok.value!r}", tok)

    # ===================================================================
    # Conditions  (operator precedence: OR < AND < NOT < comparison)
    # ===================================================================
    def _condition(self):
        return self._or_cond()

    def _or_cond(self):
        node = self._and_cond()
        while self._is_keyword("OR"):
            line = self._peek().line
            self._consume()
            right = self._and_cond()
            node  = BinaryCondition(line=line, op="OR", left=node, right=right)
        return node

    def _and_cond(self):
        node = self._not_cond()
        while self._is_keyword("AND"):
            line = self._peek().line
            self._consume()
            right = self._not_cond()
            node  = BinaryCondition(line=line, op="AND", left=node, right=right)
        return node

    def _not_cond(self):
        if self._is_keyword("NOT"):
            line = self._peek().line
            self._consume()
            operand = self._not_cond()
            return NotCondition(line=line, operand=operand)

        if self._check_value("("):
            self._consume()
            node = self._condition()
            self._expect_delim(")")
            return node

        return self._comparison()

    def _comparison(self):
        line  = self._peek().line
        left  = self._expr()
        relop = self._expect_relop()
        right = self._expr()
        return Comparison(line=line, op=relop, left=left, right=right)

    # ===================================================================
    # Expressions  (left-associative, standard precedence)
    # ===================================================================
    def _expr(self):
        return self._additive()

    def _additive(self):
        node = self._multiplicative()
        while self._check_type(TT.ARITH) and self._peek().value in ("+", "-"):
            line = self._peek().line
            op   = self._consume().value
            right = self._multiplicative()
            node  = BinaryExpr(line=line, op=op, left=node, right=right)
        return node

    def _multiplicative(self):
        node = self._factor()
        while self._check_type(TT.ARITH) and self._peek().value in ("*", "/"):
            line = self._peek().line
            op   = self._consume().value
            right = self._factor()
            node  = BinaryExpr(line=line, op=op, left=node, right=right)
        return node

    def _factor(self):
        tok = self._peek()

        if tok.type == TT.IDENTIFIER or tok.type == TT.KEYWORD:
            self._consume()
            return Identifier(line=tok.line, name=tok.value)

        if tok.type == TT.NUM_INT:
            self._consume()
            return NumLiteral(line=tok.line, value=int(tok.value), raw=tok.value)

        if tok.type == TT.NUM_FLOAT:
            self._consume()
            return NumLiteral(line=tok.line, value=float(tok.value), raw=tok.value)

        if tok.type == TT.STRING:
            self._consume()
            inner = tok.value[1:-1]                # strip surrounding quotes
            return StringLiteral(line=tok.line, value=inner)

        if tok.type == TT.BOOL:
            self._consume()
            return BoolLiteral(line=tok.line, value=(tok.value == "TRUE"))

        if tok.value == "(":
            self._consume()
            node = self._expr()
            self._expect_delim(")")
            return node

        self._error(
            f"Expected an expression (identifier, number, string, or '('); "
            f"got {tok.value!r}",
            tok,
        )

    # ===================================================================
    # Small helpers
    # ===================================================================
    def _signal_state(self) -> str:
        tok = self._peek()
        if tok.value in _SIGNAL_STATES:
            self._consume()
            return tok.value
        self._error(
            f"Expected a signal state (GREEN, RED, YELLOW); got {tok.value!r}",
            tok,
        )

    def _expect_keyword(self, kw: str) -> Token:
        tok = self._peek()
        if tok.type == TT.KEYWORD and tok.value == kw:
            return self._consume()
        self._error(f"Expected keyword '{kw}'; got {tok.value!r}", tok)

    def _expect_delim(self, ch: str) -> Token:
        tok = self._peek()
        if tok.type == TT.DELIM and tok.value == ch:
            return self._consume()
        # Insertion recovery: log the error but do NOT advance
        self._reporter.syntax(
            f"Expected '{ch}'; got {tok.value!r} — "
            f"'{ch}' has been implicitly inserted",
            tok.line, tok.column,
        )
        return tok   # return current token as if we consumed it

    def _expect_assign(self) -> Token:
        tok = self._peek()
        if tok.type == TT.ASSIGN:
            return self._consume()
        self._error(f"Expected '='; got {tok.value!r}", tok)

    def _expect_relop(self) -> str:
        tok = self._peek()
        if tok.type == TT.RELOP and tok.value in _RELOPS:
            self._consume()
            return tok.value
        self._error(f"Expected a relational operator; got {tok.value!r}", tok)

    def _expect_type(self, ttype: str, description: str) -> Token:
        tok = self._peek()
        if tok.type == ttype:
            return self._consume()
        self._error(f"Expected {description}; got {tok.value!r}", tok)

    # ===================================================================
    # Token stream primitives
    # ===================================================================
    def _peek(self) -> Token:
        return self._tokens[self._pos]

    def _consume(self) -> Token:
        tok = self._tokens[self._pos]
        if not self._at_end():
            self._pos += 1
        return tok

    def _at_end(self) -> bool:
        return self._tokens[self._pos].type == TT.EOF

    def _check_type(self, ttype: str) -> bool:
        return self._peek().type == ttype

    def _check_value(self, val: str) -> bool:
        return self._peek().value == val

    def _is_keyword(self, kw: str) -> bool:
        tok = self._peek()
        return tok.type == TT.KEYWORD and tok.value == kw

    # ===================================================================
    # Error / recovery
    # ===================================================================
    def _error(self, message: str, tok: Token):
        self._reporter.syntax(message, tok.line, tok.column)
        raise ParseError(message)

    def _synchronize(self):
        """
        Panic-mode recovery: skip tokens until we find a synchronisation
        point — either a statement terminator ';' or the start of a new rule.
        """
        while not self._at_end():
            tok = self._peek()
            if tok.type == TT.DELIM and tok.value == ";":
                self._consume()   # consume the ';' and resume
                return
            if tok.type == TT.KEYWORD and tok.value in RULE_START_KEYWORDS:
                return            # do NOT consume; let the next iteration parse it
            self._consume()
