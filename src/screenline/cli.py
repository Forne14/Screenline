"""Screenline command-line interface.

CLI-first, argparse-based (no heavy framework), with `rich` for readable output.

    screenline init my-project
    screenline add meeting_01.mp4
    screenline add transcript.md --for meeting_01.mp4
    screenline build
    screenline status
    screenline list
    screenline inspect [state_id|recording_id]
    screenline export
    screenline analyze recording.mp4        # single-recording convenience
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from screenline import __version__
from screenline.config import Config
from screenline.manifest import Manifest, SCREENLINE_DIR, find_project_root
from screenline.pipeline.build import build as run_build
from screenline.pipeline.export import write_summary_csv
from screenline.project import ProjectError, add_file, init_project

console = Console()


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 1
    try:
        return args.func(args) or 0
    except (ProjectError, FileNotFoundError) as exc:
        console.print(f"[red]error:[/red] {exc}")
        return 1
    except KeyboardInterrupt:  # pragma: no cover
        console.print("\n[yellow]interrupted[/yellow]")
        return 130


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="screenline", description="Visual timeline extraction for screen recordings.")
    p.add_argument("--version", action="version", version=f"screenline {__version__}")
    sub = p.add_subparsers(dest="command")

    sp = sub.add_parser("init", help="Create a new project")
    sp.add_argument("name", help="Project name / directory to create")
    _add_config_args(sp)
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("add", help="Add a recording or transcript to the project")
    sp.add_argument("file", help="Path to a video or transcript file")
    sp.add_argument("--for", dest="recording_for", help="Associate a transcript with a recording (id or filename)")
    sp.set_defaults(func=cmd_add)

    sp = sub.add_parser("build", help="Run the pipeline and (re)generate artifacts")
    sp.add_argument("--force", action="store_true", help="Reprocess all recordings")
    _add_config_args(sp)
    sp.set_defaults(func=cmd_build)

    sp = sub.add_parser("status", help="Show project status")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("list", help="List recordings, transcripts and states")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("inspect", help="Show details for a state or recording")
    sp.add_argument("target", nargs="?", help="state_id or recording id/filename")
    sp.set_defaults(func=cmd_inspect)

    sp = sub.add_parser("export", help="Regenerate exports (summary.csv) from the manifest")
    sp.set_defaults(func=cmd_export)

    sp = sub.add_parser("analyze", help="Single recording: init + add + build in one step")
    sp.add_argument("video", help="Path to a screen recording")
    sp.add_argument("-o", "--output", help="Output project directory (default: <name>_screenline)")
    _add_config_args(sp)
    sp.set_defaults(func=cmd_analyze)

    return p


def _add_config_args(sp: argparse.ArgumentParser) -> None:
    sp.add_argument("--fps", type=float, help="Frame sampling rate (default 1.0)")
    sp.add_argument("--embedder", choices=["default", "clip"], help="Embedding backend")
    sp.add_argument("--cut-distance", type=float, help="Boundary sensitivity (lower = more states)")


def _config_overrides(args, base: Config | None = None) -> Config:
    cfg = base or Config()
    if getattr(args, "fps", None) is not None:
        cfg.sample_fps = args.fps
    if getattr(args, "embedder", None):
        cfg.embedder = args.embedder
    if getattr(args, "cut_distance", None) is not None:
        cfg.cut_distance = args.cut_distance
    return cfg


def _require_project() -> tuple[Path, Manifest]:
    root = find_project_root(Path.cwd())
    if root is None:
        raise ProjectError("Not inside a Screenline project. Run `screenline init <name>` first.")
    return root, Manifest.load(root)


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def cmd_init(args) -> int:
    root = Path(args.name).resolve()
    manifest = init_project(root, name=root.name, config=_config_overrides(args))
    console.print(f"[green]✓[/green] Initialized project [bold]{manifest.project}[/bold] at {root}")
    console.print("  Next: [cyan]screenline add <video>[/cyan] then [cyan]screenline build[/cyan]")
    return 0


def cmd_add(args) -> int:
    root, _ = _require_project()
    kind, ident = add_file(root, Path(args.file), recording_for=args.recording_for)
    console.print(f"[green]✓[/green] Added {kind} [bold]{ident}[/bold] ({Path(args.file).name})")
    return 0


def cmd_build(args) -> int:
    root, manifest = _require_project()
    manifest.config = _config_overrides(args, base=manifest.config)
    if not manifest.recordings:
        console.print("[yellow]No recordings yet.[/yellow] Add some with `screenline add <video>`.")
        return 1
    manifest.save(root)
    report = run_build(root, manifest, force=args.force, log=lambda m: console.print(f"  {m}", style="dim"))
    _print_report(report)
    return 0


def cmd_status(args) -> int:
    root, m = _require_project()
    console.print(f"[bold]{m.project}[/bold]  ({root})")
    console.print(
        f"  recordings: {len(m.recordings)}  transcripts: {len(m.transcripts)}  "
        f"states: {len(m.states)}  transitions: {len(m.transitions)}"
    )
    pending = [r.filename for r in m.recordings if r.status != "processed"]
    if pending:
        console.print(f"  [yellow]unprocessed:[/yellow] {', '.join(pending)}  → run `screenline build`")
    elif m.states:
        scrolls = sum(1 for s in m.states if s.kind == "scroll")
        console.print(f"  [green]built[/green] — {len(m.states)} states ({scrolls} stitched scroll captures)")
    return 0


def cmd_list(args) -> int:
    _, m = _require_project()

    rt = Table(title="Recordings", show_lines=False)
    for col in ("id", "filename", "status", "duration", "transcript"):
        rt.add_column(col)
    for r in m.recordings:
        dur = f"{r.metadata.duration:.0f}s" if r.metadata.duration else "-"
        rt.add_row(r.id, r.filename, _status_style(r.status), dur, r.transcript_id or "-")
    console.print(rt)

    if m.transcripts:
        tt = Table(title="Transcripts")
        for col in ("id", "filename", "format", "recording"):
            tt.add_column(col)
        for t in m.transcripts:
            tt.add_row(t.id, t.filename, t.format, t.recording_id or "(unassigned)")
        console.print(tt)

    if m.states:
        st = Table(title="States")
        for col in ("id", "kind", "occurrences", "recordings", "first seen"):
            st.add_column(col)
        for s in m.states:
            recs = len({o.recording_id for o in s.occurrences})
            first = min((o.start_tc for o in s.occurrences), default="-")
            st.add_row(s.id, s.kind, str(len(s.occurrences)), str(recs), first)
        console.print(st)
    return 0


def cmd_inspect(args) -> int:
    _, m = _require_project()
    target = args.target
    if not target:
        return cmd_list(args)

    state = next((s for s in m.states if s.id == target), None)
    if state:
        console.print(f"[bold]{state.id}[/bold]  kind={state.kind}")
        console.print(f"  screenshot: {state.representative_screenshot}")
        if state.stitched_screenshot:
            console.print(f"  stitched:   {state.stitched_screenshot}")
        t = Table(title="Occurrences")
        for col in ("recording", "start", "end", "confidence"):
            t.add_column(col)
        for o in state.occurrences:
            t.add_row(o.recording_id, o.start_tc, o.end_tc, f"{o.confidence:.2f}")
        console.print(t)
        return 0

    rec = m.recording_by_id(target) or m.recording_by_filename(target)
    if rec:
        console.print(f"[bold]{rec.id}[/bold]  {rec.filename}  status={rec.status}")
        md = rec.metadata
        console.print(f"  {md.width}x{md.height}  {md.fps}fps  {md.duration:.0f}s  codec={md.codec}")
        trans = [t for t in m.transitions if t.recording_id == rec.id]
        if trans:
            t = Table(title="Transitions")
            for col in ("at", "from", "to", "kind", "conf"):
                t.add_column(col)
            for tr in trans:
                t.add_row(tr.at_tc, tr.from_state or "-", tr.to_state or "-", tr.kind, f"{tr.confidence:.2f}")
            console.print(t)
        return 0

    console.print(f"[red]No state or recording matches '{target}'.[/red]")
    return 1


def cmd_export(args) -> int:
    root, m = _require_project()
    path = write_summary_csv(m, root)
    console.print(f"[green]✓[/green] Wrote {path.relative_to(root)}")
    return 0


def cmd_analyze(args) -> int:
    video = Path(args.video).expanduser()
    if not video.exists():
        raise ProjectError(f"Video not found: {video}")
    out = Path(args.output).resolve() if args.output else Path.cwd() / f"{video.stem}_screenline"
    if (out / SCREENLINE_DIR / "screenline.json").exists():
        manifest = Manifest.load(out)
    else:
        manifest = init_project(out, name=video.stem, config=_config_overrides(args))
        console.print(f"[green]✓[/green] Project at {out}")
    if not manifest.recording_by_filename(video.name):
        add_file(out, video)
    manifest = Manifest.load(out)
    manifest.config = _config_overrides(args, base=manifest.config)
    report = run_build(out, manifest, force=True, log=lambda m: console.print(f"  {m}", style="dim"))
    _print_report(report)
    console.print(f"\nArtifacts in [cyan]{out / SCREENLINE_DIR}[/cyan]")
    return 0


# --------------------------------------------------------------------------- #
# rendering helpers
# --------------------------------------------------------------------------- #
def _status_style(status: str) -> str:
    return {
        "processed": "[green]processed[/green]",
        "added": "[yellow]added[/yellow]",
        "error": "[red]error[/red]",
    }.get(status, status)


def _print_report(report: dict) -> None:
    t = report["totals"]
    console.print("\n[bold green]Build complete[/bold green]")
    console.print(
        f"  {t['recordings_processed']} recording(s), {t['frames_sampled']} frames → "
        f"[bold]{t['states']}[/bold] states "
        f"({t['scroll_states']} stitched, {t['transitions']} transitions)"
    )
    console.print(
        f"  dedup: {t['segments']} segments → {t['states']} states "
        f"({t['dedup_ratio'] * 100:.0f}% deduplicated) in {report['elapsed_seconds']}s"
    )
    for w in report.get("warnings", []):
        console.print(f"  [yellow]![/yellow] {w}")


if __name__ == "__main__":
    sys.exit(main())
