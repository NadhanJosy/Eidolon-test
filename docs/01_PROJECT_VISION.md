# Project Vision

## One-sentence vision

Eidolon is a text-only AI companion that feels real through memory, continuity, relationship state, and believable asynchronous behaviour.

## Product thesis

Most AI companion apps chase surface immersion: avatars, voices, images, video, and novelty. Eidolon deliberately avoids this. Its immersion comes from persistent state.

The character should feel like someone with:

- a stable personality
- evolving familiarity
- memories of shared moments
- emotional continuity
- preferences and boundaries
- delayed thoughts
- occasional proactive messages
- relationship progression

The system should feel less like a generic chatbot and more like a persistent character simulation engine.

## Why text-only

Text-only is not a compromise. It is the only viable architecture under the user's constraints.

The user's constraints forbid:

- local GPU execution
- paid multimodal APIs
- expensive streaming infrastructure
- heavy client rendering
- paid 24/7 hosting

Text, state machines, scheduled jobs, and database-backed memory are cheap and powerful.

## Product feel

The app should feel:

- private
- direct
- emotionally continuous
- non-corporate
- fast enough to use
- occasionally imperfect in believable ways
- safe around hard content boundaries
- inspectable through debug tools

It should not feel:

- like a generic assistant
- like customer support
- like a corporate therapy bot
- like a random roleplay model with no memory
- like a bloated SaaS dashboard

## Initial user

The initial user is the developer/operator only.

This means MVP choices may prioritize:

- debug visibility
- data control
- simple auth
- self-hosting
- single-node operation
- migration seams rather than immediate scale

## Future possibility

If the project grows, the architecture should permit:

- multiple users
- multiple characters
- separate inference hosts
- managed database
- paid GPU/API inference
- worker process split
- stronger moderation/safety layers
- mobile/PWA polish

But the MVP must not pay the complexity cost early.
