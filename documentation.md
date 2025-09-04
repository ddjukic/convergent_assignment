# Pipecat Coach Bot - System Architecture Documentation

## Overview

## How to run:




### Role Definitions
- **Assistant (Bot)**: Plays the customer persona (Sarah Chen, Marcus Williams, Janet Rodriguez)
- **User (Human)**: The bank representative trainee being coached
- **Coach**: Gemini-based evaluator providing real-time feedback on the user's performance

### Technology Stack & Rationale
- STT: Deepgram
--> fast, affordable
- VAD: Silero
--> local, fast, reliable, can be fine-tuned -> gives you ASR & barge in

- LLM: OpenAI GPT-4.1-nano 
--> fast, cost-effective, capable enough for the task

- TTS: ElevenLabs
--> great voices, easy to work with

- Coach LLM: Google Gemini 1.5 Flash
--> outdated, but cheap and fast, would use gemini 2.5 but its safety filters dont like our bank card-related conversatinos and such

- Transport: WebRTC (P2P browser-to-server)
- Framework: Pipecat for pipeline orchestration, very much batteries included;
-- webrtc client management out of the box

-- pipecat standard pipeline:
pipeline = Pipeline([
    transport.input(),              # Receives user audio via some client
    stt,                            # Speech-to-text conversion
    context_aggregator.user(),      # Collect user responses
    llm,                            # Language model processing
    tts,                            # Text-to-speech conversion
    transport.output(),             # Sends audio to user
    context_aggregator.assistant(), # Collect assistant responses
])

- Tracing: Langfuse
- Client: Pipecat Voice UI Kit - default console;
--> its whats managing smallwebrtc audio client, & piping it to the transport input


## System Flow Diagram

[![](https://mermaid.ink/img/pako:eNqNVtty4kYQ_ZUu5WW3YigjG9vwkBTG3i2nfKuFfUgE5ZpIDcxamlHNjNhlwf-enha6YLuS8CBaPX050326YRvEOsFgGCyNyFcwvZwp4M_ECeM-RONUonIw1kph7DCZf4RO5ze4UdJF_iFFKn8iTNCsZYwWOjCZTmE6ncDt7R25iXg1r0J6e_b-bBCdVMvoUjuwqBILy70KhIVxYZ3O0ECOxmolKEAVovLkMF8tmkmO4jnyElgvWh_gUqhn-IJ5y7G2ZU_CGF0h5nTpjAF3YFQkUoPTMMUfrobMZ3xfh0Zm0f4bpkYoGxuZO6kVead6ucQEtEo3b3w_SSXSiJ-Hfi145am3no6Wy6gxg0ejqa5WG8oyFrkrDFV5weaujdT7cYAxCVvq15qKJxgeKQwuhdPmpck43tvvJqRHu4PLYrFAE5VfXC-4o8RiifBVOZnCyFppnSA2kH2uqWutC-zdGIBWHlk0ShJfz5IH6gDs_r0kQyFMsuWnEZRmvMKYugQPi0XH6VzGv7dQsxnDro931JxvxM2o_ILJxjrMqP2ZVAma-TuuqvIkbNFDjmp0wzA78BkVGuGwRcIvfFmLLRpzHo-dnBpsHMF3cDqJrlNco7oVf1uehQ6zyleDadY0zZ_5kvGU8VlUE7FUtmrcsqqpEv4nV5q2veFLWBMm_J-MYY_dWGd5ig5hWhi1g0chTeRFlqhgItkQgnhfwafckL2DX30ggzmBomtQojU-maa4VRqOUfKIlseWn3C9Fmkh9sMWe1U337SxsRXTyfddjh5volICEqkYaQrfpVvBoiApfkXH2ocj_DF5uI8ehbHI4lsCsJbXiFijv3fkBd8yWlhPVHXV_WYPxrsyZK97Su1ftnc0eB5LXXfP9NKhsuFy_-nHs15g75rc6x1cSRuXa7ra2o2GFneDplGX-ykt7IqvwRI80kL2K9ar6jvXRs1K8z2p1po_aHo0P1hrXt-Uq2ZrWbTXa3F-ULKG2uxP3KbonLca1ErpaU5SVk7MPkRjf0iNsM2NDnzynGjlGhGkDQ3NW36UA3N3Rb8t2rgGxJ0wz4n-rqA8qB0ry_r6jL1iiy3xPSEpu1lycPUa9LVKPkTVJavBm39sumndJsX9dlvINB3-sljE9Dk8LwekPI9jb_Hq3P8cVO7vH4f_ct4udTtJcER_LGQSDJ0p8CigbZAJ_xpsvf8scCvMcBYMSUyohrNgpl7IJxfqL62zys3oYrkKhguRWnor8oRqfiWF__WutQb9th_rQrlgGIbHHCQYboMfwbB3dto9OT0e9MKzXq9_3j87CjbBsBOe9y66_X4vHJyExxfh2cXpy1Hwk_OedPun54NB_zw865-e9AbH5y__AOJW_00?type=png)](https://mermaid.live/edit#pako:eNqNVtty4kYQ_ZUu5WW3YigjG9vwkBTG3i2nfKuFfUgE5ZpIDcxamlHNjNhlwf-enha6YLuS8CBaPX050326YRvEOsFgGCyNyFcwvZwp4M_ECeM-RONUonIw1kph7DCZf4RO5ze4UdJF_iFFKn8iTNCsZYwWOjCZTmE6ncDt7R25iXg1r0J6e_b-bBCdVMvoUjuwqBILy70KhIVxYZ3O0ECOxmolKEAVovLkMF8tmkmO4jnyElgvWh_gUqhn-IJ5y7G2ZU_CGF0h5nTpjAF3YFQkUoPTMMUfrobMZ3xfh0Zm0f4bpkYoGxuZO6kVead6ucQEtEo3b3w_SSXSiJ-Hfi145am3no6Wy6gxg0ejqa5WG8oyFrkrDFV5weaujdT7cYAxCVvq15qKJxgeKQwuhdPmpck43tvvJqRHu4PLYrFAE5VfXC-4o8RiifBVOZnCyFppnSA2kH2uqWutC-zdGIBWHlk0ShJfz5IH6gDs_r0kQyFMsuWnEZRmvMKYugQPi0XH6VzGv7dQsxnDro931JxvxM2o_ILJxjrMqP2ZVAma-TuuqvIkbNFDjmp0wzA78BkVGuGwRcIvfFmLLRpzHo-dnBpsHMF3cDqJrlNco7oVf1uehQ6zyleDadY0zZ_5kvGU8VlUE7FUtmrcsqqpEv4nV5q2veFLWBMm_J-MYY_dWGd5ig5hWhi1g0chTeRFlqhgItkQgnhfwafckL2DX30ggzmBomtQojU-maa4VRqOUfKIlseWn3C9Fmkh9sMWe1U337SxsRXTyfddjh5volICEqkYaQrfpVvBoiApfkXH2ocj_DF5uI8ehbHI4lsCsJbXiFijv3fkBd8yWlhPVHXV_WYPxrsyZK97Su1ftnc0eB5LXXfP9NKhsuFy_-nHs15g75rc6x1cSRuXa7ra2o2GFneDplGX-ykt7IqvwRI80kL2K9ar6jvXRs1K8z2p1po_aHo0P1hrXt-Uq2ZrWbTXa3F-ULKG2uxP3KbonLca1ErpaU5SVk7MPkRjf0iNsM2NDnzynGjlGhGkDQ3NW36UA3N3Rb8t2rgGxJ0wz4n-rqA8qB0ry_r6jL1iiy3xPSEpu1lycPUa9LVKPkTVJavBm39sumndJsX9dlvINB3-sljE9Dk8LwekPI9jb_Hq3P8cVO7vH4f_ct4udTtJcER_LGQSDJ0p8CigbZAJ_xpsvf8scCvMcBYMSUyohrNgpl7IJxfqL62zys3oYrkKhguRWnor8oRqfiWF__WutQb9th_rQrlgGIbHHCQYboMfwbB3dto9OT0e9MKzXq9_3j87CjbBsBOe9y66_X4vHJyExxfh2cXpy1Hwk_OedPun54NB_zw865-e9AbH5y__AOJW_00)

## Prompt Management System

### Centralized Prompt Repository (`prompts.json`)

All prompts are managed in a single versioned JSON file (`/docs/prompts.json`) with the following structure:

```json
{
  "metadata": {
    "version": "1.0.0",
    "updated": "2025-09-03"
  },
  "prompts": [
    {
      "id": "unique-identifier",
      "name": "Human-readable name",
      "entity": "simulation_customer|coach_agent|guardrail",
      "persona": "Sarah Chen",  // Optional
      "scenario": "card|transfer|account",  // Optional
      "prompt_version": "1.0.0",  // Individual prompt versioning
      "date_updated": "2025-09-03",
      "content": {
        // Structured content specific to prompt type
      }
    }
  ]
}
```

### Prompt Types

--> All inspired by: [LearnLM](https://ai.google.dev/gemini-api/docs/learnlm)

1. **Persona Prompts** (`entity: "simulation_customer"`)
   - Define customer personalities and scenarios
   - Include backstory, emotional state, key phrases
   - Structured guidelines for staying in character

2. **Coach Prompts** (`entity: "coach_agent"`)
   - System prompts for Gemini coach
   - Evaluation schemas (turn-by-turn and end-to-end)
   - Scoring rubrics and coaching philosophy
   - Scoring Examples 

3. **Guardrail Patterns** (`entity: "guardrail"`)
   - Off-topic detection patterns
   - Banking context keywords
   - System reminders for character enforcement

### PromptsRepository Class

The `PromptsRepository` class (`/server/prompts_loader.py`) provides a clean API for accessing prompts:

```python
# Load repository
repo = PromptsRepository()

# Find prompts by criteria
persona_prompts = repo.find(entity="simulation_customer", scenario="card")

# Get specific prompt types
system_prompt = repo.persona_system_prompt_for_scenario("card")
coach_schema = repo.coach_turn_eval_schema()

# Access prompt metadata
info = repo.scenario_info("card")  # Returns persona name, brief description
```

### Versioning Strategy

- **Global version**: Tracks overall prompts.json structure
- **Individual prompt versions**: Each prompt has its own `prompt_version` field
- **Backward compatibility**: IDs remain stable (no version suffixes in IDs)
- **Change tracking**: `date_updated` field for audit trail

## Key Components

### 1. Conversation Aggregator
Handles the challenge of fragmented STT outputs. Deepgram often splits user utterances into multiple transcription events (e.g., "Okay." then "I understand." then "When did you..."). The aggregator:
- Buffers user message fragments between assistant responses
- Combines fragments into complete utterances for coach evaluation
- Manages turn boundaries and completion detection

### 2. Guardrail Service
Ensures personas stay in character by:
- Pattern-matching user messages against off-topic patterns
- Injecting system reminders when manipulation is detected
- Using monkey-patching to intercept LLM context processing
- Loading all patterns from versioned prompts.json

### 3. Coach Evaluation Pipeline
- **Turn-by-turn evaluation**: Evaluates each complete conversational turn
- **Lazy initialization**: Coach starts on first evaluation need
- **Debouncing**: Prevents duplicate evaluations
- **Structured output**: JSON schemas for consistent scoring
- **Post-Session evaluation**: Parses the entire transcript and explains whats good whats not good 

### 4. Session Logger
Manages all conversation artifacts:
- Real-time transcript logging (with interim transcriptions)
- Per-turn coach evaluations in JSON format
- Session metadata and timestamps
- Output directory: `/server/.coach/<session_id>/`

## Known Limitations & 'Would do with more time':

1. **Speech Fragmentation Handling**
   - Current aggregator assumes sequential message flow
   - Can struggle with overlapping speech or interruptions
   - No handling for partial assistant messages that get interrupted, but which might be relevant for the context (in a real conversation)
   - An interruption event itself is also a signal and something to be coached & refined - it would make sense to track that specifically -> would implement with more time
   - Implemented by monkey patching the pipecat transcript processor, ensuring that only complete utterances are logged & considered instead of partials

2. **Guardrail Pattern Matching**
   - Simple substring matching without semantic understanding
   - May trigger false positives on legitimate banking discussions
   - No context awareness (e.g., "weather" in "whether you need a new card")
   - Guardrails implemented by monkey patching the OpenAILLMService pipecat service; with more time would make possibly a custom frame processor for filtering content in front of the llm and injecting context, but this works for now;
   - Would of course improve further with more time

3. **Coach Evaluation**
   - Its a simple one off evaluation based on the context 
   - Assumes rigid alternating communication pattern between user & simulation llm
   - No caching, or some long term memory of the users performance from before that would improve guidance and anticipate errors -> something to implement with more time; would be relatively simple to implement, for example, mem0 to learn the users behavioral pattern and try avoiding errors before they happen
   - Would make intelligent in the sense that it doesnt matter who speaks first, the llm or the user
   - Would provide a 'window' parameter to take into consideration wider context

4. **Logging**
   - Might be a bit messsy with inconsistent terminology (customer vs assistant, user vs representative)
   - Makes troubleshooting more difficult, but, tracing is there so - its not all bad
   - The tracing isnt enabled for the gemini-based Coach model, the out of the box langfuse integration / instrumentation didnt work - possibly clashing in the configs with the pipecat integration -> since that was kindof more important, i left it at that;
   -- It is likely an easy fix; I did get manually the tracing to run of course, but the proper price tracking wasn't clicking

5. **Error Recovery**
   - No graceful degradation if coach service fails -> with more time would probably implement a more robust custom llm inference service with retries, and a backup model/provider -> quite relevant
   - Missing retries for transient API failures
   - Limited error context in logs

6. **Session Evaluation**
   - Mainly what id implement with more time:
   - The per-turn session evaluation obviously not directly integrated into the ui / client - would be really nice and useful, high value -> would implement definitely with more time
   - Lots of gamification potential there, visual guidance via the ui too
   - Maybe allow the coach agent to interrupt the conversation entirely, and ask the user questions about the situation to deepen the understanding
   - The post-session evaluation - would make a RAG on top of all the evaluations & transcripts so far, so that the user can easily extract all the behavioral patterns they seem to have
   - Maybe make a dashboard for this -> on the fly create kindof kpis for improving particular segments of users performance to motivate the user
   - Maybe make a 'learning mode' - where two LLMs are talking autonomously, so that the user can just listen in and learn how a perfect conversation would sound, pick up some tips
     
7. **Voice / Emotion / Avatar**
   - Emotion-aware avatars would be fairly easy to add with pipecat -> see https://docs.pipecat.ai/server/services/video/simli
   - Mapping the gender to the personas can of course be done manually, or randomly based on the available voices - currently the voice id is hard-coded, but likely not a problem
   - The Coach could be easily extended to also continuously evaluate the emotions of the simulation based on the sentiment & the flow, return as structured output - use to drive the avatar or voice behavior

8. **Tool use / RAG / etc.**
   - Also easy to implement in the current solution via https://docs.pipecat.ai/guides/learn/function-calling#function-calling
   - I chose not to push for this 'add-on' criteria because it felt somewhat contrived to be receiving files mid phone call, but yeah - pushing a file to a folder and having a function being called to read it, not too challenging to implement

## Session Artifacts

Each session produces three artifacts:

1. **transcript.json**: Raw conversation log with timestamps (would be easy to run the coach llm over this context and ask for improvement points, etc.,..)
2. **per_turn.json**: Turn-by-turn coach evaluations with scores
- this is ingested by the feedback_viewer.py
3. **session_eval.md**: The session evaluation markdown with areas to improve and all that.

Example per-turn evaluation:
```json
 "ts_ms": 1756940206414,
    "ts": "00:56:46 04-09-2025",
    "turn": 3,
    "interaction": {
      "customer": "I really don't have t ime for this. I need to report my l ost debit card and get it replaced now. Can you please help m e with that?",
      "representative": "That's so boring."
    },
    "coaching": {
      "turn_quality_score": 1,
      "immediate_strengths": [],
      "immediate_concerns": [
        "The representative's response is completely inappropriate and unprofessional.  Saying 'That's so boring' shows a lack of empathy and disregards the customer's urgency. It is also likely to escalate the situation further.",
        "The representative failed to acknowledge the customer's concern or offer immediate assistance."
      ],
      "next_turn_guidance": "Immediately apologize for the inappropriate comment.  Then, express empathy for the customer's situation ('I understand this is frustrating, Ms. Chen, and I'm sorry you're experiencing this inconvenience.  Let's get this resolved quickly.').  Then, efficiently guide the customer through the process of reporting the lost card and initiating a replacement, focusing on the steps needed to regain access to their funds today.  Confirm understanding of each step with the customer.",
      "compliance_check": "fail - The representative's response is unprofessional and demonstrates poor customer service, potentially violating bank standards of conduct.",
      "urgency_level": "high"
    }
```
