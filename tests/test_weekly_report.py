"""the weekly report script under .github/scripts: markdown from a small csv, the post through a fake gh."""
import importlib.util
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("weekly_report", HERE / ".github" / "scripts" / "weekly_report.py")
wr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wr)

HEADER = ("date_utc,blocks,first_block,last_block,min_gwei,p25_gwei,median_gwei,p75_gwei,p90_gwei,max_gwei,"
          "cheapest_hour_utc,priciest_hour_utc,gas_used_ratio_mean,blob_median_gwei")
CSV = HEADER + """
2026-09-02,7200,1,7200,0.03,0.05,0.07,0.09,0.15,0.5,4,15,0.5,0.003
2026-09-01,7200,1,7200,0.03,0.04,0.06,0.08,0.12,0.4,3,14,0.5,0.002
2026-09-03,7200,1,7200,0.04,0.06,0.10,0.14,0.2,1.2,5,16,0.52,
"""


def test_markdown_orders_days_and_summarises(tmp_path):
    p = tmp_path / "daily.csv"
    p.write_text(CSV, encoding="utf-8")
    rows = wr.week_rows(p)
    assert [r["date_utc"] for r in rows] == ["2026-09-01", "2026-09-02", "2026-09-03"]
    md = wr.markdown(rows, "hour (utc)  median\n00:00  0.05\n", "2026-09-08 07:20 utc")
    assert "| 2026-09-01 | 0.06 | 0.04 | 0.08 | 0.12 | 3:00 | 14:00 | 0.002 |" in md
    assert "median of the daily medians: **0.07 gwei**" in md
    assert "cheapest day 2026-09-01" in md
    assert "```\nhour (utc)  median\n00:00  0.05\n```" in md
    assert "| - |" in md  # the empty blob column of the last row


def test_missing_table_is_said_not_hidden(tmp_path):
    p = tmp_path / "daily.csv"
    p.write_text(CSV, encoding="utf-8")
    md = wr.markdown(wr.week_rows(p), "", "now")
    assert "did not get an answer" in md and "```" not in md


def test_post_finds_the_category_and_sends_title_and_body(monkeypatch):
    calls = []

    def fake_run(cmd, capture_output, text, check):
        calls.append(cmd)
        if "createDiscussion" in cmd[4]:
            out = {"data": {"createDiscussion": {"discussion": {"url": "https://github.com/AlinaSchan/gasweek/discussions/9"}}}}
        else:
            nodes = [{"id": "C_qa", "slug": "q-a"}, {"id": "C_gen", "slug": "general"}]
            out = {"data": {"repository": {"id": "R_1", "discussionCategories": {"nodes": nodes}}}}

        class Out:
            stdout = json.dumps(out)
        return Out()

    monkeypatch.setattr(wr.subprocess, "run", fake_run)
    url = wr.post("weekly gas report, 2026-09-14 (week 38)", "body text")
    assert url.endswith("/discussions/9")
    mutation = calls[1]
    assert "c=C_gen" in mutation and "r=R_1" in mutation
    assert "t=weekly gas report, 2026-09-14 (week 38)" in mutation and "b=body text" in mutation
