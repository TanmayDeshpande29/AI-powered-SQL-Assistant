import re

# Matches ```sql ... ``` (or a bare ``` ... ```) and captures the body.
_FENCE = re.compile(r"```(?:[a-zA-Z]+)?\s*\n?(.*?)```", re.DOTALL)


def extract_sql(text: str) -> str:
    """Models often wrap SQL in markdown fences despite instructions; unwrap it."""
    blocks = _FENCE.findall(text)
    if blocks:
        return "\n\n".join(block.strip() for block in blocks)
    return text.strip()
