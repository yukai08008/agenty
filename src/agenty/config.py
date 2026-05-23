"""Agenty configuration management."""

import os
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

CONFIG_DIR = Path.home() / ".config" / "agenty"
CONFIG_FILE = CONFIG_DIR / "config.toml"


def load_config() -> dict:
    """Load config from ~/.config/agenty/config.toml.

    Returns empty dict if file doesn't exist.
    """
    if not CONFIG_FILE.exists():
        return {}
    with open(CONFIG_FILE, "rb") as f:
        return tomllib.load(f)


def get_api_key() -> str | None:
    """Get API key from config or environment variable.

    Priority: AGENT_API_KEY env var > config file
    """
    # Env var takes priority
    env_key = os.environ.get("AGENT_API_KEY")
    if env_key:
        return env_key

    config = load_config()
    return config.get("llm", {}).get("api_key") or None


def ensure_config():
    """Ensure config directory and template file exist.

    Called on first run or when config is missing.
    """
    if CONFIG_FILE.exists():
        return

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    template = Path(__file__).resolve().parent.parent.parent / ".config.example.toml"
    if template.exists():
        content = template.read_text()
    else:
        content = (
            "# Agenty Configuration\n"
            "# Fill in your values below.\n\n"
            "[llm]\n"
            'api_key = ""\n'
            '# base_url = "https://api.openai.com/v1"\n'
            '# model = "gpt-4o"\n'
        )

    CONFIG_FILE.write_text(content)
    return CONFIG_FILE
