# Shakespeare Geo

Extract placenames from Shakespeare plays, geocode them, and compute a mention-weighted center of gravity.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Set your OpenAI key:

```bash
export OPENAI_API_KEY="..."
export NOMINATIM_EMAIL="you@yourdomain.com"
```

## Run (Romeo & Juliet)

```bash
python scripts/run_play.py \
  --play-id romeo_juliet \
  --title "Romeo and Juliet" \
  --gutenberg-url "https://www.gutenberg.org/files/1513/1513-0.txt" \
  --user-agent "shakespeare-geo/0.1 (you@yourdomain.com)" \
  --model gpt-4o-mini
```

Outputs:
- `outputs/romeo_juliet_mentions.csv`
- `outputs/romeo_juliet_rejections.csv`
- `outputs/romeo_juliet_places.csv`
- `outputs/romeo_juliet_map.html`

Filtering policy:
- Keep only settlement places (city/town/village/hamlet/municipality-like geocodes).
- Reject countries, regions, landmarks/monuments, character names, and deity mentions.

## Tests

```bash
pip install -e ".[dev]"
python -m pytest -q
```

## Notes
- The pipeline is designed to scale to multiple plays by reusing the same extraction + geocoding workflow.
