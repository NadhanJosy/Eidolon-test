import type { CharacterDraft } from "../types";
import { inputClass, primaryButtonClass } from "../ui";

export function CharacterPanel({
  draft,
  setDraft,
  onSave
}: {
  draft: CharacterDraft;
  setDraft: (value: CharacterDraft) => void;
  onSave: () => void;
}) {
  return (
    <>
      <label className="block text-sm text-zinc-300">
        Name
        <input
          className={inputClass}
          value={draft.name}
          onChange={(event) => setDraft({ ...draft, name: event.target.value })}
        />
      </label>
      <label className="block text-sm text-zinc-300">
        Description
        <textarea
          className={`${inputClass} min-h-20 resize-none`}
          value={draft.description}
          onChange={(event) => setDraft({ ...draft, description: event.target.value })}
        />
      </label>
      <label className="block text-sm text-zinc-300">
        Personality
        <textarea
          className={`${inputClass} min-h-24 resize-none`}
          value={draft.personality_core}
          onChange={(event) => setDraft({ ...draft, personality_core: event.target.value })}
        />
      </label>
      <label className="block text-sm text-zinc-300">
        Speech
        <textarea
          className={`${inputClass} min-h-16 resize-none`}
          value={draft.speech_style}
          onChange={(event) => setDraft({ ...draft, speech_style: event.target.value })}
        />
      </label>
      <button className={primaryButtonClass} onClick={onSave} type="button">
        Save character
      </button>
    </>
  );
}
