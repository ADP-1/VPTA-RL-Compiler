"""
VPTA-RL Unit Tests
==================
Run with:  python -m pytest tests/ -v
or:        python tests/test_lexer.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from lexer         import Lexer, TT, Token
from parser        import Parser
from error_handler import ErrorReporter
from ast_nodes     import (
    Program, PriorityRule, IfRule, DenyAllowRule,
    Comparison, BinaryCondition, Identifier, NumLiteral, StringLiteral,
    AssignAction, SetSignalAction,
)


# ===========================================================================
# Lexer tests
# ===========================================================================
class TestLexer(unittest.TestCase):

    def _lex(self, src):
        toks, errs = Lexer(src).tokenize()
        return toks, errs

    # ── Keywords ────────────────────────────────────────────────────────
    def test_keyword_recognition(self):
        toks, errs = self._lex("IF THEN ELSE PRIORITY SET SIGNAL DENY ALLOW ENTRY AND OR NOT")
        types = [t.type for t in toks if t.type != TT.EOF]
        self.assertTrue(all(tt == TT.KEYWORD for tt in types))
        self.assertEqual(len(errs), 0)

    def test_vehicle_class_keyword(self):
        toks, _ = self._lex("VEHICLE_CLASS")
        self.assertEqual(toks[0].type, TT.KEYWORD)
        self.assertEqual(toks[0].value, "VEHICLE_CLASS")

    def test_signal_state_keywords(self):
        for state in ("GREEN", "RED", "YELLOW"):
            toks, _ = self._lex(state)
            self.assertEqual(toks[0].type, TT.KEYWORD)

    # ── Identifiers ─────────────────────────────────────────────────────
    def test_identifier(self):
        toks, _ = self._lex("congestion_level")
        self.assertEqual(toks[0].type, TT.IDENTIFIER)
        self.assertEqual(toks[0].value, "congestion_level")

    def test_identifier_not_keyword(self):
        # "toll_fee" is not a keyword
        toks, _ = self._lex("toll_fee")
        self.assertEqual(toks[0].type, TT.IDENTIFIER)

    # ── Literals ────────────────────────────────────────────────────────
    def test_integer_literal(self):
        toks, _ = self._lex("80")
        self.assertEqual(toks[0].type, TT.NUM_INT)
        self.assertEqual(toks[0].value, "80")

    def test_float_literal(self):
        toks, _ = self._lex("1.5")
        self.assertEqual(toks[0].type, TT.NUM_FLOAT)
        self.assertEqual(toks[0].value, "1.5")

    def test_string_literal(self):
        toks, _ = self._lex('"AMBULANCE"')
        self.assertEqual(toks[0].type, TT.STRING)
        self.assertEqual(toks[0].value, '"AMBULANCE"')

    def test_bool_literals(self):
        toks, _ = self._lex("TRUE FALSE")
        self.assertEqual(toks[0].type, TT.BOOL)
        self.assertEqual(toks[1].type, TT.BOOL)

    # ── Operators & delimiters ───────────────────────────────────────────
    def test_relops(self):
        for op in ("==", "!=", "<=", ">=", "<", ">"):
            toks, _ = self._lex(op)
            self.assertEqual(toks[0].type, TT.RELOP, msg=f"Failed for {op!r}")

    def test_longest_match_relop(self):
        # ">=" must be one token, not ">" + "="
        toks, _ = self._lex(">=")
        self.assertEqual(len([t for t in toks if t.type != TT.EOF]), 1)
        self.assertEqual(toks[0].value, ">=")

    def test_assign_vs_equality(self):
        toks, _ = self._lex("= ==")
        self.assertEqual(toks[0].type, TT.ASSIGN)
        self.assertEqual(toks[1].type, TT.RELOP)

    def test_arith_operators(self):
        for op in ("+", "-", "*", "/"):
            toks, _ = self._lex(op)
            self.assertEqual(toks[0].type, TT.ARITH)

    def test_delimiters(self):
        for ch in (";", "(", ")"):
            toks, _ = self._lex(ch)
            self.assertEqual(toks[0].type, TT.DELIM)

    # ── Comments & whitespace ────────────────────────────────────────────
    def test_comment_ignored(self):
        toks, _ = self._lex("// this is a comment\nIF")
        types = [t.type for t in toks if t.type != TT.EOF]
        self.assertEqual(types, [TT.KEYWORD])   # only IF

    def test_whitespace_ignored(self):
        toks, _ = self._lex("   \t\n  IF   ")
        types = [t.type for t in toks if t.type != TT.EOF]
        self.assertEqual(types, [TT.KEYWORD])

    # ── Line & column tracking ───────────────────────────────────────────
    def test_line_tracking(self):
        toks, _ = self._lex("IF\ncongestion_level")
        self.assertEqual(toks[0].line, 1)
        self.assertEqual(toks[1].line, 2)

    def test_column_tracking(self):
        toks, _ = self._lex("IF toll_fee")
        self.assertEqual(toks[0].column, 1)
        self.assertEqual(toks[1].column, 4)

    # ── Error recovery ───────────────────────────────────────────────────
    def test_illegal_char_error(self):
        toks, errs = self._lex("IF @ speed")
        self.assertEqual(len(errs), 1)
        self.assertIn("Illegal character", errs[0].message)
        # Token stream should still contain IF and speed
        values = [t.value for t in toks if t.type != TT.EOF]
        self.assertIn("IF", values)
        self.assertIn("speed", values)

    def test_unterminated_string(self):
        toks, errs = self._lex('IF vehicle_class == "HEAVY')
        self.assertEqual(len(errs), 1)
        self.assertIn("Unterminated", errs[0].message)

    def test_multiple_errors_reported(self):
        _, errs = self._lex("@ # $")
        self.assertEqual(len(errs), 3)

    def test_no_errors_on_valid_source(self):
        _, errs = self._lex('PRIORITY VEHICLE_CLASS == "AMBULANCE" SET SIGNAL GREEN ;')
        self.assertEqual(len(errs), 0)


# ===========================================================================
# Parser tests
# ===========================================================================
class TestParser(unittest.TestCase):

    def _parse(self, src):
        toks, _ = Lexer(src).tokenize()
        reporter = ErrorReporter()
        ast = Parser(toks, reporter).parse()
        return ast, reporter

    # ── Priority rule ────────────────────────────────────────────────────
    def test_priority_rule(self):
        ast, rep = self._parse('PRIORITY VEHICLE_CLASS == "AMBULANCE" SET SIGNAL GREEN ;')
        self.assertFalse(rep.has_errors)
        self.assertEqual(len(ast.rules), 1)
        self.assertIsInstance(ast.rules[0], PriorityRule)
        self.assertEqual(ast.rules[0].signal_state, "GREEN")

    # ── IF rule without ELSE ─────────────────────────────────────────────
    def test_if_rule_no_else(self):
        ast, rep = self._parse(
            'IF congestion_level > 80 THEN toll_fee = toll_fee * 1.5 ;'
        )
        self.assertFalse(rep.has_errors)
        rule = ast.rules[0]
        self.assertIsInstance(rule, IfRule)
        self.assertIsNone(rule.else_action)
        self.assertIsInstance(rule.then_action, AssignAction)

    # ── IF rule with ELSE ────────────────────────────────────────────────
    def test_if_rule_with_else(self):
        ast, rep = self._parse(
            'IF speed > 100 THEN SET SIGNAL RED ELSE SET SIGNAL GREEN ;'
        )
        self.assertFalse(rep.has_errors)
        rule = ast.rules[0]
        self.assertIsInstance(rule, IfRule)
        self.assertIsNotNone(rule.else_action)

    # ── DENY rule ────────────────────────────────────────────────────────
    def test_deny_rule(self):
        ast, rep = self._parse('DENY VEHICLE_CLASS == "OVERLOADED" ENTRY lane_id ;')
        self.assertFalse(rep.has_errors)
        rule = ast.rules[0]
        self.assertIsInstance(rule, DenyAllowRule)
        self.assertEqual(rule.verb, "DENY")
        self.assertEqual(rule.lane_id, "lane_id")

    # ── ALLOW rule ───────────────────────────────────────────────────────
    def test_allow_rule(self):
        ast, rep = self._parse('ALLOW VEHICLE_CLASS == "ELECTRIC" ENTRY express ;')
        self.assertFalse(rep.has_errors)
        rule = ast.rules[0]
        self.assertIsInstance(rule, DenyAllowRule)
        self.assertEqual(rule.verb, "ALLOW")

    # ── AND / OR conditions ──────────────────────────────────────────────
    def test_and_condition(self):
        ast, rep = self._parse(
            'IF congestion_level > 80 AND vehicle_class == "HEAVY" THEN SET SIGNAL RED ;'
        )
        self.assertFalse(rep.has_errors)
        cond = ast.rules[0].condition
        self.assertIsInstance(cond, BinaryCondition)
        self.assertEqual(cond.op, "AND")

    def test_or_condition(self):
        ast, rep = self._parse(
            'IF time_of_day >= 22 OR time_of_day <= 6 THEN toll_fee = toll_fee * 0.75 ;'
        )
        self.assertFalse(rep.has_errors)
        cond = ast.rules[0].condition
        self.assertIsInstance(cond, BinaryCondition)
        self.assertEqual(cond.op, "OR")

    # ── Multiple rules ───────────────────────────────────────────────────
    def test_multiple_rules(self):
        src = (
            'PRIORITY VEHICLE_CLASS == "AMBULANCE" SET SIGNAL GREEN ;\n'
            'IF speed > 120 THEN SET SIGNAL RED ;\n'
        )
        ast, rep = self._parse(src)
        self.assertFalse(rep.has_errors)
        self.assertEqual(len(ast.rules), 2)

    # ── Syntax error recovery ────────────────────────────────────────────
    def test_missing_then_reports_error(self):
        _, rep = self._parse('IF speed > 100 SET SIGNAL RED ;')
        self.assertTrue(rep.has_errors)

    def test_recovery_continues_after_error(self):
        # First rule is bad, second is valid — second should still be in AST
        src = (
            'IF speed > 100 SET SIGNAL RED ;\n'
            'PRIORITY VEHICLE_CLASS == "POLICE" SET SIGNAL GREEN ;\n'
        )
        ast, rep = self._parse(src)
        # At least the valid rule should be parsed
        valid_rules = [r for r in ast.rules if isinstance(r, PriorityRule)]
        self.assertGreater(len(valid_rules), 0)


# ===========================================================================
# Integration test
# ===========================================================================
class TestIntegration(unittest.TestCase):

    def test_full_demo_source(self):
        from main import DEMO_SOURCE
        toks, lex_errs = Lexer(DEMO_SOURCE).tokenize()
        reporter = ErrorReporter()
        for e in lex_errs:
            reporter.lexical(e.message, e.line, e.column)
        ast = Parser(toks, reporter).parse()
        # Demo contains one intentional '@' error — should be exactly 1 lex error
        lex_count = sum(1 for e in reporter.errors if e.severity == "LEXICAL")
        self.assertEqual(lex_count, 1)
        # But valid rules should still be in the AST
        self.assertGreater(len(ast.rules), 0)


# ===========================================================================
if __name__ == "__main__":
    unittest.main(verbosity=2)
