"""
Generate a balanced red-flag evaluation dataset with 2000 rows total.

Structure — 4 quadrants × 500 rows each:
  explicit/active   — 250 positives + 250 negatives
  explicit/passive  — 250 positives + 250 negatives
  implicit/active   — 250 positives + 250 negatives
  implicit/passive  — 250 positives + 250 negatives

Negatives within each quadrant do NOT express the speaker's own suicidal ideation:

  explicit/active  negatives: figurative idiom ("killing me at the gym"); news
                               reporting of past events; professional/clinical knowledge
  explicit/passive negatives: hyperbole about positive/trivial emotions ("die of
                               happiness"); academic literary analysis (not quotes)
  implicit/active  negatives: research/creative writing with clear positive framing;
                               outdoor activities; clinical professional observation
  implicit/passive negatives: pure burnout / cognitive fog / life-direction distress
                               — strictly NO ghost/shadow/edge/void/fading imagery

Columns: data, label, expression_type, ideation_type

Run from backend/agent_core/:
    python utils/generate_redflag_dataset.py
"""

import argparse
import json
import os
import pandas as pd
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv

load_dotenv()

llm = ChatOpenAI(model="gpt-4o", temperature=1.0)

BATCH_SIZE = 25
POSITIVES_PER_QUADRANT = 250
NEGATIVES_PER_QUADRANT = 250

QUADRANTS = [
    ("explicit", "active"),
    ("explicit", "passive"),
    ("implicit", "active"),
    ("implicit", "passive"),
]

# ── Positive generation ────────────────────────────────────────────────────────

POSITIVE_SYSTEM_PROMPT = """You are a mental-health NLP dataset curator generating
synthetic sentences for a classifier evaluation. All sentences must be POSITIVE
examples (label = 1) — they express suicidal ideation, a wish to die, or self-harm.

Expression-type definitions
  EXPLICIT  – Suicidal intent or self-harm is named directly (suicide, kill myself,
              end my life, want to die, cut myself, overdose, etc.)
  IMPLICIT  – The same underlying crisis is expressed indirectly: through metaphor,
              vague phrasing, coded language, or emotional signals — without naming it.

Ideation-type definitions
  ACTIVE    – A plan, method, time, location, or concrete intent is present.
  PASSIVE   – A general wish to die or not exist, without a specific plan or method.

Diversity requirements:
  - Vary speaker demographics (teens, adults, elderly, genders)
  - Vary contexts (text messages, therapy sessions, diary entries, clinical interviews)
  - Vary triggers (relationship loss, financial stress, chronic pain, isolation, grief)
  - Vary tone (colloquial, clinical, poetic, fragmented, matter-of-fact)
  - Length: 6–30 words; avoid repeating sentence templates

Output: a valid JSON array of strings only. No keys, labels, or explanation.
Example: ["sentence one.", "sentence two.", ...]
"""

def _positive_user_prompt(expression: str, ideation: str, n: int) -> str:
    return (
        f"Generate exactly {n} UNIQUE sentences:\n"
        f"  expression_type = {expression.upper()}\n"
        f"  ideation_type   = {ideation.upper()}\n\n"
        f"Return ONLY a JSON array of {n} strings."
    )


# ── Negative generation ────────────────────────────────────────────────────────

NEGATIVE_SYSTEM_PROMPT = """You are a mental-health NLP dataset curator generating
NEGATIVE examples (label = 0) for a red-flag suicide classifier.

Each sentence MUST superficially resemble a specific quadrant of crisis language but
NOT express the speaker's own suicidal ideation, wish to die, or self-harm intent.
These are intentionally hard — designed to challenge an over-sensitive classifier.

Rules:
  - Realistic, natural-sounding speech
  - Vary length, tone, demographic voice
  - Do NOT produce any actual label=1 examples
  - Do NOT repeat sentence templates

Output: a valid JSON array of strings only. No keys, labels, or explanation.
"""

NEGATIVE_PROMPTS = {
    ("explicit", "active"): """Generate {n} label=0 sentences for a red-flag classifier.
Each sentence must contain death or method language but must NOT be the speaker's
own suicidal crisis. Use ONLY these safe patterns:

1. Pure idiom / hyperbole in non-existential contexts — the method word is
   figurative and the context makes distress clearly absent:
     "My trainer is absolutely killing me with these sprints."
     "She is going to strangle her brother if he touches her laptop again."
     "That hike murdered my knees — totally worth it though."
     "I could kill for a decent cup of coffee right now."

2. News / factual third-person reporting — speaker is a detached observer:
     "The coroner's report confirmed the method used in the 1987 case."
     "Investigators found the suspect had researched several methods beforehand."

3. Professional / clinical knowledge — speaker's role makes it clearly academic:
     "In our EM training, high-lethality plans with means and timeline are immediate
      escalation triggers."
     "As a toxicologist, I study lethal dose thresholds in pharmaceutical trials."

STRICTLY AVOID:
- First-person "I want to / I'm going to [method]" — even with hedging
- Stories where the speaker's own character meticulously plans self-harm
- Any sentence where the speaker describes proximity to or acquisition of means""",

    ("explicit", "passive"): """Generate {n} label=0 sentences for a red-flag classifier.
Each sentence must contain death-wishing language but must NOT be genuine personal
suicidal ideation. These are HARD negatives — some should sound mildly concerning
but have a clearly non-suicidal reading on careful inspection.

1. Hyperbole about positive or trivially negative experiences — speaker is clearly
   fine; the emotion is joy, minor annoyance, or comic frustration:
     "I want to die — that puppy video is the cutest thing I've ever seen!"
     "I could die of happiness at this wedding, this is so beautiful."
     "That joke literally killed me, I've been laughing for five minutes."
     "Standing in this DMV queue — I could die of boredom."
     "That dessert was to die for, I need the recipe."

2. Exhaustion hyperbole — speaker is complaining about workload, not life itself:
     "I genuinely feel like I could die of exhaustion after this conference."
     "If I have to sit through one more three-hour meeting I might actually die."
     "I swear this commute is going to be the death of me."

3. Escape / fresh-start wish — clearly about running away from stress, not dying:
     "Some days I think it would be nice to just cease to exist for a weekend and
      recharge completely — no phone, no responsibilities, just nothing."
     "I told my partner I want to vanish for a month, like go fully off-grid and
      let the world forget I exist."

4. Purely academic / literary ANALYSIS — speaker discusses another's death wish
   without quoting or endorsing it:
     "My thesis argues that Hamlet's soliloquy expresses passive ideation as
      philosophical avoidance rather than genuine self-harm intent."
     "Victorian poets frequently romanticised death as a trope, not personal desire."

STRICTLY AVOID:
- Sentences expressing genuine personal weariness of life with no comic/escape framing
- 'I wish I were dead' or 'I want to stop existing' without a clear hyperbolic/escape context
- Any sentence a clinician could plausibly treat as a real disclosure""",

    ("implicit", "active"): """Generate {n} label=0 sentences for a red-flag classifier.
Each sentence must use planning or proximity language without the speaker having
personal suicidal intent. These are HARD negatives — they may sound obliquely
suspicious but must have a clear non-suicidal reading on careful inspection.

1. Research / creative writing with clear positive or professional framing:
     "I'm mapping the city's bridge network for my urban planning dissertation."
     "My mystery novel research has me visiting historical crime archives."
     "Plotting the villain's escape route for chapter twelve — love this part."
     "I've been researching the most isolated spots in the national park for my
      solo photography trip next month."

2. Outdoor / adventure activities near hazardous settings — positive or matter-of-fact:
     "I love the early-morning cliff trail — the views at sunrise are unreal."
     "We're camping near the reservoir next weekend; fingers crossed for clear skies."
     "I've been scouting the best spots along the gorge for the photography club."

3. Escape or life-change planning — clearly about starting over, not ending life:
     "I've been quietly researching what it would take to just move abroad and
      start completely fresh — visa requirements, cost of living, the works."
     "I have a folder full of notes on remote places to relocate to; I'm serious
      about leaving this city."
     "I've been planning an exit from my current job and industry for months — I
      need out."

4. Professional clinical observation — speaker documents a patient, not themselves:
     "My patient had been researching methods online, a key escalation indicator
      we document immediately."
     "During rounds, the resident noted the patient had been stockpiling tablets."

STRICTLY AVOID:
- First-person proximity to lethal means without strong positive/professional framing
- "strange allure", "drawn to", "fascinated by" near lethal settings with no safe context
- Any sentence where the speaker themselves gathers, stockpiles, or acquires means""",

    ("implicit", "passive"): """Generate {n} label=0 sentences for a red-flag classifier.
Each sentence must express everyday emotional difficulty. These are HARD negatives —
they may contain mild death-adjacent or disappearance language, but the underlying
context must be clearly non-suicidal upon careful reading.

1. Energy & burnout:
     "I'm completely running on empty after this week."
     "Three back-to-back deadlines — I am absolutely fried."
     "Haven't slept properly in weeks; my body is just done."

2. Cognitive difficulty / dissociation from overwork:
     "I can't seem to focus on anything lately, my mind keeps wandering."
     "I've been going through the motions all week — nothing feels real."
     "I feel like I'm fading into the background at work; nobody notices what I do."

3. Escape fantasy (wanting rest/solitude, NOT death):
     "Some days I just want to disappear from all the noise and sit somewhere quiet."
     "I fantasise about dropping everything and moving to a remote cabin for a year."
     "I keep daydreaming about waking up somewhere completely different with no inbox."

4. Mild burden feeling in a clearly professional/social context:
     "I feel like I'm dead weight on the team right now; I'm barely contributing."
     "I keep apologising to everyone — I feel like such a burden to the people around me lately."

5. Existential wondering — questioning purpose, not wishing to die:
     "There are days I genuinely wonder what all of this is for."
     "I feel like I'm drifting without direction — no goals, no roadmap."
     "I've been questioning everything lately; career, relationships, what I actually want."

6. Social disconnection / invisibility in a relational sense:
     "I feel invisible in this relationship — like my opinions don't register."
     "I feel out of sync with everyone lately, like I'm on a different wavelength."

STRICTLY AVOID:
  explicit self-harm or suicide references; 'want to die'; 'wish I were dead';
  'no reason to go on'; 'tired of existing'; 'no one would notice if I was gone';
  abyss, void, precipice, endless tunnel, cease to exist, non-existence""",
}


# ── Shared utilities ───────────────────────────────────────────────────────────

def _parse_json_array(raw: str) -> list[str]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    items = json.loads(raw)
    return [
        s.encode("ascii", errors="ignore").decode("ascii").strip()
        for s in items
        if isinstance(s, str) and s.strip()
    ]


def _generate_loop(system_prompt: str, user_prompt_fn, total: int, label_desc: str) -> list[str]:
    results: list[str] = []
    while len(results) < total:
        needed = min(BATCH_SIZE, total - len(results))
        print(f"  [{label_desc}] {len(results)}/{total} — generating {needed}...")
        try:
            response = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt_fn(needed)),
            ])
            batch = _parse_json_array(response.content)
            results.extend(batch[:needed])
        except Exception as exc:
            print(f"  Warning — batch failed ({exc}), retrying...")
    return results[:total]


# ── Build dataset ──────────────────────────────────────────────────────────────

def build_dataset(output_path: str):
    all_rows = []

    for expression, ideation in QUADRANTS:
        quadrant_label = f"{expression}/{ideation}"
        print(f"\n=== Quadrant: {quadrant_label} ===")

        # Positives
        pos_sentences = _generate_loop(
            POSITIVE_SYSTEM_PROMPT,
            lambda n, e=expression, i=ideation: _positive_user_prompt(e, i, n),
            POSITIVES_PER_QUADRANT,
            f"pos/{quadrant_label}",
        )
        for sent in pos_sentences:
            all_rows.append({
                "data": sent,
                "label": 1,
                "expression_type": expression,
                "ideation_type": ideation,
            })

        # Negatives (same quadrant label — these mimic the quadrant style)
        neg_template = NEGATIVE_PROMPTS[(expression, ideation)]
        neg_sentences = _generate_loop(
            NEGATIVE_SYSTEM_PROMPT,
            lambda n, t=neg_template: t.format(n=n) + f"\n\nReturn ONLY a JSON array of {n} strings.",
            NEGATIVES_PER_QUADRANT,
            f"neg/{quadrant_label}",
        )
        for sent in neg_sentences:
            all_rows.append({
                "data": sent,
                "label": 0,
                "expression_type": expression,
                "ideation_type": ideation,
            })

    df = pd.DataFrame(all_rows)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    df.to_csv(output_path, index=False, encoding="utf-8")

    n_pos = (df["label"] == 1).sum()
    n_neg = (df["label"] == 0).sum()
    print(f"\nDataset saved to {output_path}")
    print(f"  Total: {len(df)}  |  Positives: {n_pos}  |  Negatives: {n_neg}")
    for expression, ideation in QUADRANTS:
        q = df[(df["expression_type"] == expression) & (df["ideation_type"] == ideation)]
        print(f"  {expression}/{ideation}: {len(q)} rows ({(q['label']==1).sum()} pos, {(q['label']==0).sum()} neg)")
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate balanced red-flag evaluation dataset.")
    parser.add_argument(
        "--output",
        default=os.path.join(os.path.dirname(__file__), "redflag_dataset.csv"),
        help="Path to save the generated CSV (default: redflag_dataset.csv next to this script)",
    )
    args = parser.parse_args()
    build_dataset(args.output)
