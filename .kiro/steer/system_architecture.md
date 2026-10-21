# ChronosDecider Technical Architecture & Rules

## Core Objective
Engine for real-time RPG narrative state routing using Strands Decider 2B.
Latency Target: < 100ms per evaluation.

## Strict Rules
1. Every input must be routed via Strands Decider 2B for intent classification and decision mapping.
2. The model response MUST return a valid JSON object with `action_type`, `target_branch`, and `confidence_score` (0.0 to 1.0).
3. Fallback Trigger (Human-in-the-Loop): If `confidence_score <= 0.70`, set `trigger_fallback: true` and generate a clarification prompt for the user.
4. Telemetry: Record execution timestamp, model latency in milliseconds, and confidence score for every evaluation.