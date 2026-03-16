"""
Response provider: abstract interface and implementations.
- MockProvider: returns canned responses (for pipeline testing).
- LLMProvider: calls OpenAI/Anthropic with per-agent system prompts from config/agents.yaml.
"""

import os
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Tuple

import yaml
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Default paths relative to project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "agents.yaml"
MOCK_RESPONSES_PATH = PROJECT_ROOT / "prompts" / "mock_responses.yaml"
MOCK_RESPONSES_BAD_PATH = PROJECT_ROOT / "prompts" / "mock_responses_bad.yaml"


def load_mock_responses(path: Path = None, merge_bad: bool = False) -> dict:
    """Load prompt_id -> response text from YAML. Used for full test-suite simulation with no API calls."""
    path = path or MOCK_RESPONSES_PATH
    if not path.exists():
        return {}
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    out = {}
    if isinstance(data, dict):
        out = {str(k): (v.strip() if isinstance(v, str) else str(v).strip()) for k, v in data.items()}
    if merge_bad and MOCK_RESPONSES_BAD_PATH.exists():
        with open(MOCK_RESPONSES_BAD_PATH, "r") as f:
            bad = yaml.safe_load(f)
        if isinstance(bad, dict):
            for k, v in bad.items():
                out[str(k)] = (v.strip() if isinstance(v, str) else str(v).strip())
    return out


class ResponseProvider(ABC):
    """Abstract: get a response for (agent, prompt) and measure latency."""

    @abstractmethod
    def get_response(self, agent: str, prompt: str, prompt_id: str = "") -> Tuple[str, float]:
        """
        Return (response_text, latency_seconds).
        prompt_id is optional (e.g. for MockProvider to look up canned response).
        """
        pass


class MockProvider(ResponseProvider):
    """
    Returns fixed or deterministic canned responses. Used for testing the pipeline
    without API calls. If prompt_id is in canned_responses, use that; else return
    a generic placeholder per agent.
    """

    def __init__(self, canned_responses: dict = None):
        self.canned = canned_responses or {}
        self._defaults = {
            "trainer": "Here’s a safe, beginner-friendly plan. Always check with your doctor before starting. [Mock trainer response]",
            "chef": "Here are some meal ideas that fit your constraints. [Mock chef response]",
            "productivity": "I’d need access to your calendar to show tomorrow’s events. Would you like to connect it? [Mock productivity response]",
            "health": "This sounds like something to discuss with your healthcare provider. I can explain general info. [Mock health response]",
            "general": "I can help with fitness, nutrition, productivity, or health. What would you like to focus on? [Mock general response]",
        }

    def get_response(self, agent: str, prompt: str, prompt_id: str = "") -> Tuple[str, float]:
        start = time.perf_counter()
        text = self.canned.get(prompt_id) or self._defaults.get(agent) or "No mock response configured."
        elapsed = time.perf_counter() - start
        # Simulate minimal latency so latency score is not always 5
        return text, max(0.5, elapsed)


class LLMProvider(ResponseProvider):
    """
    Loads agent config from config/agents.yaml; calls OpenAI or Anthropic with
    the agent's system prompt + user prompt. Returns response text and latency.
    """

    def __init__(
        self,
        config_path: Path = None,
        provider: str = "openai",
        model: str = None,
    ):
        self.config_path = config_path or CONFIG_PATH
        self.provider = provider
        self.model = model
        self._agent_config = self._load_config()

    def _load_config(self) -> dict:
        if not self.config_path.exists():
            return {}
        with open(self.config_path, "r") as f:
            return yaml.safe_load(f) or {}

    def get_response(self, agent: str, prompt: str, prompt_id: str = "") -> Tuple[str, float]:
        start = time.perf_counter()
        sys_prompt = ""
        if self._agent_config and agent in self._agent_config:
            sys_prompt = self._agent_config[agent].get("system_prompt", "")
        if not sys_prompt:
            sys_prompt = f"You are a helpful assistant for the {agent} domain."

        if self.provider == "anthropic" and ANTHROPIC_API_KEY:
            text = self._call_anthropic(sys_prompt, prompt)
        else:
            if not OPENAI_API_KEY:
                raise RuntimeError("OPENAI_API_KEY or ANTHROPIC_API_KEY required for LLMProvider.")
            text = self._call_openai(sys_prompt, prompt)
        elapsed = time.perf_counter() - start
        return text, elapsed

    def _call_openai(self, system_prompt: str, user_prompt: str) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        model = self.model or "gpt-4o-mini"
        r = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=1500,
        )
        return (r.choices[0].message.content or "").strip()

    def _call_anthropic(self, system_prompt: str, user_prompt: str) -> str:
        from anthropic import Anthropic
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        model = self.model or "claude-3-5-haiku-20241022"
        m = client.messages.create(
            model=model,
            max_tokens=1500,
            temperature=0.3,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        block = next((b for b in m.content if hasattr(b, "text")), None)
        return (block.text if block else "").strip()
