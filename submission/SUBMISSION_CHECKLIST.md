# Submission checklist — Agent Experience Hackathon: Strands Decider

Deadline: **October 23**. Requirements taken from the official rules.

## Required to qualify

- [ ] **Agent that uses Strands Decider 2B** for at least one meaningful
      decision, **paired with Amazon Bedrock**.
      → Done in code: Decider picks the branch, Bedrock narrates.
      → **Your action**: run with the real Decider server + real Bedrock at least
        to record the video.
- [ ] **Article on Builder Center** describing the agent, what it does and the
      decision handed to Decider 2B.
      → Final text in `submission/ARTICLE_FINAL_EN.md` (fill in the markers).
- [ ] **Public repository** with the code and **at least one reusable decision
      pattern**.
      → Pattern in `decision_patterns/`. Repo: https://github.com/LucioD3v/ChronosDecider
- [ ] **Public demo video under 3 minutes** showing the agent and the Decider 2B
      decision working.
      → Script in `submission/VIDEO_SCRIPT.md`.
- [ ] **One declared decision pattern**: Tool selection.
- [ ] **Original agent**, not published before.

## Tags (both, before the deadline)

- [ ] `#strands-decider-2b`
- [ ] `#tool-selection`

## Recommended (adds to the rubric)

- [ ] Measure and report the latency/cost of moving the decision off the LLM
      (bonus in "Effective use of Decider 2B").
- [ ] Screenshots of the telemetry panel in the article.

## Rubric (to focus effort)

- Creativity and cool factor — 30%
- Effective use of Decider 2B (incl. reusable pattern quality) — 30%
- Communication quality (article + video) — 25%
- Originality — 15%
