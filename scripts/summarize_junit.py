#!/usr/bin/env python3
"""Сводит JUnit XML pytest и Newman в reports/ci-summary.md."""

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"
SOURCES = (
    ("pytest", REPORTS / "pytest.xml"),
    ("Newman", REPORTS / "newman.xml"),
)


def _int(value: str | None) -> int:
    try:
        return int(value or 0)
    except ValueError:
        return 0


def suite_stats(path: Path) -> dict:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    tests = failures = errors = skipped = 0
    time_s = 0.0
    failed_names: list[str] = []
    for suite in suites:
        tests += _int(suite.get("tests"))
        failures += _int(suite.get("failures"))
        errors += _int(suite.get("errors"))
        skipped += _int(suite.get("skipped"))
        time_s += float(suite.get("time") or 0)
        for case in suite.iter("testcase"):
            problem = case.find("failure")
            if problem is None:
                problem = case.find("error")
            if problem is None:
                continue
            name = case.get("name") or "?"
            classname = case.get("classname") or ""
            message = (problem.get("message") or "").strip().splitlines()
            head = message[0][:240] if message else problem.tag
            label = f"{classname}::{name}" if classname else name
            failed_names.append(f"{label} — {head}")
    return {
        "tests": tests,
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
        "time_s": time_s,
        "failed_names": failed_names,
    }


def main() -> None:
    pipeline_status = sys.argv[1] if len(sys.argv) > 1 else "?"
    lines = [
        "# Результаты конвейера",
        "",
        f"Код выхода конвейера: `{pipeline_status}`.",
        "",
        "| Прогон | Тестов | Падений | Ошибок | Пропущено | Время, с | Файл |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    details: list[str] = []
    for title, path in SOURCES:
        if not path.is_file():
            lines.append(f"| {title} | — | — | — | — | — | нет файла |")
            continue
        stats = suite_stats(path)
        lines.append(
            "| {title} | {tests} | {failures} | {errors} | {skipped} | {time_s:.2f} | `{name}` |".format(
                title=title,
                name=path.name,
                **stats,
            )
        )
        if stats["failed_names"]:
            details.append(f"### {title}")
            details.append("")
            details.extend(f"- {item}" for item in stats["failed_names"])
            details.append("")

    if details:
        lines.extend(["", "## Упавшие проверки", ""])
        lines.extend(details)
    else:
        lines.extend(["", "Упавших проверок в JUnit-отчётах нет.", ""])

    text = "\n".join(lines)
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / "ci-summary.md"
    out.write_text(text + "\n", encoding="utf-8")
    print(text)

    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as handle:
            handle.write("\n" + text + "\n")


if __name__ == "__main__":
    main()
