# Swim Results Email

Simple Python script for parsing Hy-Tek swim meet result PDFs and generating a
team highlights email for the Lakelands Lionfish.

## Requirements

- Python 3.10+
- Dependencies from `requirements.txt`

Install:

```bash
pip install -r requirements.txt
```

## Usage

Basic usage:

```bash
python swim_results_email.py "Meet Results-1A.pdf"
```

Optional flags:

```bash
python swim_results_email.py "Meet Results-1A.pdf" \
    --team "Lakelands" \
    --meet "June Invitational" \
    --out my_email.html \
    --no-first-times
```

### Options

| Flag | Default | Description |
| --- | --- | --- |
| `pdf` | *(required)* | Path to the Hy-Tek meet results PDF. |
| `--team` | `Lakelands` | Substring used to filter swims to your team. |
| `--meet` | *(auto)* | Meet name for the email subject. If omitted, it is extracted from the PDF header (falling back to the PDF filename). |
| `--out` | `lld_meet_email.html` | Output path. Any extension you pass is replaced with `.html`. |
| `--first-times` / `--no-first-times` | `--first-times` | Include or hide the first-time swims (NT seed) section. |

## What It Does

- Extracts text from a Hy-Tek meet results PDF (`pdfplumber`).
- Filters individual (non-relay) swims for the requested team.
- Detects and highlights:
    - **Personal bests** and the time drop in seconds
    - **All-Star** qualifying times (`ALL*` marker or time at/under the printed cut)
    - **LLD team records** (Hy-Tek `L` flag / time at/under the printed `LLD Team:` record)
    - **First-time swims** (seed time of `NT`)
- Randomly rotates the section headings so weekly emails feel fresh.

## Output

The script writes a single HTML file, ready to paste into Gmail or SwimTopia:

- Default: `lld_meet_email.html`
- Custom: pass `--out some_name.html` (or any extension — it will be replaced with `.html`).

Console output shows a summary of counts (results parsed, PBs, All-Star times,
team records, first-time swims) and the path of the HTML file written.
