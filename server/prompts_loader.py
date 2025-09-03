import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


PROMPTS_PATH_DEFAULT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "prompts.json")


@dataclass
class Prompt:
    id: str
    name: str
    entity: str
    prompt_version: str
    date_updated: str
    content: Dict[str, Any]
    persona: Optional[str] = None
    scenario: Optional[str] = None


class PromptsRepository:
    def __init__(self, path: Optional[str] = None):
        self._path = path or PROMPTS_PATH_DEFAULT
        self._data: Dict[str, Any] = {}
        self._index: Dict[str, Prompt] = {}
        self._load()

    def _load(self) -> None:
        with open(self._path, "r", encoding="utf-8") as f:
            self._data = json.load(f)
        prompts: List[Dict[str, Any]] = self._data.get("prompts", [])
        for p in prompts:
            prompt = Prompt(
                id=p["id"],
                name=p.get("name", p["id"]),
                entity=p.get("entity", "unknown"),
                prompt_version=p.get("prompt_version", "1.0.0"),
                date_updated=p.get("date_updated", ""),
                persona=p.get("persona"),
                scenario=p.get("scenario"),
                content=p.get("content", {}),
            )
            self._index[prompt.id] = prompt

    def by_id(self, prompt_id: str) -> Prompt:
        return self._index[prompt_id]

    def find(self, *, entity: Optional[str] = None, scenario: Optional[str] = None, name_contains: Optional[str] = None) -> List[Prompt]:
        results: List[Prompt] = list(self._index.values())
        if entity:
            results = [p for p in results if p.entity == entity]
        if scenario:
            results = [p for p in results if p.scenario == scenario]
        if name_contains:
            results = [p for p in results if name_contains.lower() in p.name.lower()]
        return results

    def persona_system_prompt_for_scenario(self, scenario: str) -> str:
        matches = self.find(entity="simulation_customer", scenario=scenario)
        if not matches:
            raise KeyError(f"No persona prompt found for scenario '{scenario}'")
        return matches[0].content.get("system", "")

    def coach_main_system_prompt(self) -> str:
        matches = self.find(entity="coach_agent", name_contains="Main System Prompt")
        if not matches:
            raise KeyError("No coach main system prompt found")
        return matches[0].content.get("system", "")

    def coach_turn_eval_schema(self) -> Dict[str, Any]:
        matches = self.find(entity="coach_agent", name_contains="Turn-by-Turn Evaluation")
        if not matches:
            raise KeyError("No coach turn evaluation prompt found")
        return matches[0].content.get("json_schema", {})

    def coach_e2e_schema(self) -> Dict[str, Any]:
        matches = self.find(entity="coach_agent", name_contains="End-to-End Assessment")
        if not matches:
            raise KeyError("No coach end-to-end prompt found")
        return matches[0].content.get("json_schema", {})

    def scenario_info(self, scenario: str) -> Dict[str, str]:
        matches = self.find(entity="simulation_customer", scenario=scenario)
        if not matches:
            raise KeyError(f"No persona prompt found for scenario '{scenario}'")
        p = matches[0]
        system_text = (p.content or {}).get("system", "").strip()
        brief = system_text.split(". ")[0].strip() if system_text else ""
        if len(brief) > 200:
            brief = brief[:200] + "…"
        return {
            "persona": p.persona or "",
            "name": p.name,
            "brief": brief,
        }


__all__ = ["PromptsRepository", "Prompt", "PROMPTS_PATH_DEFAULT"]


