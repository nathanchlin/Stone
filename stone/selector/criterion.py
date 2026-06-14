"""Safe strategy criterion evaluator using an AST whitelist."""

import ast

ALLOWED_NODES = (
    ast.Expression,
    ast.Compare,
    ast.BoolOp,
    ast.Name,
    ast.Constant,
    ast.And,
    ast.Or,
    ast.GtE,
    ast.LtE,
    ast.Gt,
    ast.Lt,
    ast.Eq,
    ast.NotEq,
    ast.Load,
)


def safe_eval_criterion(expr: str, value: float) -> bool:
    """Evaluate a criterion expression against a numeric value."""
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"非法表达式 (syntax error): {expr}") from exc

    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_NODES):
            raise ValueError(f"非法表达式 (disallowed node {type(node).__name__}): {expr}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id != "value":
            raise ValueError(f"非法表达式 (unknown name '{node.id}'): {expr}")

    compiled = compile(tree, "<strategy>", "eval")
    result = eval(compiled, {"__builtins__": {}}, {"value": value})  # noqa: S307
    return bool(result)
