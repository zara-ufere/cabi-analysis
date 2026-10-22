"""Command line: cabi download | load | analyze | quality."""
from __future__ import annotations

import argparse
import os
import sys

from . import analysis, download, figures, findings, load


def _cmd_download(a) -> int:
    failed = 0
    for month, path, err in download.fetch_range(a.start, a.end, a.dir, force=a.force):
        if err:
            failed += 1
            print("%s: %s" % (month, err), file=sys.stderr)
        else:
            print("%s: %s" % (month, path))
    return 1 if failed else 0


def _cmd_load(a) -> int:
    reports = load.load_files(a.db, a.files)
    for r in reports:
        rej = sum(r["rejected"].values())
        print("%s: read %d, kept %d, rejected %d" % (r["file"], r["read"], r["kept"], rej))
    return 0


def _cmd_analyze(a) -> int:
    if not os.path.exists(a.db):
        print("no such database: %s (run `cabi load` first)" % a.db, file=sys.stderr)
        return 2
    conn = load.connect(a.db)
    has_view = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name = 'analysis_trips'").fetchone()[0]
    if not has_view or not conn.execute("SELECT COUNT(*) FROM analysis_trips").fetchone()[0]:
        print("database has no trips (run `cabi load` first)", file=sys.stderr)
        return 2
    r = analysis.everything(conn)
    cov = analysis.coverage(conn)
    if not cov["trips"]:
        print("database has no trips", file=sys.stderr)
        return 2
    figs = {}
    for theme in ("light", "dark") if a.dark else ("light",):
        figs.update({k + ("" if theme == "light" else "-dark"): v
                     for k, v in figures.save_all(r, os.path.join(a.out, "figures"), theme).items()})
    for name, df in r.items():
        df.to_csv(os.path.join(a.out, name + ".csv"), index=False)
    light = {k: os.path.relpath(v, a.out) for k, v in figs.items() if not k.endswith("-dark")}
    with open(os.path.join(a.out, "findings.md"), "w") as fh:
        fh.write(findings.render_markdown(r, cov, light))
    print("wrote %s" % os.path.join(a.out, "findings.md"))
    return 0


def _cmd_quality(a) -> int:
    conn = load.connect(a.db)
    print(analysis.quality(conn).to_string(index=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cabi", description="Capital Bikeshare trip analysis")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("download", help="fetch monthly trip zips")
    d.add_argument("start", help="first month, YYYY-MM")
    d.add_argument("end", help="last month, YYYY-MM")
    d.add_argument("--dir", default="data")
    d.add_argument("--force", action="store_true")
    d.set_defaults(fn=_cmd_download)
    l = sub.add_parser("load", help="clean and load zips or CSVs into SQLite")
    l.add_argument("--db", default="data/cabi.db")
    l.add_argument("files", nargs="+")
    l.set_defaults(fn=_cmd_load)
    an = sub.add_parser("analyze", help="run analyses, write figures, CSVs and findings.md")
    an.add_argument("--db", default="data/cabi.db")
    an.add_argument("--out", default="reports")
    an.add_argument("--dark", action="store_true", help="also write dark-theme figures")
    an.set_defaults(fn=_cmd_analyze)
    q = sub.add_parser("quality", help="print rows removed by cleaning")
    q.add_argument("--db", default="data/cabi.db")
    q.set_defaults(fn=_cmd_quality)
    return p


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == "analyze":
        os.makedirs(a.out, exist_ok=True)
    try:
        return a.fn(a)
    except (load.SchemaError, download.DownloadError, ValueError, OSError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
