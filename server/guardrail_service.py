"""
Guardrail Service for LLM Character Constancy

This module provides guardrail patterns and enforcement for keeping LLM personas
in character and preventing off-topic or meta-conversations. All patterns are
loaded from prompts.json for versioning and easy updates.
"""

import types
from typing import Optional, Dict, List, Tuple, Any
from loguru import logger

from prompts_loader import PromptsRepository


class GuardrailService:
    """Service for managing LLM guardrails from prompts.json"""
    
    def __init__(self, prompts_repo: PromptsRepository):
        """Initialize the guardrail service with patterns from prompts repository.
        
        Args:
            prompts_repo: PromptsRepository instance to load patterns from
        """
        self.prompts_repo = prompts_repo
        self.patterns: Dict[str, Any] = {
            'off_topic': [],
            'banking_keywords': [],
            'reminders': {},
            'version': 'unknown'
        }
        self._load_patterns()
    
    def _load_patterns(self) -> None:
        """Load guardrail patterns from prompts.json"""
        try:
            guardrail_prompts = self.prompts_repo.find(entity="guardrail")
            if not guardrail_prompts:
                logger.warning("[GUARDRAIL] No guardrail patterns found in prompts.json")
                return
                
            guardrail = guardrail_prompts[0]
            content = guardrail.content
            
            self.patterns = {
                'off_topic': content.get('off_topic_patterns', []),
                'banking_keywords': content.get('banking_context', []),
                'reminders': content.get('system_reminders', {}),
                'version': guardrail.prompt_version
            }
            
            logger.info(
                f"[GUARDRAIL] Loaded patterns v{self.patterns['version']}: "
                f"{len(self.patterns['off_topic'])} off-topic patterns, "
                f"{len(self.patterns['banking_keywords'])} banking keywords"
            )
        except Exception as e:
            logger.error(f"[GUARDRAIL] Failed to load patterns: {e}")
    
    def check_off_topic(self, message: str, scenario: str) -> Tuple[bool, Optional[str]]:
        """Check if a message is off-topic and return appropriate reminder.
        
        Args:
            message: The user message to check
            scenario: Current scenario ('card', 'transfer', or 'account')
            
        Returns:
            Tuple of (is_off_topic, reminder_message)
        """
        if not message:
            return False, None
            
        msg_lower = message.lower()
        
        # Check if message has banking context (makes it on-topic)
        has_banking_context = any(
            keyword in msg_lower 
            for keyword in self.patterns['banking_keywords']
        )
        
        # Check for off-topic patterns
        is_off_topic = any(
            pattern in msg_lower 
            for pattern in self.patterns['off_topic']
        ) and not has_banking_context
        
        if is_off_topic:
            # Get scenario-specific reminder or use a default
            reminder = self.patterns['reminders'].get(
                scenario,
                "Stay in character! You're in a crisis and need help with your banking issue NOW!"
            )
            return True, reminder
            
        return False, None
    
    def create_patched_llm(self, llm, scenario: str):
        """Apply guardrail monkey-patch to LLM service.
        
        This patches the _process_context method to inject guardrail reminders
        when off-topic patterns are detected.
        
        Args:
            llm: The LLM service instance to patch
            scenario: Current scenario for context-aware reminders
            
        Returns:
            The patched LLM service instance
        """
        # Store original method
        original_process_context = llm._process_context
        
        # Capture reference to this service for use in closure
        service = self
        
        async def guarded_process_context(self, context):
            """Patched _process_context that injects guardrail reminders"""
            
            # Extract messages from context
            messages = []
            if hasattr(context, 'get_messages'):
                messages = context.get_messages()
            elif hasattr(context, 'messages'):
                messages = context.messages
            
            # Find last user message
            last_user_msg = None
            for msg in reversed(messages):
                if isinstance(msg, dict) and msg.get('role') == 'user':
                    last_user_msg = msg.get('content', '')
                    break
            
            # Check if last user message is off-topic
            if last_user_msg:
                is_off_topic, reminder = service.check_off_topic(last_user_msg, scenario)
                
                if is_off_topic:
                    logger.info(f"[GUARDRAIL] Off-topic detected: '{last_user_msg[:60]}...'")
                    
                    # Create reminder message
                    reminder_msg = {
                        "role": "system",
                        "content": reminder
                    }
                    
                    # Try different methods to inject the reminder into context
                    if hasattr(context, 'add_message'):
                        context.add_message(reminder_msg)
                        logger.debug("[GUARDRAIL] Injected reminder via add_message()")
                    elif hasattr(context, '_messages') and isinstance(context._messages, list):
                        context._messages.append(reminder_msg)
                        logger.debug("[GUARDRAIL] Injected reminder via _messages list")
                    elif hasattr(context, 'messages') and isinstance(context.messages, list):
                        context.messages.append(reminder_msg)
                        logger.debug("[GUARDRAIL] Injected reminder via messages list")
                    else:
                        logger.warning("[GUARDRAIL] Could not inject reminder - unknown context structure")
            
            # Call original method with potentially modified context
            return await original_process_context(context)
        
        # Apply the monkey-patch using types.MethodType for proper binding
        llm._process_context = types.MethodType(guarded_process_context, llm)
        
        logger.info(
            f"[GUARDRAIL] LLM patched for scenario '{scenario}' "
            f"with guardrails v{self.patterns['version']}"
        )
        
        return llm


__all__ = ['GuardrailService']