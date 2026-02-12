from __future__ import annotations

import os
from typing import List

import langextract as lx


PROMPT = """
Extract all geographic place names mentioned in the play.
- Use the exact text span from the source.
- Only include real-world geographic places (cities, regions, countries, landmarks).
- Exclude people, buildings, organizations, and fictional institutions.
- Return results in order of appearance.

For each extraction, include attributes:
- normalized_place: canonical place name
- place_type: city | region | country | landmark | other
- is_fictional: true | false
""".strip()


def build_examples() -> List[lx.data.ExampleData]:
    return [
        lx.data.ExampleData(
            text="From Verona to Mantua, our course lies northward.",
            extractions=[
                lx.data.Extraction(
                    extraction_class="place",
                    extraction_text="Verona",
                    attributes={
                        "normalized_place": "Verona",
                        "place_type": "city",
                        "is_fictional": "false",
                    },
                ),
                lx.data.Extraction(
                    extraction_class="place",
                    extraction_text="Mantua",
                    attributes={
                        "normalized_place": "Mantua",
                        "place_type": "city",
                        "is_fictional": "false",
                    },
                ),
            ],
        ),
        lx.data.ExampleData(
            text="I have been in Rome and all of Italy besides.",
            extractions=[
                lx.data.Extraction(
                    extraction_class="place",
                    extraction_text="Rome",
                    attributes={
                        "normalized_place": "Rome",
                        "place_type": "city",
                        "is_fictional": "false",
                    },
                ),
                lx.data.Extraction(
                    extraction_class="place",
                    extraction_text="Italy",
                    attributes={
                        "normalized_place": "Italy",
                        "place_type": "country",
                        "is_fictional": "false",
                    },
                ),
            ],
        ),
    ]


def extract_places(text: str, model_id: str) -> list[lx.data.Extraction]:
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("LANGEXTRACT_API_KEY")

    result = lx.extract(
        text_or_documents=text,
        prompt_description=PROMPT,
        examples=build_examples(),
        model_id=model_id,
        api_key=api_key,
        fence_output=True,
        use_schema_constraints=False,
    )

    return list(result.extractions)
