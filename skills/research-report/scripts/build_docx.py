#!/usr/bin/env python3
"""One-click pipeline to build a formatted Chinese research report DOCX from Markdown.

Steps performed automatically:
1. Convert Markdown to base DOCX (in an ASCII temp directory to avoid CJK path issues).
2. Insert and style the 3-level automatic Word Table of Contents (TOC).
3. On Windows with Microsoft Word installed, update TOC/page fields via Word COM;
   on macOS/Linux or systems without Word, gracefully degrade (Word will prompt/update on open).
4. Optionally export PDF and per-page PNG previews when --render-dir is specified.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from ensure_toc import ensure_toc
from markdown_to_docx import MODES, convert


def _run_powershell(script: Path, *args: str) -> tuple[bool, str]:
    pwsh = shutil.which("powershell") or shutil.which("pwsh")
    if not pwsh:
        return False, "PowerShell executable not found"
    cmd = [pwsh, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or f"Exit code {proc.returncode}").strip()
    return True, proc.stdout.strip()


def build_report(
    input_md: Path,
    output_docx: Path,
    mode: str = "decision-proposal",
    render_dir: Path | None = None,
    skip_word_update: bool = False,
    encoding: str = "utf-8-sig",
) -> dict:
    if not input_md.is_file():
        raise FileNotFoundError(f"Markdown source file not found: {input_md}")

    text = input_md.read_text(encoding=encoding)
    output_docx = output_docx.resolve()
    output_docx.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="report_build_") as tmp:
        tmp_dir = Path(tmp)
        base_docx = tmp_dir / "base.docx"
        staged_docx = tmp_dir / "report.docx"

        conv_report = convert(
            text=text,
            output=base_docx,
            mode=mode,
            base_dir=input_md.resolve().parent,
            title_mode="auto",
        )

        if conv_report.get("needs_toc", True):
            toc_report = ensure_toc(base_docx, staged_docx)
        else:
            shutil.copyfile(base_docx, staged_docx)
            toc_report = {"ok": True, "created": False, "needs_field_update": False}

        word_updated = False
        word_note = ""
        if sys.platform == "win32" and not skip_word_update:
            upd_script = SCRIPT_DIR / "update_word_fields.ps1"
            ok, detail = _run_powershell(upd_script, "-InputDocx", str(staged_docx))
            word_updated = ok
            if not ok:
                word_note = (
                    "Skipped Word COM field refresh (Microsoft Word not available or COM blocked). "
                    "Automatic TOC field with w:updateFields=true is embedded and will refresh when opened."
                )
        else:
            word_note = (
                "Word COM field refresh skipped on non-Windows platform or by flag; "
                "w:updateFields=true is set on the document."
            )

        shutil.copyfile(staged_docx, output_docx)

        rendered_pages: list[str] = []
        if render_dir is not None and sys.platform == "win32" and word_updated:
            render_dir = render_dir.resolve()
            render_dir.mkdir(parents=True, exist_ok=True)
            rnd_script = SCRIPT_DIR / "render_with_word.ps1"
            ok, _ = _run_powershell(
                rnd_script,
                "-InputDocx",
                str(staged_docx),
                "-OutputDir",
                str(render_dir),
            )
            if ok:
                rendered_pages = [
                    str(p) for p in sorted(render_dir.glob("page-*.png"))
                ]

    return {
        "ok": True,
        "input": str(input_md.resolve()),
        "output": str(output_docx),
        "headings": conv_report.get("headings", 0),
        "tables": conv_report.get("tables", 0),
        "images": len(conv_report.get("images", [])),
        "toc_inserted": toc_report.get("created", False),
        "word_fields_updated": word_updated,
        "note": word_note or "DOCX generated and TOC/page fields updated via Word.",
        "rendered_pages": rendered_pages,
    }


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Input Markdown file path")
    parser.add_argument("--out", type=Path, required=True, help="Output DOCX file path")
    parser.add_argument("--mode", choices=MODES, default="decision-proposal")
    parser.add_argument("--render-dir", type=Path, help="Optional directory to render PDF/PNG previews")
    parser.add_argument("--skip-word-update", action="store_true", help="Skip Word COM field update")
    parser.add_argument("--encoding", default="utf-8-sig")
    args = parser.parse_args()

    try:
        report = build_report(
            input_md=args.input,
            output_docx=args.out,
            mode=args.mode,
            render_dir=args.render_dir,
            skip_word_update=args.skip_word_update,
            encoding=args.encoding,
        )
    except Exception as exc:
        report = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
