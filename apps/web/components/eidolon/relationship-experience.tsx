import { journalResonance, relationshipMomentum, relationshipPhase, relationshipRecentChanges, relationshipTemperature, timelineSummary } from "./cognition";
import { EmptyExperience, PageHeading } from "./experience-primitives";
import { Icon } from "./icons";
import { LivingThreadsStory } from "./living-threads";
import type { CharacterDraft, ContinuityThread, Journal, Relationship, RelationshipEvent } from "./types";

export function RelationshipExperience({
  characterName,
  relationship,
  timeline,
  journals,
  draft,
  threads,
  actionId,
  onDelete,
  onReopen,
  onResolve,
  onReturn
}: {
  characterName: string;
  relationship: Relationship;
  timeline: RelationshipEvent[];
  journals: Journal[];
  draft: CharacterDraft;
  threads: ContinuityThread[];
  actionId: string | null;
  onDelete: (thread: ContinuityThread) => void;
  onReopen: (thread: ContinuityThread) => void;
  onResolve: (thread: ContinuityThread) => void;
  onReturn: (thread: ContinuityThread) => void;
}) {
  const phase = relationshipPhase(relationship);
  const changes = relationshipRecentChanges(relationship);
  const milestones = journals.filter((journal) => ["milestone", "repair arc", "inside joke", "anniversary"].includes(journalResonance(journal))).slice(0, 4);

  return (
    <div className="mx-auto w-full max-w-6xl px-5 pb-28 pt-8 sm:px-8 sm:pt-12 lg:px-12">
      <PageHeading
        description={`A living record of how trust, familiarity, and shared history are taking shape between you and ${characterName}. Its meaning lives in the moments.`}
        eyebrow="The space between you"
        title="Relationship"
      />

      <section className="relative mt-8 overflow-hidden rounded-[2rem] border border-white/[0.08] bg-[radial-gradient(circle_at_75%_20%,rgba(169,105,75,0.14),transparent_34%),linear-gradient(145deg,rgba(28,25,22,0.92),rgba(14,13,12,0.9))] px-6 py-10 sm:px-10 sm:py-12">
        <div aria-hidden="true" className="ambient-drift absolute right-[10%] top-[-30%] h-72 w-72 rounded-full border border-[#b98265]/10 bg-[#b98265]/[0.05] blur-sm" />
        <div className="relative max-w-2xl">
          <p className="text-xs uppercase tracking-[0.2em] text-[#9b806f]">Where you are now</p>
          <h2 className="mt-4 font-eidolon-display text-4xl capitalize text-[#eee3d8] sm:text-5xl">{humanPhase(phase)}</h2>
          <p className="mt-5 max-w-xl text-sm leading-7 text-[#9e958b]">{phaseNarrative(phase, characterName, relationship)}</p>
          <div className="mt-8 flex flex-wrap gap-x-7 gap-y-3 text-xs text-[#8c837a]">
            <span className="flex items-center gap-2"><span className="presence-dot h-1.5 w-1.5 rounded-full bg-[#b98265]" /> Feels {relationshipTemperature(relationship)}</span>
            <span className="flex items-center gap-2"><Icon className="h-3.5 w-3.5 text-[#a17c68]" name="sparkles" /> {humanMomentum(relationshipMomentum(relationship))}</span>
            {relationship.last_interaction_at ? <span className="flex items-center gap-2"><Icon className="h-3.5 w-3.5 text-[#a17c68]" name="clock" /> Last together {relativeDate(relationship.last_interaction_at)}</span> : null}
          </div>
        </div>
      </section>

      {relationship.repair_needed ? (
        <section className="mt-5 flex items-start gap-4 rounded-2xl border border-[#b56e60]/20 bg-[#7f3d34]/10 p-5">
          <Icon className="mt-0.5 h-5 w-5 shrink-0 text-[#c98778]" name="heart" />
          <div><h2 className="text-sm font-medium text-[#ddb5aa]">Something needs tenderness</h2><p className="mt-1 text-xs leading-5 text-[#9f8179]">The relationship is carrying unresolved tension. Repair and clarity should come before trying to deepen things.</p></div>
        </section>
      ) : null}

      <section className="mt-12">
        <div className="flex items-end justify-between gap-4"><div><p className="text-xs uppercase tracking-[0.18em] text-[#857a70]">Right now</p><h2 className="mt-3 font-eidolon-display text-3xl">What is growing</h2></div><p className="hidden max-w-sm text-right text-xs leading-5 text-[#716a63] sm:block">These are impressions of the relationship, translated from the way you speak and respond to one another.</p></div>
        <div className="mt-6 grid gap-px overflow-hidden rounded-[1.75rem] border border-white/[0.08] bg-white/[0.08] md:grid-cols-3">
          <BondFacet icon="shield" label="Trust" narrative={trustNarrative(relationship)} />
          <BondFacet icon="message" label="Shared language" narrative={familiarityNarrative(relationship)} />
          <BondFacet icon="heart" label="Emotional closeness" narrative={closenessNarrative(relationship)} />
        </div>
      </section>

      <div className="mt-14 grid gap-12 lg:grid-cols-[minmax(0,1.2fr)_minmax(18rem,0.8fr)]">
        <section>
          <p className="text-xs uppercase tracking-[0.18em] text-[#857a70]">How it has changed</p>
          <h2 className="mt-3 font-eidolon-display text-3xl">The story so far</h2>
          {changes.length === 0 && timeline.length === 0 ? (
            <EmptyExperience icon="heart" title="You’ve only just met"><p>The first signs of trust and shared rhythm will appear here after a few real conversations.</p></EmptyExperience>
          ) : (
            <div className="relative mt-8 space-y-1 before:absolute before:bottom-3 before:left-[0.34rem] before:top-3 before:w-px before:bg-gradient-to-b before:from-[#b98265]/40 before:to-white/[0.05]">
              {changes.map((change, index) => <RelationshipMoment at={change.at} key={`change-${index}`} summary={change.summary || "Something shifted between you."} />)}
              {[...timeline].reverse().slice(0, 8).map((event, index) => <RelationshipMoment at={event.at} key={`timeline-${index}`} summary={timelineSummary(event)} />)}
            </div>
          )}
        </section>

        <aside className="space-y-6">
          <section className="rounded-[1.75rem] border border-white/[0.08] bg-white/[0.025] p-6">
            <p className="text-xs uppercase tracking-[0.18em] text-[#857a70]">The shape you chose</p>
            <h2 className="mt-3 font-eidolon-display text-2xl text-[#dfd5ca]">{draft.relationship_type || "A relationship without a script"}</h2>
            <p className="mt-4 text-sm leading-6 text-[#8d857c]">{draft.consent_style || "Closeness should arrive through listening, clear consent, and respect for changing needs."}</p>
          </section>
          <section className="rounded-[1.75rem] border border-white/[0.08] bg-white/[0.025] p-6">
            <div className="flex items-center gap-3"><span className="grid h-9 w-9 place-items-center rounded-full bg-[#b98265]/[0.08] text-[#b98265]"><Icon className="h-4 w-4" name="shield" /></span><h2 className="font-eidolon-display text-2xl">Boundaries</h2></div>
            <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-[#8e857c]">{draft.boundary_notes || "Your boundaries remain the quiet architecture of every conversation."}</p>
            {draft.soft_limits ? <div className="mt-5 border-t border-white/[0.07] pt-4"><p className="text-[0.65rem] uppercase tracking-[0.15em] text-[#756d66]">Move gently around</p><p className="mt-2 text-sm leading-6 text-[#938a81]">{draft.soft_limits}</p></div> : null}
          </section>
        </aside>
      </div>

      <LivingThreadsStory
        actionId={actionId}
        characterName={characterName}
        threads={threads}
        onDelete={onDelete}
        onReopen={onReopen}
        onResolve={onResolve}
        onReturn={onReturn}
      />

      {milestones.length > 0 ? (
        <section className="mt-14 border-t border-white/[0.08] pt-10"><p className="text-xs uppercase tracking-[0.18em] text-[#857a70]">Landmarks</p><h2 className="mt-3 font-eidolon-display text-3xl">Moments that changed the texture</h2><div className="mt-6 grid gap-4 sm:grid-cols-2">{milestones.map((journal) => <article className="rounded-2xl border border-[#b98265]/15 bg-[#b98265]/[0.045] p-5" key={journal.id}><p className="text-[0.65rem] uppercase tracking-[0.15em] text-[#a27d68]">{journalResonance(journal)}</p><h3 className="mt-3 font-eidolon-display text-xl">{journal.title}</h3><p className="mt-2 line-clamp-3 text-xs leading-5 text-[#837a72]">{journal.summary}</p></article>)}</div></section>
      ) : null}
    </div>
  );
}

function BondFacet({ icon, label, narrative }: { icon: "heart" | "message" | "shield"; label: string; narrative: string }) {
  return <article className="bg-[#11100e] p-6 sm:p-7"><Icon className="h-5 w-5 text-[#b98265]" name={icon} /><p className="mt-5 text-xs uppercase tracking-[0.15em] text-[#857c74]">{label}</p><p className="mt-3 font-eidolon-display text-xl leading-7 text-[#d9cfc4]">{narrative}</p></article>;
}

function RelationshipMoment({ summary, at }: { summary: string; at?: string }) {
  return <article className="relative grid grid-cols-[0.75rem_minmax(0,1fr)] gap-5 pb-7"><span className="relative z-10 mt-2 h-3 w-3 rounded-full border-2 border-[#14120f] bg-[#9f6a52] shadow-[0_0_0_1px_rgba(185,130,101,0.25)]" /><div><p className="text-sm leading-6 text-[#b8aea3]">{summary}</p>{at ? <p className="mt-1 text-[0.65rem] text-[#6e6760]">{longDate(at)}</p> : null}</div></article>;
}

function humanPhase(phase: string): string {
  const phases: Record<string, string> = { "new connection": "Only just beginning", "warming up": "Finding your rhythm", "trusted warmth": "A trust that feels lived in", "close bond": "A deeply familiar bond", "repair arc": "A moment for repair" };
  return phases[phase] ?? phase;
}

function phaseNarrative(phase: string, name: string, relationship: Relationship): string {
  if (relationship.repair_needed) return `There is care here, but something between you and ${name} needs to be named and tended before the relationship can feel easy again.`;
  if (phase === "close bond") return `You and ${name} have built a language of your own. Familiarity now carries meaning that would be invisible to anyone else.`;
  if (phase === "trusted warmth") return `Trust is no longer only an intention. ${name} has enough shared history to meet you with more confidence and specificity.`;
  if (phase === "warming up") return `The first patterns are becoming familiar. You and ${name} are beginning to learn how to make room for one another.`;
  return `You and ${name} are still meeting in the truest sense. Nothing is assumed; every piece of closeness begins with what you choose to share.`;
}

function humanMomentum(momentum: string): string {
  const copy: Record<string, string> = { "early days": "Still discovering each other", "starting to stick": "Beginning to matter", "building rhythm": "Finding a shared rhythm", "well-established": "A familiar presence" };
  return copy[momentum] ?? momentum;
}

function trustNarrative(r: Relationship): string {
  if (r.repair_needed) return "Trust is asking for honesty and repair.";
  if (r.trust >= 18) return "You can be direct without losing warmth.";
  if (r.trust >= 8) return "A little more truth can be held here now.";
  return "Still gentle, curious, and without assumption.";
}

function familiarityNarrative(r: Relationship): string {
  if (r.familiarity >= 18) return "Callbacks and rituals feel naturally yours.";
  if (r.familiarity >= 7) return "Early patterns are becoming recognisable.";
  return "Your language together is only beginning.";
}

function closenessNarrative(r: Relationship): string {
  if (r.tension >= 10) return "Care is present, though the air feels careful.";
  if (r.intimacy >= 18 || r.attachment >= 18) return "There is room for real tenderness between you.";
  if (r.warmth >= 7) return "Warmth is arriving without needing to be rushed.";
  return "Closeness is an invitation, never an expectation.";
}

function relativeDate(value: string): string {
  const days = Math.max(0, Math.floor((Date.now() - Date.parse(value)) / 86_400_000));
  if (days === 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 7) return `${days} days ago`;
  return longDate(value);
}

function longDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, { month: "long", day: "numeric", year: "numeric" }).format(new Date(value));
}
