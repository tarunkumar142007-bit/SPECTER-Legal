from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule

console = Console()

ORACLE_C  = "bright_magenta"
PHANTOM_C = "cyan"
COUNSEL_C = "green"
VERIFIER_C = "yellow"


def print_oracle(data: dict):
    console.print(Rule(f"[bold {ORACLE_C}]🔮  ORACLE · CONTRACT RISK ENGINE[/bold {ORACLE_C}]"))

    score   = data.get("overall_risk_score", 0)
    verdict = data.get("risk_verdict", "UNKNOWN")
    doc_type= data.get("document_type", "unknown").upper()

    vc = {"CRITICAL":"red","HIGH":"red","MEDIUM":"yellow","LOW":"green"}.get(verdict,"white")

    console.print(f"\n  Document Type : [cyan]{doc_type}[/cyan]")
    console.print(f"  Risk Score    : [{vc} bold]{score}/100[/{vc} bold]")
    console.print(f"  Verdict       : [{vc} bold]{verdict}[/{vc} bold]\n")

    bars = [
        ("Signing Risk",     data.get("signing_risk", 0),            "red"),
        ("Financial Risk",   data.get("financial_risk", 0),          "red"),
        ("Legal Obligation", data.get("legal_obligation_risk", 0),   "yellow"),
        ("Exit Difficulty",  data.get("exit_difficulty_risk", 0),    "magenta"),
    ]
    for label, val, color in bars:
        filled = int(val / 5)
        bar = f"[{color}]{'█' * filled}[/{color}]{'░' * (20 - filled)}"
        console.print(f"  {label:<20} {bar} [{color}]{val}%[/{color}]")

    console.print()
    console.print(Panel(
        f"[dim]{data.get('oracle_assessment', '')}[/dim]",
        title=f"[{ORACLE_C}]ORACLE VERDICT[/{ORACLE_C}]",
        border_style=ORACLE_C
    ))

    # Summary stats
    s = data.get("summary", {})
    console.print(
        f"\n  [red]Critical: {s.get('critical',0)}[/red]  "
        f"[yellow]High: {s.get('high',0)}[/yellow]  "
        f"[blue]Medium: {s.get('medium',0)}[/blue]  "
        f"[green]Low: {s.get('low',0)}[/green]\n"
    )

    # Clause table
    clauses = data.get("clauses", [])
    if clauses:
        table = Table(title="Clause Risk Breakdown", show_lines=True, border_style="dim")
        table.add_column("ID",    width=6,  style="dim")
        table.add_column("Clause",width=20)
        table.add_column("Type",  width=14, style="dim")
        table.add_column("Risk",  width=10)
        table.add_column("Plain English")
        for c in clauses:
            rl = c.get("risk_level","low")
            rc = {"critical":"red","high":"red","medium":"yellow","low":"green"}.get(rl,"white")
            table.add_row(
                c.get("id",""),
                c.get("title",""),
                c.get("type","").replace("_"," "),
                f"[{rc}]{rl.upper()}[/{rc}]",
                c.get("plain_english","")
            )
        console.print(table)

    # Hidden obligations
    ho = data.get("hidden_obligations", [])
    if ho:
        console.print(f"\n  [yellow bold]⚠  Hidden Obligations:[/yellow bold]")
        for o in ho:
            console.print(f"    [yellow]▸[/yellow] {o}")
    console.print()


def print_phantom(data: dict):
    console.print(Rule(f"[bold {PHANTOM_C}]👻  PHANTOM · EXPLANATION & DECISION LAYER[/bold {PHANTOM_C}]"))

    meta    = data.get("_meta", {})
    profile = meta.get("user_profile")
    mode    = meta.get("mode", "generic")

    if mode == "personal" and profile:
        console.print(f"\n  Mode: [green]PERSONAL[/green] → [cyan]{profile['label']}[/cyan]")
        console.print(f"  Focus: [dim]{profile['focus']}[/dim]")
    else:
        console.print(f"\n  Mode: [dim]GENERIC[/dim] → neutral language")

    console.print(f"\n  [dim]{data.get('document_summary','')}[/dim]\n")

    # ── Plain English Brief ──────────────────────────────────────────────────
    peb = data.get("plain_english_brief", {})
    console.print(f"  [bold cyan]📄  PLAIN ENGLISH BRIEF[/bold cyan]")
    console.print(Panel(
        f"[bold]What is this?[/bold]\n{peb.get('what_is_this','')}\n\n"
        f"[bold]What you are agreeing to:[/bold]\n" +
        "\n".join(f"  • {x}" for x in peb.get("what_you_are_agreeing_to", [])),
        border_style="cyan"
    ))

    traps = peb.get("hidden_traps", [])
    if traps:
        console.print(f"  [yellow]Hidden Traps:[/yellow]")
        for t in traps:
            console.print(f"    [yellow]⚠[/yellow] {t}")

    # ── Decision Report ──────────────────────────────────────────────────────
    dr = data.get("decision_report", {})
    verdict = dr.get("verdict", "NEGOTIATE")
    vc = {"SIGN":"green","NEGOTIATE":"yellow","AVOID":"red"}.get(verdict,"white")
    confidence = dr.get("confidence_to_sign", 0)

    console.print(f"\n  [bold yellow]⚖️  DECISION REPORT[/bold yellow]")
    console.print(f"\n  Verdict            : [{vc} bold]{verdict}[/{vc} bold]")
    console.print(f"  Confidence to Sign : [{vc}]{confidence}%[/{vc}]")
    console.print(Panel(dr.get("verdict_reason",""), border_style="yellow"))

    # Clauses to negotiate
    neg = dr.get("clauses_to_negotiate", [])
    if neg:
        console.print(f"  [yellow]Clauses to Negotiate:[/yellow]")
        for n in neg:
            console.print(f"    [yellow]▸[/yellow] [{n.get('clause_id','')}] {n.get('title','')} → {n.get('ask_for','')}")

    # Questions to ask
    qs = dr.get("questions_to_ask", [])
    if qs:
        console.print(f"\n  [cyan]Questions to Ask Before Signing:[/cyan]")
        for i, q in enumerate(qs, 1):
            console.print(f"    [cyan]{i}.[/cyan] {q}")

    # Red flags & positives
    rf = dr.get("red_flags", [])
    pos = dr.get("positives", [])
    if rf:
        console.print(f"\n  [red]Red Flags:[/red]")
        for r in rf:
            console.print(f"    [red]✗[/red] {r}")
    if pos:
        console.print(f"\n  [green]Positives:[/green]")
        for p in pos:
            console.print(f"    [green]✓[/green] {p}")
    console.print()


def print_counselor(data: dict):
    console.print(Rule(f"[bold {COUNSEL_C}]⚖️  COUNSELOR · ACTION ENGINE[/bold {COUNSEL_C}]"))

    # Rewritten clauses
    rewrites = data.get("rewritten_clauses", [])
    if rewrites:
        console.print(f"\n  [green]Rewritten Clauses (Fairer Versions)[/green]")
        for r in rewrites:
            console.print(Panel(
                f"[bold]Original:[/bold] {r.get('original_summary','')}\n\n"
                f"[bold green]Proposed Rewrite:[/bold green]\n{r.get('rewritten','')}\n\n"
                f"[dim]Why better: {r.get('why_better','')}[/dim]",
                title=f"[green]{r.get('clause_id','')} · {r.get('title','')}[/green]",
                border_style="green"
            ))

    # Negotiation script
    ns = data.get("negotiation_script", {})
    if ns:
        console.print(f"\n  [cyan]Negotiation Script[/cyan]")
        console.print(Panel(
            f"[bold]Opening:[/bold]\n{ns.get('opening','')}\n\n"
            f"[bold]Key Asks:[/bold]\n" +
            "\n".join(f"  • {a['ask']} — {a['justification']}" for a in ns.get("key_asks", [])) +
            f"\n\n[bold]Closing:[/bold]\n{ns.get('closing','')}",
            border_style="cyan"
        ))

    # Checklist
    checklist = data.get("before_you_sign_checklist", [])
    if checklist:
        console.print(f"\n  [yellow]Before You Sign — Checklist[/yellow]")
        table = Table(show_lines=True, border_style="dim")
        table.add_column("Done", width=5)
        table.add_column("Item")
        table.add_column("Why It Matters")
        for item in checklist:
            table.add_row("[ ]", item.get("item",""), item.get("why",""))
        console.print(table)

    # Final verdict
    fv = data.get("counselor_verdict","")
    if fv:
        console.print(Panel(fv, title="[green]COUNSELOR FINAL ADVICE[/green]", border_style="green"))
    console.print()
def print_verifier(data: dict):
    console.print(Rule(f"[bold {VERIFIER_C}]🔍  VERIFIER · DOCUMENT AUTHENTICITY ENGINE[/bold {VERIFIER_C}]"))

    verdict     = data.get("trust_verdict", "UNVERIFIABLE")
    score       = data.get("trust_score", 0)
    summary     = data.get("verifier_summary", "")
    proceed     = data.get("proceed_with_analysis", True)
    red_flags   = data.get("red_flags", [])
    missing     = data.get("missing_clauses", [])
    note        = data.get("verification_note", "")

    vc = {
        "TRUSTED":      "green",
        "LIKELY_REAL":  "cyan",
        "SUSPICIOUS":   "yellow",
        "UNVERIFIABLE": "dim",
        "FORGED":       "red",
    }.get(verdict, "white")

    console.print(f"\n  Trust Verdict : [{vc} bold]{verdict}[/{vc} bold]")
    console.print(f"  Trust Score   : [{vc} bold]{score}/100[/{vc} bold]")
    console.print(f"  Proceed       : [{'green' if proceed else 'red'}]{'YES — safe to analyse' if proceed else 'NO — FORGED document detected'}[/{'green' if proceed else 'red'}]\n")

    console.print(Panel(f"[dim]{summary}[/dim]", title=f"[{VERIFIER_C}]VERIFIER VERDICT[/{VERIFIER_C}]", border_style=VERIFIER_C))

    # ── 7-check table ─────────────────────────────────────────────────────────
    checks = data.get("checks", {})
    if checks:
        table = Table(title="Authenticity Checks", show_lines=True, border_style="dim")
        table.add_column("Check",   width=24)
        table.add_column("Status",  width=10)
        table.add_column("Finding")

        check_labels = {
            "signatures":           "Signatures",
            "stamps_seals":         "Stamps & Seals",
            "date_consistency":     "Date Consistency",
            "party_completeness":   "Party Completeness",
            "document_completeness":"Doc Completeness",
            "document_identity":    "Document Identity",
            "tampering_signals":    "Tampering Signals",
        }
        status_colors = {"pass": "green", "warn": "yellow", "fail": "red", "na": "dim"}
        status_icons  = {"pass": "✓", "warn": "⚠", "fail": "✗", "na": "—"}

        for key, label in check_labels.items():
            chk = checks.get(key, {})
            st  = chk.get("status", "na")
            sc  = status_colors.get(st, "white")
            si  = status_icons.get(st, "?")
            table.add_row(label, f"[{sc}]{si} {st.upper()}[/{sc}]", chk.get("finding", ""))

        console.print(table)

    # ── Red flags ─────────────────────────────────────────────────────────────
    if red_flags:
        console.print(f"\n  [red bold]🚩 Red Flags:[/red bold]")
        for flag in red_flags:
            console.print(f"    [red]▸[/red] {flag}")

    # ── Missing clauses ───────────────────────────────────────────────────────
    if missing:
        console.print(f"\n  [yellow]⚠  Missing Standard Clauses:[/yellow]")
        for clause in missing:
            console.print(f"    [yellow]▸[/yellow] {clause}")

    # ── Verification note ─────────────────────────────────────────────────────
    if note:
        console.print(Panel(note, title="[yellow]WHAT TO DO BEFORE SIGNING[/yellow]", border_style="yellow"))

    console.print()