from __future__ import annotations

import ast
import operator
import uuid
from datetime import datetime, timezone
from sqlite3 import Connection
from typing import Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status

from app.auth import CurrentUser
from app.db.schema import utc_now
from app.services.file_processor import get_file_contexts


class ToolDispatcher:
    def __init__(self, db: Connection, user: CurrentUser, enabled_tools: list[str]):
        self.db = db
        self.user = user
        self.enabled_tools = set(enabled_tools)
        self._tools: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "datetime": self._datetime,
            "calculator": self._calculator,
            "summarize_file": self._summarize_file,
        }

    @property
    def available_tools(self) -> list[str]:
        return sorted(self._tools.keys())

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in self._tools:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown tool: {name}")
        if name not in self.enabled_tools:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Tool disabled: {name}")
        try:
            result = self._tools[name](arguments)
            self._record(name, arguments, result, ok=True)
            return {"name": name, "ok": True, "result": result, "error": None}
        except HTTPException:
            raise
        except Exception as exc:
            result = {"error_type": type(exc).__name__}
            self._record(name, arguments, result, ok=False)
            return {"name": name, "ok": False, "result": None, "error": str(exc)}

    def _datetime(self, arguments: dict[str, Any]) -> dict[str, Any]:
        requested_timezone = str(arguments.get("timezone", "UTC"))
        try:
            local_timezone = ZoneInfo(requested_timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown timezone: {requested_timezone}") from exc
        return {
            "timezone": requested_timezone,
            "utc": datetime.now(timezone.utc).isoformat(),
            "local": datetime.now(local_timezone).isoformat(),
        }

    def _calculator(self, arguments: dict[str, Any]) -> dict[str, Any]:
        expression = str(arguments.get("expression", ""))
        if not expression.strip():
            raise ValueError("Missing expression")
        if len(expression) > 120:
            raise ValueError("Expression is too long")
        return {"expression": expression, "value": safe_eval(expression)}

    def _summarize_file(self, arguments: dict[str, Any]) -> dict[str, Any]:
        file_id = str(arguments.get("file_id", ""))
        if not file_id:
            raise ValueError("Missing file_id")
        file_context = get_file_contexts(self.db, self.user, [file_id])[0]
        text = file_context.get("extracted_text") or ""
        preview = text[:1200]
        return {
            "file_id": file_id,
            "filename": file_context["filename"],
            "summary": file_context["summary"],
            "preview": preview,
        }

    def _record(self, name: str, arguments: dict[str, Any], output: dict[str, Any], ok: bool) -> None:
        import json

        self.db.execute(
            """
            INSERT INTO tool_runs (id, user_id, tool_name, input, output, ok, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                self.user.id,
                name,
                json.dumps(arguments),
                json.dumps(output),
                1 if ok else 0,
                utc_now(),
            ),
        )
        self.db.commit()


ALLOWED_BINARY_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
ALLOWED_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def safe_eval(expression: str) -> float:
    tree = ast.parse(expression, mode="eval")
    return float(_eval_node(tree.body))


def _eval_node(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in ALLOWED_BINARY_OPS:
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 12:
            raise ValueError("Exponent is too large")
        return ALLOWED_BINARY_OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in ALLOWED_UNARY_OPS:
        return ALLOWED_UNARY_OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError("Expression can only contain numbers and arithmetic operators")
