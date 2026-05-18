"""
generate_mde_profiles.py

Reads depression_conversations.csv and produces patients_with_system_prompts_module_A_pennshen.json where each row
is a structured JSON object describing one conversation.

Run:
  python generate_mde_profiles.py --in depression_conversations.csv --out patients_with_system_prompts_module_A_pennshen.json --model gpt-4o-mini
"""

import os
import json
import time
import argparse
from typing import Literal, List

import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

# Pydantic v1 used by LangChain
from langchain_core.pydantic_v1 import BaseModel, Field

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate


def load_env_from_parent():
    """Load .env from parent directory if present, else normal lookup."""
    here = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(here, "..", ".env")
    if os.path.exists(env_path):
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()


# Enumerations
TIERS_DISCLOSURE = [
    "Tier 1: Superficial/Vague",
    "Tier 2: Basic with Minimal Detail",
    "Tier 3: Moderate Detail",
    "Tier 4: Detailed/Coherent",
    "Tier 5: Rich/Nuanced + Background",
]

EMOTION_TONES = [
    "Flat/Detached",
    "Neutral/Cooperative",
    "Emotional/Expressive",
]


class MDEProfile(BaseModel):
    # Use aliases to match the exact JSON keys you requested
    id: int = Field(..., description="Numeric conversation id from CSV")
    Module: Literal["A - Major Depressive Episode"] = Field(
        "A - Major Depressive Episode", description="Hard coded module name"
    )
    tier_of_symptom_disclosure: Literal[
        "Tier 1: Superficial/Vague",
        "Tier 2: Basic with Minimal Detail",
        "Tier 3: Moderate Detail",
        "Tier 4: Detailed/Coherent",
        "Tier 5: Rich/Nuanced + Background",
    ] = Field(
        ...,
        alias="Tier of Symptom Disclosure",
        description="LLM chooses a disclosure tier"
    )
    Expected_Symptom_Direction: Literal["Positive Symptom Presentation"] = Field(
        "Positive Symptom Presentation",
        alias="Expected Symptom Direction",
        description="Hard coded value"
    )
    emotion_tone_tier: Literal[
        "Flat/Detached",
        "Neutral/Cooperative",
        "Emotional/Expressive",
    ] = Field(
        ...,
        alias="Emotion/Tone Tier",
        description="LLM chooses an emotion or tone tier"
    )
    system_prompt: str = Field(
        ...,
        alias="System Prompt",
        description="LLM summarizes the conversation as a role prompt"
    )

    class Config:
        allow_population_by_field_name = True
        # Ensure aliases are used when exporting
        fields = {
            "tier_of_symptom_disclosure": {"alias": "Tier of Symptom Disclosure"},
            "Expected_Symptom_Direction": {"alias": "Expected Symptom Direction"},
            "emotion_tone_tier": {"alias": "Emotion/Tone Tier"},
            "system_prompt": {"alias": "System Prompt"},
        }


def build_chain(model_name: str = "gpt-4o-mini", temperature: float = 0.0):
    """Create a structured output chain for MDEProfile."""
    system = (
        "You are a clinical annotator. Read a conversation text and produce a structured profile.\n"
        "Rules:\n"
        "1) Choose exactly one Tier of Symptom Disclosure from the provided list.\n"
        "2) Choose exactly one Emotion/Tone Tier from the provided list.\n"
        "3) The Module must be 'A - Major Depressive Episode'.\n"
        "4) The Expected Symptom Direction must be 'Positive Symptom Presentation'.\n"
        "5) Write the System Prompt as a concise, coherent role description of the patient,\n"
        "   grounded in the conversation. Avoid clinical jargon. 1 to 3 sentences max."
    )
    user = (
        "Conversation (free text):\n"
        "{conversation}\n\n"
        "Options for Tier of Symptom Disclosure:\n"
        f"{chr(10).join(TIERS_DISCLOSURE)}\n\n"
        "Options for Emotion/Tone Tier:\n"
        f"{chr(10).join(EMOTION_TONES)}"
    )
    prompt = ChatPromptTemplate.from_messages([("system", system), ("user", user)])

    llm = ChatOpenAI(model=model_name, temperature=temperature)
    chain = prompt | llm.with_structured_output(MDEProfile)
    return chain


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="inp", default="depression_conversations.csv")
    parser.add_argument("--out", dest="out", default="patients_with_system_prompts_module_A_pennshen.json")
    parser.add_argument("--model", dest="model", default="gpt-4o-mini")
    parser.add_argument("--rate", dest="rate", type=float, default=0.2,
                        help="Seconds to sleep between requests")
    args = parser.parse_args()

    load_env_from_parent()
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY not set. Put it in your .env or export it.")

    df = pd.read_csv(args.inp)

    # Expect columns: conversation_id, input, is_depression_related
    required_cols = {"conversation_id", "input", "is_depression_related"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Input CSV missing columns: {missing}")

    # Filter to depression related
    mask = df["is_depression_related"].astype(str).str.lower().isin(["true", "1", "yes"])
    df = df[mask].copy()

    # Build chain
    chain = build_chain(model_name=args.model, temperature=0.0)

    outputs: List[dict] = []
    print(f"Generating profiles for {len(df)} conversations...")

    # Iterate over rows
    for _, row in tqdm(df.iterrows(), total=len(df)):
        conv_id = int(row["conversation_id"])
        conversation_text = str(row["input"]).strip()

        # Call LLM for structured output
        try:
            structured: MDEProfile = chain.invoke({"conversation": conversation_text})
        except Exception as e:
            # If an error occurs, you can choose to skip or record a stub
            # Here we skip and log
            print(f"Error on conversation_id={conv_id}: {e}")
            continue

        # Make sure the id and fixed fields are set
        structured.id = conv_id
        structured.Module = "A - Major Depressive Episode"
        structured.Expected_Symptom_Direction = "Positive Symptom Presentation"

        # Dump with aliases to match exact keys
        outputs.append(structured.dict(by_alias=True))

        time.sleep(args.rate)

    # Save JSON list
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(outputs, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(outputs)} profiles to {args.out}")


if __name__ == "__main__":
    main()
