# Adam — AI Agent Product Architecture

## Product definition

Adam is an autonomous voice-and-messaging agent. A user gives Adam an outcome (for example, reserve a table for two at 8 PM), and Adam plans and executes the required steps through approved tools. It is not just a chat interface.

## Primary user journeys

### 1. Outbound phone task

1. The user submits a task in the dashboard or through NourBot on WhatsApp.
2. Adam extracts the restaurant, date, time, party size, location, and constraints. Missing required details are requested from the user.
3. Adam creates a task record and asks for confirmation before placing the call when the action has an external consequence.
4. The phone adapter starts a call through the configured carrier.
5. A real-time voice session handles speech recognition, turn-taking, response generation, and speech playback.
6. Adam records the outcome: confirmed, alternative offered, unavailable, no answer, failed, or needs human help.
7. Adam reports the result to the user on the originating channel.

### 2. WhatsApp voice-note journey (NourBot)

1. Meta WhatsApp Cloud API sends an inbound webhook event.
2. The webhook is authenticated and deduplicated using the provider message ID.
3. Adam downloads the audio media, transcribes it, and passes the transcript plus conversation context to the agent core.
4. The agent decides whether to answer, ask a clarification, or create an actionable task.
5. Text-to-speech generates the reply. The audio is converted to OGG/Opus for a native WhatsApp voice note.
6. The WhatsApp adapter sends the voice note and stores the provider message ID.

Text messages follow the same agent path without transcription or speech synthesis unless a spoken reply is requested.

## Architecture boundaries

- **Agent core:** intent extraction, planning, tool selection, task state, confirmation policy, and result synthesis.
- **Realtime voice runtime:** low-latency audio streaming, speech recognition, interruption handling, and speech playback during PSTN calls.
- **Phone adapter:** vendor-specific PSTN/SIP call creation, media streaming, call status callbacks, and hangup.
- **WhatsApp adapter:** Meta webhook verification, inbound event normalization, media download, text/audio sending, and delivery status callbacks.
- **Conversation/task storage:** per-user context, task lifecycle, audit trail, and idempotency keys.

Provider-specific code must remain behind the interfaces in integrations/contracts.py.

## Provider strategy for Egypt

- Keep the phone layer provider-neutral. Twilio documents outbound termination to Egyptian local and mobile numbers, but its Egypt pricing page does not list a local Egyptian number as inbound-capable. A verified caller ID can be a possible outbound prototype route; callbacks to that number remain with its normal carrier.
- Before production, verify caller-ID presentation, account approval, call recording rules, carrier routing, and real-time media-stream availability with the selected provider.
- Use the official Meta WhatsApp Business Platform for NourBot messaging and voice notes. Do not confuse WhatsApp voice notes with WhatsApp Business Calling; availability and restrictions differ.

## Safety and reliability requirements

- Tell the called party that they are speaking with an AI assistant when the interaction begins.
- Do not impersonate the user or claim to be human.
- Ask the user to approve consequential actions such as confirming, changing, or cancelling a reservation.
- Never invent a reservation confirmation. A task is confirmed only after the restaurant explicitly confirms it.
- Verify webhook signatures, enforce request-size limits, deduplicate provider events, and keep credentials only in server-side environment variables.
- Store minimal personal data, protect call recordings, and define retention/deletion rules before production.
- Add retry limits, timeouts, human handoff, and clear failure states.

## Delivery phases

1. **Foundation:** provider contracts, task lifecycle, webhook/event model, and tests without requiring paid accounts.
2. **WhatsApp:** Meta Cloud API webhook, audio download, transcription, voice-note generation, and outbound audio delivery.
3. **Phone prototype:** one outbound carrier integration, real-time audio bridge, call status callbacks, and one controlled reservation scenario.
4. **Production:** approved number/caller ID, PostgreSQL migrations, rate limits, monitoring, billing/usage controls, human handoff, and operational policies.

## Current implementation status

The repository currently has authenticated text/audio chat, a basic STT → LLM → TTS pipeline, structured AI task planning, persistent account-scoped task lifecycle APIs, a task-planning dashboard panel, verified Meta webhook challenge/signature handling, inbound text/audio event normalization, durable event persistence with duplicate-delivery protection, and a Meta Cloud API transport adapter for media download, text delivery, and OGG/Opus voice-note delivery. MP3-to-OGG/Opus conversion is included for Docker deployments with FFmpeg. The inbound webhook currently validates and normalizes events but does not yet route them into user accounts or automatically invoke the agent. No live phone carrier or WhatsApp business account is connected yet; therefore no real calls or WhatsApp messages can be placed from this code today.
