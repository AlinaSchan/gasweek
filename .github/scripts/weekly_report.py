"""the weekly gas report: the last seven rows of data/daily.csv as a table, the hour-of-day
table from a fresh run under it, posted as a discussion. standard library plus the gh cli
(present on github runners). `--print` writes the markdown to stdout instead of posting."""
from __future__ import annotations

import csv
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

OWNER, REPO, CATEGORY = "AlinaSchan", "gasweek", "general"


def gwei(text: str) -> str:
    try:
        x = float(text)
    except (TypeError, ValueError):
        return "-"
    return f"{x:.3g}" if x < 1 else f"{x:.2f}"


def week_rows(path: str | Path, days: int = 7) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda r: r["date_utc"])
    return rows[-days:]


def median(values: list[float]) -> float:
    s = sorted(values)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def markdown(rows: list[dict], table: str, run_at: str) -> str:
    lines = [
        f"the last seven utc days from `data/daily.csv` (one row per day, written by the nightly workflow), "
        f"then the hour-of-day table from a fresh run at {run_at}. base fee of the next block, in gwei.",
        "",
        "| day | median | p25 | p75 | p90 | cheapest hour | priciest hour | blob median |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(f"| {r['date_utc']} | {gwei(r['median_gwei'])} | {gwei(r['p25_gwei'])} | {gwei(r['p75_gwei'])} | "
                     f"{gwei(r['p90_gwei'])} | {r['cheapest_hour_utc']}:00 | {r['priciest_hour_utc']}:00 | {gwei(r['blob_median_gwei'])} |")
    meds = [float(r["median_gwei"]) for r in rows if r.get("median_gwei")]
    if meds:
        cheap = min(rows, key=lambda r: float(r["median_gwei"]))
        lines += ["", f"median of the daily medians: **{gwei(str(median(meds)))} gwei**; cheapest day {cheap['date_utc']} "
                      f"at {gwei(cheap['median_gwei'])} gwei; the cheapest hour was {cheap['cheapest_hour_utc']}:00 utc that day."]
    if table.strip():
        lines += ["", "```", table.rstrip(), "```"]
    else:
        lines += ["", "the fresh run did not get an answer from the public rpcs this time; the table above is the nightly data."]
    lines += ["", "posted by the weekly workflow. the code that made every number is this repository; "
                  "a number that looks wrong is an issue, not a mystery."]
    return "\n".join(lines)


def gh_graphql(query: str, variables: dict[str, str]) -> dict:
    cmd = ["gh", "api", "graphql", "-f", f"query={query}"]
    for k, v in variables.items():
        cmd += ["-f", f"{k}={v}"]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def post(title: str, body: str) -> str:
    data = gh_graphql("query($o: String!, $n: String!) { repository(owner: $o, name: $n) { id "
                      "discussionCategories(first: 20) { nodes { id slug } } } }", {"o": OWNER, "n": REPO})
    repo = data["data"]["repository"]
    category = next(c for c in repo["discussionCategories"]["nodes"] if c["slug"] == CATEGORY)
    made = gh_graphql("mutation($r: ID!, $c: ID!, $t: String!, $b: String!) { createDiscussion(input: {repositoryId: $r, "
                      "categoryId: $c, title: $t, body: $b}) { discussion { url } } }",
                      {"r": repo["id"], "c": category["id"], "t": title, "b": body})
    return made["data"]["createDiscussion"]["discussion"]["url"]


def main(argv: list[str]) -> int:
    csv_path, table_path = argv[0], argv[1]
    table = Path(table_path).read_text(encoding="utf-8") if Path(table_path).exists() else ""
    now = dt.datetime.now(dt.timezone.utc)
    week = now.isocalendar()[1]
    title = f"weekly gas report, {now:%Y-%m-%d} (week {week})"
    body = markdown(week_rows(csv_path), table, f"{now:%Y-%m-%d %H:%M} utc")
    if "--print" in argv:
        print(title)
        print(body)
        return 0
    print(post(title, body))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
