#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Client-Server Web Example.

This is the server-side bot implementation for the Pipecat client-server
web example. It runs a simple voice AI bot that you can connect to using a
web browser and speak with it.

Required AI services:
- Deepgram (Speech-to-Text)
- OpenAI (LLM)
- Cartesia (Text-to-Speech)

The example connects between client and server using a P2P WebRTC connection.

Run the bot using::

    python bot.py
"""

import os
import argparse
import uuid

from dotenv import load_dotenv
from loguru import logger
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.frameworks.rtvi import RTVIConfig, RTVIObserver, RTVIProcessor
from pipecat.runner.types import RunnerArguments
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.transcriptions.language import Language
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.openai.llm import BaseOpenAILLMService, OpenAILLMService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.network.small_webrtc import SmallWebRTCTransport
from pipecat.processors.transcript_processor import TranscriptProcessor
from pipecat.utils.tracing.setup import setup_tracing

from prompts_loader import PromptsRepository
from coach import GeminiCoach, ConversationState
from session_logger import SessionLogger
from conversation_aggregator import ConversationAggregator
from guardrail_service import GuardrailService

load_dotenv(override=True)

# Initialize tracing if enabled
IS_TRACING_ENABLED = bool(os.getenv("ENABLE_TRACING"))
if IS_TRACING_ENABLED:
    # Create the OTLP exporter for Langfuse
    otlp_exporter = OTLPSpanExporter()
    
    # Set up tracing with the exporter
    setup_tracing(
        service_name="pipecat-coach-bot",
        exporter=otlp_exporter,
        console_export=bool(os.getenv("OTEL_CONSOLE_EXPORT")),
    )
    logger.info("OpenTelemetry tracing initialized for Langfuse")

REQUIRED_ENV_KEYS = [
    "DEEPGRAM_API_KEY",
    "OPENAI_API_KEY",
    "ELEVENLABS_API_KEY",
    "ELEVENLABS_VOICE_ID",
    "GEMINI_API_KEY",
]

async def run_bot(transport: BaseTransport, scenario: str):
    logger.info(f"Starting bot")

    stt = DeepgramSTTService(api_key=os.getenv("DEEPGRAM_API_KEY"))

    tts = ElevenLabsTTSService(
        api_key=os.getenv("ELEVENLABS_API_KEY"),
        voice_id=os.getenv("ELEVENLABS_VOICE_ID"),
        model="eleven_flash_v2_5", # 50% cheaper, fast, english only -> should be fine while english main language -> known limitation if not
        params=ElevenLabsTTSService.InputParams(
            language=Language.EN,
            stability=0.7,
            similarity_boost=0.8,
            style=0.5,
            use_speaker_boost=True,
            speed=1.1,
            auto_mode=True,
            enable_ssml_parsing=True
        )
    )

    # GPT-4.1-nano for speed & cost, intelligent enough for a simple persona
    # and can be managed via determinism params - see below:
    llm = OpenAILLMService(api_key=os.getenv("OPENAI_API_KEY"),
        model="gpt-4.1-nano",
        params=BaseOpenAILLMService.InputParams(
            temperature=0.4,            # Response creativity (0.0-2.0)
            max_completion_tokens=50,   # Maximum response length -> towards shorter length, more human-like, not essays, less cost, more speech & speed
            frequency_penalty=0.3,      # Reduce repetition (0.0-2.0)
            presence_penalty=0.5,       # Encourage topic diversity (0.0-2.0)
            top_p=0.75,                 # Nucleus sampling parameter
            seed=42,                    # For reproducibility
        ) # see: https://platform.openai.com/docs/advanced-usage
    )

    # Load persona prompt based on scenario
    prompts_repo = PromptsRepository()
    
    # Apply guardrails from prompts.json
    guardrail_service = GuardrailService(prompts_repo)
    llm = guardrail_service.create_patched_llm(llm, scenario)
    
    # Scenario confirmation with brief
    try:
        info = prompts_repo.scenario_info(scenario)
        logger.info(
            f"Scenario loaded: '{scenario}' | Persona: {info.get('persona')} | Description: {info.get('brief')}"
        )
    except Exception as e:
        logger.error(f"Failed to load scenario info: {e}")
        raise
    persona_system = prompts_repo.persona_system_prompt_for_scenario(scenario)
    print(f"Persona system: {persona_system}")

    messages = [
        {
            "role": "system",
            "content": persona_system,
        },
    ]

    context = OpenAILLMContext(messages)
    context_aggregator = llm.create_context_aggregator(context)

    rtvi = RTVIProcessor(config=RTVIConfig(config=[]))
    transcript = TranscriptProcessor()  # Regular transcript processor

    # Coach setup (Gemini)
    coach = GeminiCoach(prompts_repo)
    conv_state = ConversationState(
        scenario=scenario,
        persona_name=prompts_repo.find(entity="simulation_customer", scenario=scenario)[0].persona or "",
    )
    # Attempt eager start; if it fails, we'll try again lazily on first turn
    try:
        await coach.start()
    except Exception as e:
        logger.warning(f"[COACH] Deferred start (will retry on first turn): {e}")

    # Session logger
    session_logger = SessionLogger(scenario=scenario)
    logger.info(f"[COACH] Session logging directory: {session_logger.base_dir}")
    logger.info(f"[COACH] Transcript file (final): {session_logger.transcript_path}")
    logger.info(f"[COACH] Transcript file (with interims): {session_logger._interim_transcript_path}")
    logger.info(f"[COACH] Per-turn file: {session_logger.per_turn_path}")
    logger.info(f"[COACH] Session eval file: {session_logger._session_eval_path}")
    
    # Create conversation aggregator to handle fragmented user messages
    conversation_aggregator = ConversationAggregator()
    
    # Monkey-patch the UserTranscriptProcessor to filter interim transcriptions
    # while still logging them for debugging
    user_processor = transcript.user()
    original_process_frame = user_processor.process_frame
    
    async def filtered_process_frame(self, frame, direction=None):
        from pipecat.frames.frames import InterimTranscriptionFrame, TranscriptionFrame
        
        if isinstance(frame, InterimTranscriptionFrame):
            # Log interim transcription but don't process for transcript events
            text = getattr(frame, 'text', '')
            user_id = getattr(frame, 'user_id', 'unknown')
            if text:
                logger.debug(f"[TRANSCRIPT-INTERIM] User {user_id}: {text}")
                session_logger.append_transcript("user", text, is_interim=True)
            # Pass through the frame without processing
            await self.push_frame(frame, direction)
            return
        
        # Process final transcriptions normally
        return await original_process_frame(frame, direction)
    
    # Apply the monkey-patch
    user_processor.process_frame = filtered_process_frame.__get__(user_processor, user_processor.__class__)

    pipeline = Pipeline(
        [
            transport.input(),  # Transport user input
            rtvi,  # RTVI processor
            stt,
            transcript.user(),              # Capture user transcripts
            context_aggregator.user(),  # User responses
            llm,  
            tts,  
            transport.output(),  # Transport bot output
            transcript.assistant(),         # Capture assistant transcripts
            context_aggregator.assistant(),  # Assistant spoken responses
        ]
    )

    # Generate a conversation ID for tracking
    conversation_id = str(uuid.uuid4())
    logger.info(f"Conversation ID: {conversation_id}")
    
    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        observers=[RTVIObserver(rtvi)],
        enable_tracing=IS_TRACING_ENABLED,
        conversation_id=conversation_id if IS_TRACING_ENABLED else None,
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info(f"Client connected")
        # Kick off the conversation.
        messages.append({"role": "system", "content": persona_system + "\n\nSay hello and very briefly introduce yourself, and your problem, you are a customer in need, not interested in chatting,."})
        await task.queue_frames([context_aggregator.user().get_context_frame()])

    # Log final transcript updates (both user and assistant) - these are used for coach evaluation
    @transcript.event_handler("on_transcript_update")
    async def on_transcript_update(processor, frame):
        for m in getattr(frame, "messages", []) or []:
            role = m.role
            content = m.content
            
            # Always log raw transcripts as they arrive
            logger.info(f"[TRANSCRIPT-FINAL] {role}: {content}")
            session_logger.append_transcript(role, content, is_interim=False)
            
            # Use aggregator to handle fragmented messages
            turn_pair = conversation_aggregator.add_message(role, content)
            
            if turn_pair:
                # We have a complete turn ready for evaluation
                # turn_pair = (customer_prompt, representative_response)
                customer_prompt, representative_response = turn_pair
                
                logger.info(f"[COACH] Evaluating complete turn {conv_state.turn_index + 1}:")
                logger.info(f"  Customer (assistant): {customer_prompt[:80]}...")
                logger.info(f"  Representative (user): {representative_response[:80]}...")
                
                try:
                    # Ensure coach is running (lazy start on first need)
                    await coach.ensure_started()
                    eval_res = await coach.evaluate_turn(
                        conv_state,
                        customer_prompt=customer_prompt,  # What the customer (assistant) said
                        representative_response=representative_response,  # How the bank rep (user) responded
                    )
                    if eval_res and eval_res.parsed:
                        session_logger.append_coach_turn(
                            conv_state.turn_index,
                            customer_prompt,  # Customer (assistant) message
                            representative_response,  # Bank rep (user) response
                            eval_res.parsed,
                        )
                        logger.info(f"[COACH] Turn {conv_state.turn_index} evaluation saved to {session_logger.per_turn_path}")
                    else:
                        logger.warning(f"[COACH] Turn {conv_state.turn_index} evaluation failed or unparseable")
                except Exception as e:
                    logger.error(f"[COACH] Evaluation error: {e}", exc_info=True)

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info(f"Client disconnected")
        try:
            # Flush any pending turn for evaluation
            final_turn = conversation_aggregator.flush_pending_turn()
            if final_turn:
                customer_prompt, representative_response = final_turn
                logger.info(f"[COACH] Evaluating final turn {conv_state.turn_index + 1}:")
                logger.info(f"  Customer (assistant): {customer_prompt[:80]}...")
                logger.info(f"  Representative (user): {representative_response[:80]}...")
                
                try:
                    await coach.ensure_started()
                    eval_res = await coach.evaluate_turn(
                        conv_state,
                        customer_prompt=customer_prompt,
                        representative_response=representative_response,
                    )
                    if eval_res and eval_res.parsed:
                        session_logger.append_coach_turn(
                            conv_state.turn_index,
                            customer_prompt,
                            representative_response,
                            eval_res.parsed,
                        )
                        logger.info(f"[COACH] Final turn {conv_state.turn_index} evaluation saved")
                except Exception as e:
                    logger.error(f"[COACH] Final evaluation error: {e}", exc_info=True)
            
            # Write transcript snapshot
            tpath = session_logger.snapshot_transcript()
            logger.info(f"[TRANSCRIPT] Snapshot written to {tpath}")
            
            # Generate session assessment
            try:
                logger.info(f"[COACH] Generating session assessment for {session_logger.session_id}")
                transcript = session_logger.get_transcript_for_assessment()
                
                if transcript:
                    await coach.ensure_started()
                    assessment_markdown = await coach.generate_session_assessment(
                        conv_state,
                        transcript
                    )
                    
                    # Write the assessment to markdown file
                    eval_path = session_logger.write_session_eval(assessment_markdown)
                    logger.info(f"[COACH] Session assessment written to {eval_path}")
                else:
                    logger.warning("[COACH] No transcript available for session assessment")
                    
            except Exception as e:
                logger.error(f"[COACH] Session assessment error: {e}", exc_info=True)
                
        finally:
            await task.cancel()

    runner = PipelineRunner(handle_sigint=False)

    try:
        await runner.run(task)
    finally:
        try:
            await coach.stop()
        except Exception:
            pass


async def bot(runner_args: RunnerArguments):
    """Main bot entry point for the bot starter."""

    # Parse scenario from environment or default
    scenario = os.environ.get("SCENARIO", "card")

    transport = SmallWebRTCTransport(
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
        ),
        webrtc_connection=runner_args.webrtc_connection,
    )

    await run_bot(transport, scenario)


if __name__ == "__main__":
    import sys
    parser = argparse.ArgumentParser(
        description=(
            "Client/Server voice bot using Pipecat.\n\n"
            "This app runs a persona-driven customer simulation (Lost Card / Failed Transfer / Account Locked)\n"
            "and a background Gemini coach that scores each assistant turn with structured JSON, writing artifacts\n"
            "to server/.coach/<session_id> (per-turn evaluations, transcript with timestamps, and a final summary).\n\n"
            "Required environment variables: DEEPGRAM_API_KEY, OPENAI_API_KEY, ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, GEMINI_API_KEY.\n"
        ),
        add_help=True,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Scenarios:\n"
            "  --card      Lost Card (Sarah Chen) - Family time pressure, immediate access to funds needed.\n"
            "  --transfer  Failed Transfer (Marcus Williams) - IRS payment stuck, deadline-driven escalation.\n"
            "  --account   Account Locked (Janet Rodriguez) - Payroll blocked, employees awaiting paychecks.\n"
        ),
    )
    parser.add_argument(
        "--card",
        action="store_true",
        help="Use Lost Card scenario (Sarah Chen).",
    )
    parser.add_argument(
        "--transfer",
        action="store_true",
        help="Use Failed Transfer scenario (Marcus Williams).",
    )
    parser.add_argument(
        "--account",
        action="store_true",
        help="Use Account Locked scenario (Janet Rodriguez).",
    )
    args, unknown = parser.parse_known_args()

    scenario = "card"
    if args.transfer:
        scenario = "transfer"
    elif args.account:
        scenario = "account"

    # Expose to the bot entrypoint through environment variable
    os.environ["SCENARIO"] = scenario

    # Validate required envs before starting
    missing = [k for k in REQUIRED_ENV_KEYS if not os.environ.get(k)]
    if missing:
        missing_list = ", ".join(missing)
        logger.error(f"Missing required environment variables: {missing_list}")
        raise SystemExit(2)

    # Load and confirm scenario/persona at boot
    try:
        _repo = PromptsRepository()
        _info = _repo.scenario_info(scenario)
        _system_head = _repo.persona_system_prompt_for_scenario(scenario)[:160].replace("\n", " ")
        logger.info(
            f"Scenario confirmed: {scenario} | Persona: {_info.get('persona')} | Brief: {_info.get('brief')}"
        )
        logger.info(f"Persona system prompt (head): {_system_head}…")
    except Exception as e:
        logger.error(f"Failed to confirm scenario/persona: {e}")
        raise SystemExit(2)

    # Health summary
    logger.info(
        f"Health: starting bot with scenario='{scenario}', transport='SmallWebRTC', env_ok=yes"
    )

    # Ensure downstream runner sees only its own args
    sys.argv = [sys.argv[0]] + unknown

    from pipecat.runner.run import main

    main()
