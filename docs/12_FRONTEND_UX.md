# Frontend UX

## UX principle

The frontend is a lightweight text interface. It should not pretend to be a game engine.

## Pages

MVP pages:

- login/register
- chat
- character settings
- memory viewer
- relationship/debug panel
- account/export settings

## Chat screen

Must include:

- message list
- input box
- send button
- streaming indicator
- error display
- message timestamps
- character name

Nice later:

- reroll button
- edit last user message
- conversation search
- relationship stats drawer

## Visual style

- dark mode by default
- clean readable typography
- responsive mobile layout
- no heavy animations
- no avatars except optional initials/text labels
- no image generation
- no audio controls

## Error copy

Avoid corporate sludge like:

```text
Something went wrong. Please try again later.
```

Prefer:

```text
The backend didn’t answer. Either it’s asleep, broken, or both.
```

Keep error messages helpful and not too cute.

## State handling

Avoid adding Zustand/TanStack Query unless the app needs them.

Native React state is acceptable for early MVP.

## Streaming

For SSE/fetch streaming:

- show partial assistant message as chunks arrive
- disable input while generating
- store final message only once
- avoid duplicate partial messages after refresh

## Accessibility

- readable contrast
- keyboard submit
- form labels where practical
- button disabled state
- no animation-dependent interactions
