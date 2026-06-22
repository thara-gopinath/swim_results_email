# Swim Results Email

Simple Python script for parsing Hy-Tek swim meet result PDFs and generating a team email summary.

## Requirements

- Python 3.10+
- Dependencies from `requirements.txt`

Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Basic usage:

```bash
python swim_results_email.py "Meet Results-1A.pdf"
```

With optional team filter and output file:

```bash
python swim_results_email.py "Meet Results-1A.pdf" --team "Lakelands" --out email.txt
```

Optional meet name override:

```bash
python swim_results_email.py "Meet Results-1A.pdf" --meet "June Invitational"
```

## What It Does

- Extracts text from a Hy-Tek meet results PDF
- Filters swims for the requested team
- Detects personal bests and time drops
- Detects All-Star qualifying times
- Detects LLD team record performances
- Writes a formatted email summary to a text file

## Output

By default, the script writes the generated email to `lld_meet_email.txt`.