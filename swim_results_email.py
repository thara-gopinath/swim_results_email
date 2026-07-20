#!/usr/bin/env python3
"""
Simple Hy-Tek swim results parser for LLD/Lakelands Lionfish.

Usage:
  python swim_results_email.py "Meet Results-1A.pdf"
  python swim_results_email.py "Meet Results-1A.pdf" --team "Lakelands" --out email.txt

Requires:
  pip install pdfplumber
"""
from __future__ import annotations

import argparse
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pdfplumber

TIME_RE = r"(?:\d+:)?\d{1,2}\.\d{2}"
TEAM_RE = r"Lakelands Lion.*?ish"


@dataclass
class SwimResult:
    event_no: int
    event_name: str
    swimmer: str
    age: int
    team: str
    seed_time: str
    final_time: str
    all_star_cut: Optional[str]
    lld_record: Optional[str]
    all_star: bool = False
    pb: bool = False
    drop_seconds: Optional[float] = None
    team_record: bool = False
    first_time: bool = False


def clean_text(text: str) -> str:
    # Hy-Tek PDFs sometimes extract the "fi" ligature as weird cid text.
    text = text.replace("(cid:976)", "f")
    text = text.replace("ϐ", "f")
    return text


def time_to_seconds(t: str) -> Optional[float]:
    if not t or t in {"NT", "NS", "SCR"} or t.startswith("DQ"):
        return None
    t = t.replace("ALL*", "").strip()
    if t.startswith("X"):
        t = t[1:]
    # Hy-Tek appends an "L" flag to the time when the swim sets a new team
    # record. Strip it before numeric parsing.
    if t.endswith("L"):
        t = t[:-1]
    if ":" in t:
        mins, secs = t.split(":")
        return int(mins) * 60 + float(secs)
    return float(t)


def seconds_to_time(seconds: float) -> str:
    if seconds >= 60:
        mins = int(seconds // 60)
        secs = seconds - mins * 60
        return f"{mins}:{secs:05.2f}"
    return f"{seconds:.2f}"


def extract_pdf_text(pdf_path: Path) -> str:
    pages: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return clean_text("\n".join(pages))


def extract_meet_name(text: str) -> Optional[str]:
    """Pull the meet name from the header lines of a Hy-Tek results PDF."""
    skip_substrings = ("hy-tek", "meet manager", "page ", "licensed to")
    for raw in text.splitlines()[:25]:
        line = raw.strip()
        if not line:
            continue
        lower = line.lower()
        if any(s in lower for s in skip_substrings):
            continue
        if lower in {"results", "meet results"}:
            continue
        if lower.startswith("event "):
            break
        return line
    return None


def parse_results(pdf_path: Path, team_filter: str = "Lakelands") -> list[SwimResult]:
    text = extract_pdf_text(pdf_path)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    results: list[SwimResult] = []
    current_event_no: Optional[int] = None
    current_event_name: Optional[str] = None
    current_all_star_cut: Optional[str] = None
    current_lld_record: Optional[str] = None

    event_re = re.compile(r"^Event\s+(\d+)\s+(.+)$")
    all_star_re = re.compile(rf"^({TIME_RE})\s+ALL\*$")
    lld_record_re = re.compile(rf"^LLD Team:\s+({TIME_RE})\b")

    # Individual result row. Relay rows are ignored in this first simple version.
    # The final time may carry a trailing "L" flag set by Hy-Tek when the swim
    # is a new team record.
    row_re = re.compile(
        rf"^(?:\*?\d+|---)\s+(.+?)\s+(\d{{1,2}})\s+({TEAM_RE})\s+"
        rf"(NT|X?{TIME_RE})\s+((?:DQ\s+)?X?{TIME_RE}L?|NS|SCR)(?:\s+ALL\*)?(?:\s+\d+)?$"
    )

    for line in lines:
        m = event_re.match(line)
        if m:
            current_event_no = int(m.group(1))
            current_event_name = m.group(2).strip()
            current_all_star_cut = None
            current_lld_record = None
            continue

        m = lld_record_re.match(line)
        if m:
            current_lld_record = m.group(1)
            continue

        m = all_star_re.match(line)
        if m:
            current_all_star_cut = m.group(1)
            continue

        m = row_re.match(line)
        if not m or current_event_no is None or current_event_name is None:
            continue

        swimmer, age, team, seed, final = m.groups()
        if team_filter.lower() not in team.lower():
            continue
        if final in {"NS", "SCR"} or final.startswith("DQ"):
            continue

        # Drop the trailing Hy-Tek team-record flag from the displayed time.
        if final.endswith("L"):
            final = final[:-1]

        seed_sec = time_to_seconds(seed)
        final_sec = time_to_seconds(final)
        all_cut_sec = time_to_seconds(current_all_star_cut or "")
        record_sec = time_to_seconds(current_lld_record or "")

        first_time = seed.strip().upper() == "NT"
        pb = seed_sec is not None and final_sec is not None and final_sec < seed_sec
        drop = (seed_sec - final_sec) if pb else None
        all_star = ("ALL*" in line) or (all_cut_sec is not None and final_sec is not None and final_sec <= all_cut_sec)
        team_record = record_sec is not None and final_sec is not None and final_sec <= record_sec

        results.append(
            SwimResult(
                event_no=current_event_no,
                event_name=current_event_name,
                swimmer=swimmer.strip(),
                age=int(age),
                team=team.strip(),
                seed_time=seed,
                final_time=final,
                all_star_cut=current_all_star_cut,
                lld_record=current_lld_record,
                all_star=all_star,
                pb=pb,
                drop_seconds=drop,
                team_record=team_record,
                first_time=first_time,
            )
        )
    for result in results:
        print(result)
    return results


def bullet(result: SwimResult, include_seed: bool = False) -> str:
    name = result.swimmer.replace(",", ",")
    base = f"- {name} — {result.event_name} — {result.final_time}"
    if include_seed and result.seed_time != "NT":
        base += f" from {result.seed_time}"
    return base

def _html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

# Map of Unicode emoji -> Google notoemoji codepoint hex (matches the URLs
# SwimTopia auto-converts to). By emitting our own <img> at a small inline
# size, we try to defeat SwimTopia's 72px auto-embed.
_EMOJI_CODEPOINTS = {
    "🦁": "1f981",
    "🐟": "1f41f",
    "✨": "2728",
    "💙": "1f499",
    "❤️": "2764_fe0f",
    "🌊": "1f30a",
    "🏆": "1f3c6",
    "🚨": "1f6a8",
    "⭐": "2b50",
    "🚀": "1f680",
}


def _emoji(char: str, size: int = 18) -> str:
    cp = _EMOJI_CODEPOINTS.get(char)
    if cp is None:
        return char
    url = f"https://fonts.gstatic.com/s/e/notoemoji/17.0/{cp}/72.png"
    return (
        f'<img src="{url}" alt="{char}" width="{size}" height="{size}" '
        f'style="vertical-align:-3px;display:inline-block;border:0" />'
    )


# Alternate phrasings for the three highlight sections. One is picked at
# random each time the email is built so the message feels fresh week to week.
_RECORD_HEADINGS = [
    "BIG SHOUTOUT FOR NEW LIONFISH TEAM RECORDS",
    "ROAR FOR OUR NEW LIONFISH TEAM RECORDS",
    "HISTORY MADE — NEW LIONFISH TEAM RECORDS",
    "RECORD BOOKS REWRITTEN BY OUR LIONFISH",
    "FRESH NAMES ON THE LIONFISH RECORD BOARD",
]

_ALL_STAR_HEADINGS = [
    "HUGE CHEER FOR ALL-STAR TIMES",
    "STANDING OVATION FOR ALL-STAR TIMES",
    "SHINING BRIGHT WITH ALL-STAR TIMES",
    "ROAR LOUD FOR ALL-STAR TIMES",
    "ALL-STAR TIMES — LET'S HEAR IT!",
]

_FIRST_TIME_HEADINGS = [
    "WELCOME SPLASHES — FIRST-TIME SWIMS",
    "MAKING A SPLASH FOR THE FIRST TIME",
    "BRAND NEW TIMES ON THE BOARD — FIRST-TIME SWIMS",
    "FIRST-TIME SWIMS — WAY TO GO!",
    "DEBUT SWIMS — FINS UP!",
    "OFFICIAL TIMES FOR THE FIRST TIME — GREAT JOB!",
    "NEW EVENTS CONQUERED — FIRST-TIME SWIMS",
]

_PB_HEADINGS = [
    "LOUDEST HURRAYS FOR PERSONAL BESTS",
    "FINS UP FOR PERSONAL BESTS",
    "CHEER LOUD FOR THESE PERSONAL BESTS",
    "NEW PERSONAL BESTS — WAY TO DROP TIME!",
    "BIG TIME DROPS — PERSONAL BESTS",
    "HARD WORK PAID OFF — NEW PERSONAL BESTS",
    "PROOF THAT PRACTICE WORKS — PERSONAL BESTS",
    "FASTER THAN EVER — PERSONAL BESTS",
    "BREAKING THROUGH — NEW PERSONAL BESTS",
    "EVERY SECOND COUNTS — PERSONAL BESTS",
    "CHASING THE CLOCK AND WINNING — PERSONAL BESTS",
    "RISING TO NEW HEIGHTS — PERSONAL BESTS",
    "GRIT, GUTS, AND GLORY — PERSONAL BESTS",
    "SHATTERING OLD TIMES — PERSONAL BESTS",
    "DREAM BIG, SWIM FAST — PERSONAL BESTS",
    "OUTSWIMMING YESTERDAY'S YOU — PERSONAL BESTS",
    "ONWARD AND FASTER — PERSONAL BESTS",
    "PROGRESS IN THE POOL — PERSONAL BESTS",
    "LEAVING OLD TIMES IN THE WAKE — PERSONAL BESTS",
    "THIS IS WHAT GROWTH LOOKS LIKE — PERSONAL BESTS",
]


def build_email_html(results: list[SwimResult], meet_name: str, include_first_times: bool = True) -> str:
    """HTML version of the email. Uses <p> + <br> blocks so the layout survives
    paste into rich-text editors (Gmail, SwimTopia) that strip <div> wrappers.
    Emojis are emitted as small explicit <img> tags so SwimTopia does not
    auto-convert them into 72px image embeds."""
    pbs = sorted([r for r in results if r.pb], key=lambda r: r.drop_seconds or 0, reverse=True)
    all_stars = sorted([r for r in results if r.all_star], key=lambda r: (r.swimmer, r.event_no))
    records = sorted([r for r in results if r.team_record], key=lambda r: r.event_no)
    first_times = (
        sorted([r for r in results if r.first_time], key=lambda r: (r.swimmer, r.event_no))
        if include_first_times
        else []
    )

    e = _emoji  # short local alias

    parts: list[str] = []
    parts.append(f"<p><b>Subject:</b> {e('🌊')} Meet Highlights – {_html_escape(meet_name)}</p>")
    parts.append("<p>Hi Lionfish families,</p>")
    parts.append(f"<p>Write your weekly message here {e('🦁')}{e('🐟')}{e('✨')}</p>")
    parts.append(f"<p>Huge congratulations to all our swimmers, coaches, timers, officials, and cheering families. Way to go, Lionfish! {e('💙')}{e('❤️')}</p>")

    def swimmer_block_html(swimmer: str, items: list[str]) -> str:
        # Use one <p> per swimmer with <br> between events. Some rich-text
        # editors (e.g. SwimTopia) strip plain <div> wrappers, which collapses
        # every event onto a single line.
        body = f"<b>{_html_escape(swimmer)}</b>"
        for item in items:
            body += f"<br>{item}"
        return f"<p>{body}</p>"

    # Thin grey horizontal rule placed between sections.
    divider = '<hr style="border:0;border-top:1px solid #cccccc;margin:16px 0">'

    if records:
        parts.append(divider)
        parts.append(f"<p><b>{e('🏆')} {random.choice(_RECORD_HEADINGS)}</b></p>")
        by_swimmer: dict[str, list[SwimResult]] = {}
        for r in records:
            by_swimmer.setdefault(r.swimmer, []).append(r)
        for swimmer in sorted(by_swimmer):
            items = [
                f"{_html_escape(r.event_name)}: {_html_escape(r.final_time)}"
                for r in sorted(by_swimmer[swimmer], key=lambda x: x.event_no)
            ]
            parts.append(swimmer_block_html(swimmer, items))

    if all_stars:
        parts.append(divider)
        parts.append(f"<p><b>{e('⭐')} {random.choice(_ALL_STAR_HEADINGS)}</b></p>")
        by_swimmer = {}
        for r in all_stars:
            by_swimmer.setdefault(r.swimmer, []).append(r)
        for swimmer in sorted(by_swimmer):
            items = [
                f"{_html_escape(r.event_name)}: {_html_escape(r.final_time)}"
                for r in sorted(by_swimmer[swimmer], key=lambda x: x.event_no)
            ]
            parts.append(swimmer_block_html(swimmer, items))

    if pbs:
        parts.append(divider)
        parts.append(f"<p><b>{e('🚀')} {random.choice(_PB_HEADINGS)}</b></p>")

        pbs_by_swimmer: dict[str, list[SwimResult]] = {}
        for r in pbs:
            pbs_by_swimmer.setdefault(r.swimmer, []).append(r)

        for swimmer in sorted(pbs_by_swimmer):
            swims = sorted(
                pbs_by_swimmer[swimmer],
                key=lambda s: s.drop_seconds or 0,
                reverse=True,
            )
            items = []
            for s in swims:
                improvement = (
                    f"improved by {s.drop_seconds:.2f} secs"
                    if s.drop_seconds is not None
                    else "PB"
                )
                items.append(
                    f"{_html_escape(s.event_name)}: {improvement}"
                )
            parts.append(swimmer_block_html(swimmer, items))

    if first_times:
        parts.append(divider)
        parts.append(f"<p><b>{e('✨')} {random.choice(_FIRST_TIME_HEADINGS)}</b></p>")
        by_swimmer = {}
        for r in first_times:
            by_swimmer.setdefault(r.swimmer, []).append(r)
        for swimmer in sorted(by_swimmer):
            items = [
                _html_escape(r.event_name)
                for r in sorted(by_swimmer[swimmer], key=lambda x: x.event_no)
            ]
            parts.append(swimmer_block_html(swimmer, items))

    if not any([records, all_stars, pbs, first_times]):
        parts.append(divider)
        parts.append("<p>Lots of great swims today! No PBs, All-Star times, team records, or first-time swims were detected from this file.</p>")

    parts.append(divider)
    parts.append("<p>Your Lakelands Lionfish Automation Team</p>")
    body = "".join(parts)
    return (
        "<!doctype html>"
        '<html><body style="font-family:Arial,Helvetica,sans-serif;font-size:14px">'
        f"{body}"
        "</body></html>"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse Hy-Tek swim meet results and generate a fun team email.")
    parser.add_argument("pdf", type=Path, help="Meet results PDF")
    parser.add_argument("--team", default="Lakelands", help="Team name filter. Default: Lakelands")
    parser.add_argument("--meet", default=None, help="Meet name for the email subject")
    parser.add_argument("--out", type=Path, default=Path("lld_meet_email.txt"), help="Output email text file")
    parser.add_argument(
        "--first-times",
        dest="first_times",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include a first-time swims section (swimmers with NT seed). Use --no-first-times to hide it.",
    )
    args = parser.parse_args()

    results = parse_results(args.pdf, args.team)
    meet_name = args.meet or extract_meet_name(extract_pdf_text(args.pdf)) or args.pdf.stem

    html_out = args.out.with_suffix(".html")
    html_out.write_text(
        build_email_html(results, meet_name, include_first_times=args.first_times),
        encoding="utf-8",
    )

    print(f"Parsed {len(results)} individual {args.team} results")
    print(f"Personal bests: {sum(r.pb for r in results)}")
    print(f"All-Star times: {sum(r.all_star for r in results)}")
    print(f"Team records: {sum(r.team_record for r in results)}")
    print(f"First-time swims: {sum(r.first_time for r in results)}"
          + ("" if args.first_times else " (hidden in email)"))
    print(f"Wrote: {args.out}")
    print(f"Wrote: {html_out}")


if __name__ == "__main__":
    main()
