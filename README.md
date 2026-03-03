# VPTA-RL-Compiler: Vehicle-Priority and Toll Adjustment Rule Language

> **CSE353: Compiler Design** · Integrated Assignment Units 1 & 2  
> Sharda University · Academic Year 2025–2026

A complete **compiler front-end** for a domain-specific language (DSL) that lets traffic management authorities define vehicle-priority rules at smart intersections and dynamic toll adjustment policies on highways — all in a human-readable, formally validated rule script.

---

## Features

| Component | What it does |
|-----------|-------------|
| **Lexer** (`lexer.py`) | Tokenises vpta-rl-compiler source using maximal munch, resolves keywords vs identifiers, and recovers from illegal characters and unterminated strings |
| **Parser** (`parser.py`) | Recursive-descent parser builds a full AST; uses panic-mode synchronisation and insertion recovery for syntax errors |
| **AST Nodes** (`ast_nodes.py`) | Typed dataclasses for every grammar production |
| **Error Reporter** (`error_handler.py`) | Centralised collector for lexical and syntax errors with severity levels |
| **Examples** (`examples/`) | Three sample `.vpta` scripts including a deliberate error-recovery test |
| **Tests** (`tests/`) | 30+ unit tests covering the lexer, parser, and integration pipeline |

---

## Language Overview

vpta-rl-compiler supports three rule types:

```
1. Priority rule — grant green signal to emergency vehicles
PRIORITY VEHICLE_CLASS == "AMBULANCE" SET SIGNAL GREEN ;

2. IF/THEN/ELSE rule — dynamic toll adjustment
IF congestion_level > 80 AND vehicle_class == "HEAVY"
    THEN toll_fee = toll_fee * 1.5
    ELSE toll_fee = toll_fee * 1.0 ;

3. Deny/Allow rule — restrict lane access
DENY VEHICLE_CLASS == "OVERLOADED" ENTRY main_plaza ;
```

### Keywords
`PRIORITY` `IF` `THEN` `ELSE` `SET` `SIGNAL` `DENY` `ALLOW` `ENTRY`  
`AND` `OR` `NOT` `VEHICLE_CLASS` `TRUE` `FALSE` `GREEN` `RED` `YELLOW`

### Token Types

| Category | Examples | Regex |
|----------|---------|-------|
| Keywords | `IF`, `PRIORITY`, `DENY` | `PRIORITY\|IF\|THEN\|…` |
| Identifiers | `toll_fee`, `lane_id` | `[a-zA-Z_][a-zA-Z0-9_]*` |
| Integer Literals | `80`, `22` | `[0-9]+` |
| Float Literals | `1.5`, `0.75` | `[0-9]+\.[0-9]+` |
| String Literals | `"AMBULANCE"` | `"[^"\n]*"` |
| Relational Ops | `==`, `!=`, `>=` | `==\|!=\|<=\|>=\|<\|>` |
| Arithmetic Ops | `+`, `-`, `*`, `/` | `[+\-*/]` |
| Assignment | `=` | `=` |
| Delimiters | `;`, `(`, `)` | `[;()]` |
| Comments | `// note` | `//[^\n]*` |

---

## Project Structure

```
vpta-rl-compiler/
├── main.py              # Compiler driver / CLI entry point
├── lexer.py             # Lexical analyser
├── parser.py            # Recursive-descent parser
├── ast_nodes.py         # AST node dataclasses
├── error_handler.py     # Error reporter & recovery helpers
├── examples/
│   ├── emergency_priority.vpta    # Priority rules only
│   ├── toll_adjustment.vpta       # Toll rules only
│   └── error_recovery_test.vpta  # Deliberate errors
└── tests/
    └── test_lexer.py    # Unit + integration tests
```

---

## Requirements

- Python 3.8+
- No third-party packages required (standard library only)

---

## Usage

```bash
# Run the built-in demo (includes deliberate error recovery)
python main.py --demo

# Compile a .vpta source file
python main.py examples/toll_adjustment.vpta

# Compile quietly (errors only, no token table)
python main.py examples/error_recovery_test.vpta --quiet
```

### Example output

```
────────────────────────────────────────────────────────────
  vpta-rl-compiler Compiler Front-End  |  examples/toll_adjustment.vpta
────────────────────────────────────────────────────────────

[Stage 1] Lexical Analysis …

  TOKEN TYPE             LEXEME                        LINE   COL
  ──────────────────────────────────────────────────────────────
  KEYWORD                'IF'                             3     1
  IDENTIFIER             'congestion_level'               3     4
  RELOP                  '>'                              3    21
  NUM_INT                '80'                             3    23
  KEYWORD                'AND'                            3    26
  ...

[Stage 2] Parsing …
[Stage 2] AST:
Program
  rules:
    IfRule
      condition:
        BinaryCondition
          op: 'AND'
          ...

────────────────────────────────────────────────────────────
✓ No errors detected.

Compilation finished — 0 lexical error(s), 0 syntax error(s), 0 warning(s).
────────────────────────────────────────────────────────────
```

---

## Running the Tests

```bash
# Using pytest (recommended)
pip install pytest
pytest tests/ -v

# Or directly
python tests/test_lexer.py
```

---

## Error Recovery

The front-end never stops at the first error. It applies four strategies:

| Strategy | Trigger | Mechanism |
|----------|---------|-----------|
| **Panic Mode** | Illegal character | Log error, skip character, resume scanning |
| **End-of-line Recovery** | Unterminated string | Treat EOL as closing `"`, emit error token, continue |
| **Synchronisation** | Syntax error mid-rule | Advance to next `;` or rule-start keyword |
| **Insertion Recovery** | Missing `;` | Log "implicitly inserted", do not consume input |

---

## Grammar (BNF)

```
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
action          → IDENTIFIER '=' expr | SET SIGNAL signal_state
expr            → term (('+' | '-') term)*
term            → factor (('*' | '/') factor)*
factor          → IDENTIFIER | NUM_INT | NUM_FLOAT | STRING | BOOL
signal_state    → GREEN | RED | YELLOW
relop           → '==' | '!=' | '<' | '>' | '<=' | '>='
```

---

## Authors

| Name | System ID |
|------|----------------|
| Aditya Pandey | 2023336032 |
| Krish Pankaj Goyal | 2023359271 |
| Aseem Varshney | 2023379326 |

**Group ID:** 23  
**Submitted to:** Mr. Ajai Verma, Dept. of CSE, Sharda University
