import os
from rich.console import Console
from rich.rule import Rule
from rich.table import Table

import oracle
import phantom
import counselor
import briefing
import verifier


os.environ["ANTHROPIC_API_KEY"] = "your_api_key_here"

console = Console()


def get_document_input() -> str:
    console.print("\n[dim]Paste your legal document below. Type [bold]END[/bold] on a new line when done.[/dim]\n")
    lines = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)
    return "\n".join(lines)


def pick_user_type() -> str | None:
    types = phantom.list_user_types()
    profiles = [phantom.get_user_profile(k) for k in types]

    console.print("\n[dim]Who are you? (helps PHANTOM tailor its explanation)[/dim]")
    table = Table(show_header=True, header_style="dim", box=None)
    table.add_column("Key",      style="cyan",   width=12)
    table.add_column("Type",     style="white",  width=22)
    table.add_column("Focus",    style="dim")
    for key, profile in zip(types, profiles):
        table.add_row(key, profile["label"], profile["focus"])
    console.print(table)

    console.print("\n[dim]Enter your type key (or press Enter to skip → generic mode):[/dim] ", end="")
    raw = input().strip().lower()
    if not raw:
        return None
    if phantom.get_user_profile(raw):
        return raw
    console.print(f"[yellow]'{raw}' not found — using generic mode.[/yellow]")
    return None


def run():
    console.print()
    console.print(Rule("[bold]⚖️  S P E C T E R  L E G A L[/bold]"))
    console.print(
        "[dim]Smart Predictive Explainer for Contract Text Evaluation & Risk[/dim]",
        justify="center"
    )
    console.print(Rule())

    document = get_document_input()
    if not document.strip():
        console.print("[red]No document provided. Exiting.[/red]")
        return

    user_type = pick_user_type()
    console.print("[bright_yellow]🔍  VERIFIER checking document authenticity & completeness...[/bright_yellow]")

    try:
        verifier_data = verifier.verify_from_text(document)
    except Exception as e:
        console.print(f"[yellow]VERIFIER WARNING: {e} — skipping verification, proceeding with analysis.[/yellow]")
        verifier_data = {"trust_verdict": "UNVERIFIABLE", "proceed_with_analysis": True}

    briefing.print_verifier(verifier_data)

    # Block the pipeline if forgery is detected
    if verifier.should_block_analysis(verifier_data):
        console.print(
            "[red bold]⛔  VERIFIER detected document forgery. "
            "Analysis blocked. Verify this document manually before proceeding.[/red bold]"
        )
        return   # exits run()

    # If SUSPICIOUS — warn but continue
    if verifier_data.get("trust_verdict") == "SUSPICIOUS":
        console.print(
            "[yellow]⚠  VERIFIER flagged this document as SUSPICIOUS. "
            "Proceeding with analysis — but review red flags before signing.[/yellow]\n"
        )

    # ── ORACLE ───────────────────────────────────────────────────────────────
    console.print("\n[bright_magenta]🔮  ORACLE scanning document for risks...[/bright_magenta]")
    try:
        oracle_data = oracle.analyze(document)
    except Exception as e:
        console.print(f"[red]ORACLE ERROR: {e}[/red]")
        return
    briefing.print_oracle(oracle_data)

    # ── PHANTOM ──────────────────────────────────────────────────────────────
    mode_label = f"personal → [cyan]{user_type}[/cyan]" if user_type else "generic"
    console.print(f"[cyan]👻  PHANTOM generating explanation & decision report ({mode_label})...[/cyan]")
    try:
        phantom_data = phantom.generate_reports(
            oracle_data=oracle_data,
            document_text=document,
            user_type=user_type,
        )
    except Exception as e:
        console.print(f"[red]PHANTOM ERROR: {e}[/red]")
        phantom_data = {}
    briefing.print_phantom(phantom_data)

    # ── COUNSELOR ─────────────────────────────────────────────────────────────
    console.print("[green]⚖️  COUNSELOR generating action plan & rewrites...[/green]")
    try:
        counselor_data = counselor.advise(
            oracle_data=oracle_data,
            phantom_data=phantom_data,
            document_text=document,
        )
    except Exception as e:
        console.print(f"[red]COUNSELOR ERROR: {e}[/red]")
        counselor_data = {}
    briefing.print_counselor(counselor_data)

    console.print(Rule("[bold]SPECTER LEGAL — MISSION COMPLETE[/bold]"))


if __name__ == "__main__":
    run()
