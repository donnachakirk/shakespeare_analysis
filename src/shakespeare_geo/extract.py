from __future__ import annotations

import os
from typing import List

import langextract as lx


PROMPT = """
Extract only real-world settlement placenames from the play.

Rules:
- Keep only settlement places: city, town, village, hamlet, municipality.
- Do not extract countries, regions, continents, landmarks, monuments, buildings, organizations, people, or deities.
- Do not extract character names such as Friar John.
- Do not extract deity references such as God.
- Do not extract landmark phrases such as Capel's monument.
- Use exact source spans and preserve appearance order.

For each extraction, include attributes:
- normalized_place: canonical place name
- entity_kind: place | person | deity | organization | other
- place_granularity: city | town | village | hamlet | municipality | country | region | landmark | building | other
- is_real_world: true | false
- should_keep: true | false
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
                        "entity_kind": "place",
                        "place_granularity": "city",
                        "is_real_world": "true",
                        "should_keep": "true",
                    },
                ),
                lx.data.Extraction(
                    extraction_class="place",
                    extraction_text="Mantua",
                    attributes={
                        "normalized_place": "Mantua",
                        "entity_kind": "place",
                        "place_granularity": "city",
                        "is_real_world": "true",
                        "should_keep": "true",
                    },
                ),
            ],
        ),
        lx.data.ExampleData(
            text="Friar John carried letters to Verona.",
            extractions=[
                lx.data.Extraction(
                    extraction_class="place",
                    extraction_text="Verona",
                    attributes={
                        "normalized_place": "Verona",
                        "entity_kind": "place",
                        "place_granularity": "city",
                        "is_real_world": "true",
                        "should_keep": "true",
                    },
                ),
            ],
        ),
        lx.data.ExampleData(
            text="God keep us safe in Mantua.",
            extractions=[
                lx.data.Extraction(
                    extraction_class="place",
                    extraction_text="Mantua",
                    attributes={
                        "normalized_place": "Mantua",
                        "entity_kind": "place",
                        "place_granularity": "city",
                        "is_real_world": "true",
                        "should_keep": "true",
                    },
                ),
            ],
        ),
        lx.data.ExampleData(
            text="He rode from Rome across Italy.",
            extractions=[
                lx.data.Extraction(
                    extraction_class="place",
                    extraction_text="Rome",
                    attributes={
                        "normalized_place": "Rome",
                        "entity_kind": "place",
                        "place_granularity": "city",
                        "is_real_world": "true",
                        "should_keep": "true",
                    },
                ),
            ],
        ),
        lx.data.ExampleData(
            text="Meet me at Capel's monument in Verona.",
            extractions=[
                lx.data.Extraction(
                    extraction_class="place",
                    extraction_text="Verona",
                    attributes={
                        "normalized_place": "Verona",
                        "entity_kind": "place",
                        "place_granularity": "city",
                        "is_real_world": "true",
                        "should_keep": "true",
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
