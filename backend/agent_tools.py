import ast
import json
import operator
import urllib.parse
import urllib.request

from langchain.agents import create_agent
from langchain.tools import tool


_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod}


def _calculate(node):
    if isinstance(node, ast.Expression):
        return _calculate(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _calculate(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left, right = _calculate(node.left), _calculate(node.right)
        if abs(left) > 10**12 or abs(right) > 10**12:
            raise ValueError("Number too large")
        return _OPS[type(node.op)](left, right)
    raise ValueError("Only basic arithmetic is allowed")


@tool
def calculator(expression: str) -> str:
    """Calculate a basic arithmetic expression. Never use this for code execution."""
    try:
        tree = ast.parse(expression.strip(), mode="eval")
        return str(_calculate(tree))
    except Exception as exc:
        return f"Calculator error: {exc}"


@tool
def web_search(query: str) -> str:
    """Search the public web using DuckDuckGo Instant Answer and return concise source snippets."""
    params = urllib.parse.urlencode({"q": query, "format": "json", "no_html": 1, "skip_disambig": 1})
    request = urllib.request.Request(
        f"https://api.duckduckgo.com/?{params}",
        headers={"User-Agent": "SimpleChat/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
        results = []
        if data.get("AbstractText"):
            results.append(f"{data['AbstractText']}\nSource: {data.get('AbstractURL', '')}")
        for item in data.get("RelatedTopics", [])[:5]:
            if item.get("Text"):
                results.append(f"{item['Text']}\nSource: {item.get('FirstURL', '')}")
        return "\n\n".join(results) or "No concise DuckDuckGo result was found."
    except Exception as exc:
        return f"Web search unavailable: {exc}"


def should_use_agent(message: str) -> bool:
    text = message.lower()
    return any(word in text for word in ("calculate", "what is", "search the web", "search online", "latest", "news", "current"))


def build_agent(model, system_prompt):
    return create_agent(model, tools=[calculator, web_search], system_prompt=system_prompt)
