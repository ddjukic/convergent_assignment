"""
Conversation aggregator for managing fragmented transcriptions.

This module handles the issue where speech-to-text services (like Deepgram) split
user utterances into multiple transcription fragments that arrive as separate messages.
It aggregates these fragments between assistant responses to provide complete 
conversational context for coach evaluation.

**IMPORTANT**: Role Definitions
- Assistant = Customer (the bot playing a persona like Janet Rodriguez)
- User = Bank Representative (the human being coached)

The coach evaluates how well the USER (bank rep) handles the ASSISTANT (customer).
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from loguru import logger


@dataclass
class ConversationTurn:
    """Represents a complete conversation turn for coach evaluation.
    
    A turn consists of:
    1. Customer prompt (assistant message) - what the customer said
    2. Representative response (user messages) - how the bank rep responded
    """
    customer_prompt: Optional[str] = None  # What the customer (assistant) said
    representative_responses: List[str] = field(default_factory=list)  # Bank rep's (user's) response fragments
    
    def get_aggregated_representative_response(self) -> str:
        """Combine all representative response fragments into one coherent message."""
        if not self.representative_responses:
            return ""
        # Join with space, but clean up any double spaces
        aggregated = " ".join(self.representative_responses)
        # Clean up any redundant spaces
        aggregated = " ".join(aggregated.split())
        return aggregated
    
    def is_complete(self) -> bool:
        """Check if turn has both customer prompt and representative response."""
        return bool(self.customer_prompt and self.representative_responses)


class ConversationAggregator:
    """
    Manages conversation flow and aggregates fragmented user messages.
    
    This class solves the problem where STT services split user utterances into 
    multiple transcriptions (e.g., "Okay." then "I understand." then "When did you...").
    It collects all user message fragments that arrive before an assistant response
    and aggregates them into a single complete utterance for accurate coach evaluation.
    
    Example:
        Customer (assistant) says: "My account is locked and I need to pay employees!"
        Bank Rep (user) responds: "Okay. I understand. When did you first notice the issue?"
        Deepgram fragments: ["Okay.", "I understand.", "When did you first notice the issue?"]
        Aggregator pairs: Customer prompt + aggregated rep response for evaluation
    """
    
    def __init__(self):
        """Initialize the aggregator with empty state."""
        self.pending_customer_prompt: Optional[str] = None  # Current customer (assistant) message
        self.pending_rep_fragments: List[str] = []  # Accumulating bank rep (user) responses
        self.completed_turns: List[ConversationTurn] = []
        self._turn_count = 0
        
    def add_message(self, role: str, content: str) -> Optional[Tuple[str, str]]:
        """
        Add a message to the conversation flow.
        
        Args:
            role: Either "user" (bank rep) or "assistant" (customer)
            content: The message content
            
        Returns:
            Optional tuple of (customer_prompt, representative_response)
            when a complete turn is ready for coach evaluation.
            Returns None if turn is not yet complete.
        """
        if not content or not content.strip():
            logger.debug(f"[AGGREGATOR] Skipping empty {role} message")
            return None
            
        if role == "assistant":  # Customer (bot) speaking
            # Check if we have a pending turn to complete
            if self.pending_customer_prompt and self.pending_rep_fragments:
                # Complete the previous turn before starting new one
                aggregated_rep = " ".join(self.pending_rep_fragments)
                aggregated_rep = " ".join(aggregated_rep.split())  # Clean spaces
                
                previous_prompt = self.pending_customer_prompt
                self._turn_count += 1
                
                # Store completed turn
                turn = ConversationTurn(
                    customer_prompt=previous_prompt,
                    representative_responses=self.pending_rep_fragments.copy()
                )
                self.completed_turns.append(turn)
                
                logger.info(f"[AGGREGATOR] Complete turn #{self._turn_count} ready for evaluation:")
                logger.info(f"  Customer (assistant): '{previous_prompt[:100]}...'")
                logger.info(f"  Representative (user aggregated from {len(self.pending_rep_fragments)} parts): '{aggregated_rep[:100]}...'")
                
                # Reset for new turn
                self.pending_customer_prompt = content.strip()
                self.pending_rep_fragments = []
                
                return (previous_prompt, aggregated_rep)
            else:
                # Starting new turn or initial greeting
                logger.info(f"[AGGREGATOR] Customer (assistant) message starting turn: '{content[:50]}...'")
                self.pending_customer_prompt = content.strip()
                self.pending_rep_fragments = []
                return None
            
        elif role == "user":  # Bank representative (human) responding
            if not self.pending_customer_prompt:
                logger.warning(f"[AGGREGATOR] Bank rep (user) response without customer prompt - ignoring: '{content[:50]}...'")
                return None
                
            # Accumulate bank rep's response fragments
            self.pending_rep_fragments.append(content.strip())
            logger.debug(f"[AGGREGATOR] Added bank rep (user) fragment #{len(self.pending_rep_fragments)}: '{content[:50]}...'")
            return None
                
        else:
            logger.warning(f"[AGGREGATOR] Unknown role: {role}")
            return None
    
    def flush_pending_turn(self) -> Optional[Tuple[str, str]]:
        """
        Flush any pending turn at the end of conversation.
        Returns the final turn if there's a pending customer prompt with representative response.
        """
        if self.pending_customer_prompt and self.pending_rep_fragments:
            aggregated_rep = " ".join(self.pending_rep_fragments)
            aggregated_rep = " ".join(aggregated_rep.split())  # Clean spaces
            
            customer_prompt = self.pending_customer_prompt
            self._turn_count += 1
            
            # Store completed turn
            turn = ConversationTurn(
                customer_prompt=customer_prompt,
                representative_responses=self.pending_rep_fragments.copy()
            )
            self.completed_turns.append(turn)
            
            logger.info(f"[AGGREGATOR] Flushing final turn #{self._turn_count}:")
            logger.info(f"  Customer (assistant): '{customer_prompt[:100]}...'")
            logger.info(f"  Representative (user): '{aggregated_rep[:100]}...'")
            
            # Clear state
            self.pending_customer_prompt = None
            self.pending_rep_fragments = []
            
            return (customer_prompt, aggregated_rep)
        return None
    
    def get_pending_representative_response(self) -> Optional[str]:
        """
        Get the current aggregated representative response without clearing the buffer.
        Useful for debugging or displaying partial representative input.
        """
        if not self.pending_rep_fragments:
            return None
        aggregated = " ".join(self.pending_rep_fragments)
        return " ".join(aggregated.split())  # Clean up spaces
    
    def get_last_complete_turn(self) -> Optional[ConversationTurn]:
        """Get the most recent complete conversation turn."""
        return self.completed_turns[-1] if self.completed_turns else None
    
    def get_turn_count(self) -> int:
        """Get the number of completed turns."""
        return self._turn_count
    
    def reset(self):
        """Clear all state and start fresh."""
        self.pending_customer_prompt = None
        self.pending_rep_fragments = []
        self.completed_turns = []
        self._turn_count = 0
        logger.info("[AGGREGATOR] State reset")
    
    def get_conversation_summary(self) -> str:
        """Get a summary of the conversation flow for debugging."""
        lines = [f"[AGGREGATOR] Conversation Summary: {self._turn_count} completed turns"]
        for i, turn in enumerate(self.completed_turns, 1):
            customer_msg = turn.customer_prompt or "None"
            rep_msg = turn.get_aggregated_representative_response()
            lines.append(f"  Turn {i}:")
            lines.append(f"    Customer (assistant): {customer_msg[:80]}...")
            lines.append(f"    Representative (user): {rep_msg[:80]}...")
        if self.pending_customer_prompt:
            lines.append(f"  Pending customer prompt: {self.pending_customer_prompt[:80]}...")
        if self.pending_rep_fragments:
            lines.append(f"  Pending rep fragments: {len(self.pending_rep_fragments)}")
            for frag in self.pending_rep_fragments:
                lines.append(f"    - {frag[:50]}...")
        return "\n".join(lines)