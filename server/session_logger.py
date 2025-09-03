import json
import os
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional


def _now_ms() -> int:
    return int(time.time() * 1000)


def _now_str() -> str:
    # HH_MM_SS_DD_MM_YYYY
    return time.strftime("%H_%M_%S_%d_%m_%Y", time.localtime())


@dataclass
class TranscriptEntry:
    ts_ms: int
    ts: str
    role: str
    content: str


class SessionLogger:
    """File-based session logger for transcripts and coach outputs.

    Files are written to:
      server/.coach/transcripts/transcript_<STAMP>.json
      server/.coach/transcripts/transcript_with_interims_<STAMP>.json
      server/.coach/feedback/per_turn_<STAMP>.json
      server/.coach/feedback/summary_<STAMP>_<SCENARIO>.json
    """

    def __init__(self, scenario: str, session_id: Optional[str] = None):
        stamp = session_id or _now_str()
        root = os.path.dirname(__file__)
        base_dir = os.path.join(root, ".coach")
        transcripts_dir = os.path.join(base_dir, "transcripts")
        feedback_dir = os.path.join(base_dir, "feedback")
        session_evals_dir = os.path.join(base_dir, "session_evals")
        os.makedirs(transcripts_dir, exist_ok=True)
        os.makedirs(feedback_dir, exist_ok=True)
        os.makedirs(session_evals_dir, exist_ok=True)

        self._base_dir = base_dir
        self._transcripts_dir = transcripts_dir
        self._feedback_dir = feedback_dir
        self._session_evals_dir = session_evals_dir
        self._scenario = scenario
        self._session_id = stamp
        self._transcript_path = os.path.join(transcripts_dir, f"transcript_{stamp}.json")
        self._interim_transcript_path = os.path.join(transcripts_dir, f"transcript_with_interims_{stamp}.json")
        self._per_turn_path = os.path.join(feedback_dir, f"per_turn_{stamp}.json")
        self._summary_path = os.path.join(feedback_dir, f"summary_{stamp}_{scenario}.json")
        self._session_eval_path = os.path.join(session_evals_dir, f"session_eval_{stamp}.md")

        self._transcript: List[TranscriptEntry] = []
        self._interim_transcript: List[Dict[str, Any]] = []
        self._coach_turns: List[Dict[str, Any]] = []

    @property
    def base_dir(self) -> str:
        return self._base_dir

    @property
    def transcript_path(self) -> str:
        return self._transcript_path

    @property
    def per_turn_path(self) -> str:
        return self._per_turn_path
    
    @property
    def session_id(self) -> str:
        return self._session_id

    def append_transcript(self, role: str, content: str, is_interim: bool = False) -> None:
        entry = TranscriptEntry(
            ts_ms=_now_ms(), 
            ts=time.strftime("%H:%M:%S %d-%m-%Y", time.localtime()), 
            role=role, 
            content=content
        )
        
        if not is_interim:
            # Final transcriptions go to main transcript
            self._transcript.append(entry)
            self._flush_transcript()
        
        # All messages (including interims) go to interim transcript
        self._interim_transcript.append({
            **asdict(entry),
            "is_interim": is_interim
        })
        self._flush_interim_transcript()

    def append_coach_turn(self, turn_index: int, customer_message: str, representative_response: str, evaluation: Dict[str, Any]) -> None:
        """Append coach evaluation for a conversation turn.
        
        Args:
            turn_index: The turn number
            customer_message: What the customer (assistant bot) said
            representative_response: How the bank rep (user) responded
            evaluation: The coach's evaluation of the representative's response
        """
        entry = {
            "ts_ms": _now_ms(),
            "ts": time.strftime("%H:%M:%S %d-%m-%Y", time.localtime()),
            "turn": turn_index,
            "interaction": {
                "customer": customer_message,  # The customer (assistant) speaks first
                "representative": representative_response,  # The bank rep (user) responds
            },
            "coaching": evaluation,
        }
        self._coach_turns.append(entry)
        self._flush_per_turn()

    def _flush_transcript(self) -> str:
        with open(self._transcript_path, "w", encoding="utf-8") as f:
            json.dump([asdict(t) for t in self._transcript], f, indent=2)
        return self._transcript_path

    def snapshot_transcript(self) -> str:
        return self._flush_transcript()

    def _flush_per_turn(self) -> str:
        with open(self._per_turn_path, "w", encoding="utf-8") as f:
            json.dump(self._coach_turns, f, indent=2)
        return self._per_turn_path
    
    def _flush_interim_transcript(self) -> str:
        with open(self._interim_transcript_path, "w", encoding="utf-8") as f:
            json.dump(self._interim_transcript, f, indent=2)
        return self._interim_transcript_path

    def write_summary(self, summary: Dict[str, Any]) -> str:
        with open(self._summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        return self._summary_path
    
    def write_session_eval(self, markdown_content: str) -> str:
        """Write session evaluation markdown file."""
        with open(self._session_eval_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        return self._session_eval_path
    
    def get_transcript_for_assessment(self) -> List[Dict[str, Any]]:
        """Get the transcript entries for assessment (no interims)."""
        return [asdict(t) for t in self._transcript]


