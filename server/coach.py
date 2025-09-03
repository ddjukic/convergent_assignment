import asyncio
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import google.generativeai as genai
from loguru import logger
from dotenv import load_dotenv

from prompts_loader import PromptsRepository

# Load .env specifically from the server directory to ensure keys are available
_ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=_ENV_PATH, override=False)

# Enable automatic tracing for all Google Gemini calls
if os.environ.get("ENABLE_TRACING"):
    try:
        from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor
        GoogleGenAIInstrumentor().instrument()
        logger.info("[COACH] Google GenAI instrumentation enabled for automatic tracing")
    except Exception as e:
        logger.warning(f"[COACH] Failed to enable Google GenAI instrumentation: {e}")

def _safe_json_extract(text: str) -> Optional[Dict[str, Any]]:
    """Attempt to extract the first valid JSON object from text.

    The model may return code fences or trailing commentary. This function tries to
    find the first '{' and the last '}' and parse the substring. Returns None on
    failure.
    """
    if not text:
        return None
    try:
        # Fast path
        return json.loads(text)
    except Exception:
        pass
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            frag = text[start : end + 1]
            return json.loads(frag)
    except Exception:
        return None
    return None


@dataclass
class TurnEvaluation:
    turn_number: int
    customer_message: str
    representative_response: str
    raw_text: str
    parsed: Optional[Dict[str, Any]] = None


@dataclass
class ConversationState:
    scenario: str
    persona_name: str
    last_customer_message: Optional[str] = None
    last_evaluated_rep_response: Optional[str] = None
    turn_index: int = 0
    evaluations: List[TurnEvaluation] = field(default_factory=list)


class GeminiCoach:
    """A conversation coach using standard Gemini API for turn-by-turn evaluation.
    
    This version uses stateless API calls instead of Live API sessions,
    making it more reliable for turn-based evaluation.

    Using 1.5-flash as a good balance of cost, performance, and quality; 
    Outdated, but 2.5 models have very strong safety filters, if we talking about bank cards and such,
    they just block the output and break the functionallity.
    """

    def __init__(self, prompts_repo: PromptsRepository, model: str = "gemini-1.5-flash"):
        self._prompts_repo = prompts_repo
        self._model_name = model
        self._model = None
        self._api_key = os.environ.get("GEMINI_API_KEY")
        
    async def start(self) -> None:
        """Initialize the Gemini model."""
        if not self._api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        
        genai.configure(api_key=self._api_key)
        self._model = genai.GenerativeModel(self._model_name)
        logger.info(f"[COACH] Initialized Gemini model: {self._model_name}")

    def is_ready(self) -> bool:
        return self._model is not None

    async def ensure_started(self) -> None:
        if not self.is_ready():
            await self.start()

    async def stop(self) -> None:
        """No cleanup needed for standard API."""
        self._model = None
        logger.info("[COACH] Coach stopped")

    def _build_evaluation_prompt(
        self,
        state: ConversationState,
        customer_prompt: str,
        representative_response: str
    ) -> str:
        """Build the complete prompt for turn evaluation with full context.
        
        Args:
            customer_prompt: What the customer (assistant bot) said
            representative_response: How the bank rep (human user) responded
        """
        
        # Get the coach system prompt from prompts.json
        coach_prompt = self._prompts_repo.find(entity="coach_agent", name_contains="Main System")
        if not coach_prompt:
            # Fallback to basic prompt
            coach_system = self._prompts_repo.coach_main_system_prompt()
        else:
            coach_system = coach_prompt[0].content.get("system", "")
            role_expertise = "\n".join(coach_prompt[0].content.get("role_expertise", []))
            eval_criteria = "\n".join([f"- {c}" for c in coach_prompt[0].content.get("evaluation_criteria", [])])
            guidelines = "\n".join([f"- {g}" for g in coach_prompt[0].content.get("behavioral_guidelines", [])])
            philosophy = "\n".join([f"- {p}" for p in coach_prompt[0].content.get("coaching_philosophy", [])])
            
            coach_system = f"""{coach_system}

                        **Your Role & Expertise:**
                        {role_expertise}

                        **Evaluation Criteria:**
                        {eval_criteria}

                        **Behavioral Guidelines:**
                        {guidelines}

                        **Coaching Philosophy:**
                        {philosophy}"""

        # Get persona information for context
        persona_prompts = self._prompts_repo.find(entity="simulation_customer", scenario=state.scenario)
        if persona_prompts:
            persona_info = persona_prompts[0].content
            emotional_state = persona_info.get("emotional_state", "Unknown")
            key_phrases = persona_info.get("key_phrases", [])
            backstory = persona_info.get("backstory", [])
            
            scenario_context = f"""
                            **Current Scenario Context:**
                            CUSTOMER PERSONA: {state.persona_name}
                            SCENARIO: {state.scenario}
                            EMOTIONAL STATE: {emotional_state}
                            CUSTOMER BACKSTORY: {'; '.join(backstory[:2])}
                            KEY CUSTOMER CONCERNS: {'; '.join(key_phrases[:2])}
                            """
        else:
            scenario_context = f"""
            **Current Scenario Context:**
            CUSTOMER PERSONA: {state.persona_name}
            SCENARIO: {state.scenario}
            """

        # Build the complete prompt
        instruction = """Evaluate this single turn in the customer service conversation. 
            Analyze how well the bank representative handled the customer's message.
            Focus on the representative's response quality, empathy, and problem-solving.
            Provide ONLY the JSON object, no additional text or markdown."""

        turn_context = f"""
                        **Turn Details:**
                        - Turn Number: {state.turn_index}
                        - Customer Statement: "{customer_prompt}"
                        - Representative Response: "{representative_response}"

                        **Required JSON Output:**
                        {{
                        "turn_quality_score": <0-10>,
                        "immediate_strengths": ["specific strength observed"],
                        "immediate_concerns": ["specific concern to address"],
                        "next_turn_guidance": "specific suggestion for what to do next",
                        "compliance_check": "pass/warning/fail with brief reason",
                        "urgency_level": "low/medium/high - based on customer emotional state"
                        }}
                        """

        return f"""{coach_system}

                    {scenario_context}

                    {instruction}

                    {turn_context}"""

    async def evaluate_turn(
        self,
        state: ConversationState,
        customer_prompt: str,
        representative_response: str,
    ) -> Optional[TurnEvaluation]:
        """Send a turn to the coach for evaluation using standard Gemini API.
        
        Debounces duplicate evaluations by skipping if the representative response
        has already been evaluated and no new customer message has arrived.
        """
        # Debounce logic
        if (
            state.last_evaluated_rep_response == representative_response
            and state.last_customer_message == customer_prompt
        ):
            logger.debug("[COACH] Skipping duplicate evaluation")
            return None

        state.turn_index += 1
        state.last_customer_message = customer_prompt
        state.last_evaluated_rep_response = representative_response

        # Build the complete prompt
        prompt = self._build_evaluation_prompt(state, customer_prompt, representative_response)
        
        logger.info(
            f"[COACH] Evaluating turn {state.turn_index}: "
            f"persona='{state.persona_name}', scenario='{state.scenario}'"
        )
        
        # Automatic tracing via GoogleGenAIInstrumentor handles this

        try:
            # Use async timeout for the API call with relaxed safety settings
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self._model.generate_content,
                    prompt,
                    generation_config={
                        "temperature": 0.3,
                        "max_output_tokens": 500,
                        "response_mime_type": "text/plain",
                    },
                    safety_settings={
                        "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
                        "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
                        "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
                        "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
                    }
                ),
                timeout=10.0
            )
            
            # Check if response was blocked by safety filters
            if response and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'finish_reason'):
                    from google.generativeai.types import GenerationConfig
                    if candidate.finish_reason == 2:  # SAFETY
                        logger.warning(f"[COACH] Response blocked by safety filters")
                        raw_text = "Response blocked by safety filters"
                    else:
                        raw_text = response.text if response else ""
                else:
                    raw_text = response.text if response else ""
            else:
                raw_text = ""
            
            if raw_text and raw_text != "Response blocked by safety filters":
                logger.debug(f"[COACH] Raw response: {raw_text[:200]}...")
            
            parsed = _safe_json_extract(raw_text)
            
            # Log token usage for debugging
            if hasattr(response, 'usage_metadata'):
                logger.debug(
                    f"[COACH] Tokens - prompt: {response.usage_metadata.prompt_token_count}, "
                    f"completion: {response.usage_metadata.candidates_token_count}, "
                    f"total: {response.usage_metadata.prompt_token_count + response.usage_metadata.candidates_token_count}"
                )
            
            if parsed:
                logger.info(f"[COACH] Turn {state.turn_index} evaluation: score={parsed.get('turn_quality_score')}")
            else:
                logger.warning(f"[COACH] Failed to parse JSON from response")
                
        except asyncio.TimeoutError:
            logger.error(f"[COACH] Evaluation timeout for turn {state.turn_index}")
            raw_text = "Timeout"
            parsed = None
        except Exception as e:
            logger.error(f"[COACH] Evaluation error for turn {state.turn_index}: {e}")
            raw_text = str(e)
            parsed = None

        evaluation = TurnEvaluation(
            turn_number=state.turn_index,
            customer_message=customer_prompt,  # Keeping field name for compatibility
            representative_response=representative_response,
            raw_text=raw_text,
            parsed=parsed,
        )
        state.evaluations.append(evaluation)
        
        return evaluation

    async def summarize_conversation(self, state: ConversationState) -> Optional[Dict[str, Any]]:
        """Generate end-to-end assessment of the complete conversation."""
        if not state.evaluations:
            return None

        # Get coach system prompt
        coach_prompt = self._prompts_repo.find(entity="coach_agent", name_contains="Main System")
        if coach_prompt:
            coach_system = coach_prompt[0].content.get("system", "")
        else:
            coach_system = self._prompts_repo.coach_main_system_prompt()

        instruction = """Analyze the complete customer service conversation and provide comprehensive feedback.
                        Provide ONLY the JSON object per the schema, no additional text."""

        # Build transcript text
        lines: List[str] = []
        for ev in state.evaluations:
            lines.append(f"Turn {ev.turn_number} - Customer: {ev.customer_message}")
            lines.append(f"Turn {ev.turn_number} - Representative: {ev.representative_response}")
        transcript_text = "\n".join(lines)

        summary_schema = """
                        {
                        "overall_performance_score": <0-10>,
                        "category_scores": {
                            "greeting_verification": <0-10>,
                            "clarity": <0-10>,
                            "empathy": <0-10>,
                            "probing": <0-10>,
                            "resolution_focus": <0-10>,
                            "compliance": <0-10>
                        },
                        "key_strengths": ["specific strength with evidence"],
                        "priority_improvements": ["specific area needing work"],
                        "coaching_recommendations": ["specific training area"]
                        }"""

        prompt = f"""{coach_system}

                    {instruction}

                    **Full Transcript:**
                    {transcript_text}

                    **Required JSON Output:**
                    {summary_schema}"""
        
        # Automatic tracing via GoogleGenAIInstrumentor handles this

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self._model.generate_content,
                    prompt,
                    generation_config={
                        "temperature": 0.3,
                        "max_output_tokens": 800,
                    },
                    safety_settings={
                        "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
                        "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
                        "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
                        "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
                    }
                ),
                timeout=15.0
            )
            
            # Check if response was blocked by safety filters
            if response and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'finish_reason') and candidate.finish_reason == 2:  # SAFETY
                    logger.warning(f"[COACH][SUMMARY] Response blocked by safety filters")
                    raw = "Response blocked by safety filters"
                    parsed = None
                else:
                    raw = response.text if response else ""
                    parsed = _safe_json_extract(raw)
            else:
                raw = ""
                parsed = None
            
            # Log token usage for debugging
            if hasattr(response, 'usage_metadata'):
                logger.debug(
                    f"[COACH] Summary tokens - prompt: {response.usage_metadata.prompt_token_count}, "
                    f"completion: {response.usage_metadata.candidates_token_count}, "
                    f"total: {response.usage_metadata.prompt_token_count + response.usage_metadata.candidates_token_count}"
                )
            
            logger.info(f"[COACH][SUMMARY] Generated summary evaluation")
            return parsed
            
        except Exception as e:
            logger.error(f"[COACH] Summary generation error: {e}")
            return None
    
    async def generate_session_assessment(
        self, 
        state: ConversationState, 
        transcript: List[Dict[str, Any]]
    ) -> str:
        """Generate markdown assessment for the session."""
        if not transcript:
            return "# Session Assessment\n\nNo transcript available for assessment."
        
        # Get assessment prompt
        assessment_prompt = self._prompts_repo.find(entity="coach_agent", name_contains="Session Assessment")
        if not assessment_prompt:
            logger.error("[COACH] Session assessment prompt not found")
            return "# Session Assessment\n\nAssessment configuration not found."
        
        prompt_content = assessment_prompt[0].content
        instruction = prompt_content.get("instruction", "")
        achievements_list = prompt_content.get("achievements", [])
        
        # Build conversation text with evidence markers
        conversation_lines = []
        for i, entry in enumerate(transcript, 1):
            role = entry.get("role", "").title()
            content = entry.get("content", "")
            timestamp = entry.get("ts", "")
            conversation_lines.append(f"[Turn {i} - {timestamp}]")
            conversation_lines.append(f"{role}: {content}")
            conversation_lines.append("")
        
        conversation_text = "\n".join(conversation_lines)
        
        # Build the assessment prompt
        system_prompt = f"""You are an expert customer service coach providing detailed session assessments.
        {instruction}
        
        Available achievements to award (be selective, only award if truly earned):
        {chr(10).join(achievements_list)}
        
        Generate a markdown assessment with:
        1. Overall performance score (0-10)
        2. Category scores for each evaluation area
        3. Specific strengths with quoted evidence
        4. Areas for improvement with specific examples
        5. Actionable training recommendations
        6. Achievements earned (if any)
        
        IMPORTANT: Quote specific utterances from the representative as evidence.
        Format quotes like: "As shown in Turn 3: 'I understand this must be frustrating...'"
        """
        
        assessment_prompt_text = f"""{system_prompt}
        
        **Session Details:**
        - Customer: {state.persona_name}
        - Scenario: {state.scenario}
        - Total Turns: {len(transcript)}
        
        **Full Conversation Transcript:**
        {conversation_text}
        
        Generate the markdown assessment now. Be specific and quote evidence."""
        
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self._model.generate_content,
                    assessment_prompt_text,
                    generation_config={
                        "temperature": 0.4,
                        "max_output_tokens": 1500,
                        "response_mime_type": "text/plain",
                    },
                    safety_settings={
                        "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
                        "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
                        "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
                        "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
                    }
                ),
                timeout=20.0
            )
            
            if response and response.text:
                logger.info("[COACH] Session assessment generated successfully")
                return response.text
            else:
                logger.warning("[COACH] Empty assessment response")
                return "# Session Assessment\n\nAssessment generation failed - no response received."
                
        except asyncio.TimeoutError:
            logger.error("[COACH] Session assessment timeout")
            return "# Session Assessment\n\nAssessment generation timed out."
        except Exception as e:
            logger.error(f"[COACH] Session assessment error: {e}")
            return f"# Session Assessment\n\nAssessment generation failed: {str(e)}"


if __name__ == "__main__":
    # Minimal self-test: send a single synthetic turn and print parsed JSON
    import asyncio as _asyncio

    async def _main():
        repo = PromptsRepository()
        coach = GeminiCoach(repo)
        await coach.start()
        state = ConversationState(scenario="card", persona_name="Sarah Chen")
        ev = await coach.evaluate_turn(
            state,
            customer_prompt="I lost my debit card this morning and need cash for groceries.",
            representative_response="I'm sorry to hear that. I'll freeze your card now and arrange emergency cash at a nearby branch. May I verify your identity first?",
        )
        print("RAW:", ev.raw_text if ev else "No evaluation")
        print("PARSED:", ev.parsed if ev else "No parsed data")
        await coach.stop()

    _asyncio.run(_main())