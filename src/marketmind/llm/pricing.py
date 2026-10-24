"""USD per 1M tokens (input, output), used when the provider doesn't report cost itself.

Checked against OpenRouter's model API and Anthropic's price list on 2026-10-24.
"""

PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "deepseek/deepseek-v4.1-flash-1017": (0.21, 0.84),  # Fireworks host (D37)
    "z-ai/glm-5.3-flash": (0.15, 0.50),
    "anthropic/claude-haiku-5.5": (0.10, 0.50),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
}


def cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    price_in, price_out = PRICES_PER_MTOK.get(model, (0.0, 0.0))
    return (tokens_in * price_in + tokens_out * price_out) / 1_000_000
