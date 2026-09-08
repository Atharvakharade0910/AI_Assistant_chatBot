import re


PROMPT_INJECTION_PATTERNS = (
    r"ignore (all|any|previous|prior) instructions",
    r"reveal (the )?(system|developer) prompt",
    r"disable (the )?(safety|security) rules",
    r"bypass (the )?(guardrails|safety)",
)


def check_input_guardrails(message: str) -> tuple[bool, str | None]:
    """Return a decision without attempting to inspect or persist sensitive content."""
    normalized = " ".join(message.lower().split())
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, normalized):
            return False, "This request conflicts with the assistant's safety rules."
    return True, None
