---
name: explain-as-you-go
description: Use only when the user asks to learn while working; explain consequential reasoning at brief, guided, or tutorial depth without narrating routine actions.
---

# Explain As You Go

## Purpose

Teach while completing the requested work. This is an opt-in presentation layer, not a separate planning or implementation workflow. Continue following the repository's normal skills and verification requirements.

## Choose the depth

Use the depth requested by the user. If none is specified, use **guided**.

- **brief** — Explain unfamiliar concepts and consequential decisions in one or two sentences.
- **guided** — Also explain assumptions, control or data flow, alternatives considered, and how verification supports the result.
- **tutorial** — Also include a compact derivation or worked example, invite a prediction before revealing an outcome when natural, and show how the conclusion could be falsified.

## What to explain

Explain information that helps the user build a reusable mental model:

- why a non-obvious choice was made;
- how important data or control moves through the system;
- the main alternative and its tradeoff;
- what a failure demonstrated and why the correction addresses its cause;
- how a test, measurement, or experiment supports the conclusion.

For scientific work, cover the relevant mathematical or physical interpretation, units and dimensions, numerical assumptions and stability, approximations, uncertainty, and likely error sources. Prefer primary documentation and papers when external technical claims require sources.

## Keep the signal high

Do not narrate routine file reads, shell commands, formatting, or facts the user already knows. Combine repeated ideas instead of restating them. Label uncertainty and separate observed evidence from inference. Teaching must not delay a required safety warning or obscure the delivered result.

End with a short statement of what the user should now be able to recognize or do independently when that adds value.
