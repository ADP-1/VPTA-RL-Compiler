"""
VPTA-RL Abstract Syntax Tree Nodes
===================================
All AST node classes produced by the parser.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------
@dataclass
class ASTNode:
    """Base class for all AST nodes."""
    line: int = 0

    def __repr__(self):
        return self._tree_str(0)

    def _tree_str(self, depth: int) -> str:
        indent = "  " * depth
        name = self.__class__.__name__
        children = []
        for k, v in self.__dict__.items():
            if k == "line":
                continue
            if isinstance(v, ASTNode):
                children.append(f"{indent}  {k}:\n{v._tree_str(depth + 2)}")
            elif isinstance(v, list):
                items = "\n".join(
                    n._tree_str(depth + 2) if isinstance(n, ASTNode)
                    else f"{'  ' * (depth + 2)}{n!r}"
                    for n in v
                )
                children.append(f"{indent}  {k}:\n{items}")
            else:
                children.append(f"{indent}  {k}: {v!r}")
        body = "\n".join(children)
        return f"{indent}{name}\n{body}" if children else f"{indent}{name}"


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------
@dataclass
class Program(ASTNode):
    rules: List[ASTNode] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------
@dataclass
class PriorityRule(ASTNode):
    """PRIORITY <condition> SET SIGNAL <signal_state>"""
    condition:    ASTNode = None
    signal_state: str     = ""


@dataclass
class IfRule(ASTNode):
    """IF <condition> THEN <action> [ELSE <action>]"""
    condition:   ASTNode           = None
    then_action: ASTNode           = None
    else_action: Optional[ASTNode] = None


@dataclass
class DenyAllowRule(ASTNode):
    """DENY | ALLOW <condition> ENTRY <lane_id>"""
    verb:      str     = ""      # "DENY" or "ALLOW"
    condition: ASTNode = None
    lane_id:   str     = ""


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------
@dataclass
class AssignAction(ASTNode):
    """<identifier> = <expr>"""
    target: str     = ""
    value:  ASTNode = None


@dataclass
class SetSignalAction(ASTNode):
    """SET SIGNAL <state>"""
    state: str = ""


# ---------------------------------------------------------------------------
# Conditions / Expressions
# ---------------------------------------------------------------------------
@dataclass
class BinaryCondition(ASTNode):
    """<cond> AND|OR <cond>"""
    op:    str     = ""
    left:  ASTNode = None
    right: ASTNode = None


@dataclass
class NotCondition(ASTNode):
    """NOT <cond>"""
    operand: ASTNode = None


@dataclass
class Comparison(ASTNode):
    """<expr> <relop> <expr>"""
    op:    str     = ""
    left:  ASTNode = None
    right: ASTNode = None


@dataclass
class BinaryExpr(ASTNode):
    """<expr> +|-|*|/ <expr>"""
    op:    str     = ""
    left:  ASTNode = None
    right: ASTNode = None


@dataclass
class Identifier(ASTNode):
    name: str = ""


@dataclass
class NumLiteral(ASTNode):
    value: Any  = None    # int or float
    raw:   str  = ""


@dataclass
class StringLiteral(ASTNode):
    value: str = ""       # without surrounding quotes


@dataclass
class BoolLiteral(ASTNode):
    value: bool = False
