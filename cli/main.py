"""xnch CLI entrypoint."""

from __future__ import annotations

import json
import subprocess
from typing import Annotated, Any

import click
import httpx
import typer

from .client import XnchCliClient
from .mcp_tests import CHAT_TESTS, MCP_TOOL_TESTS
from .util import dedupe_memory_results, join_args, parse_recall_intent, parse_timer_line
from .voice import voice_app

app = typer.Typer(
    name="xnch-cli",
    help="Interact with the xnch control plane (session pipeline, Nexi chat, memory).",
    no_args_is_help=True,
)
auth_app = typer.Typer(help="Authentication helpers")
memory_app = typer.Typer(help="Memory queries")
session_app = typer.Typer(help="Manage the CLI's persisted session")
consolidate_app = typer.Typer(help="Consolidation job status (systemd)")
mcp_app = typer.Typer(help="MCP bridge tools (Nexi runtime)")
app.add_typer(auth_app, name="auth")
app.add_typer(memory_app, name="memory")
app.add_typer(session_app, name="session")
app.add_typer(consolidate_app, name="consolidate")
app.add_typer(mcp_app, name="mcp")
app.add_typer(voice_app, name="voice")


@app.command()
def tui() -> None:
    """Launch the Textual TUI dashboard."""
    try:
        from cli.tui.app import XnchTuiApp
    except ImportError:
        typer.secho(
            "Textual is required for the TUI. Install with: pip install textual",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    app_tui = XnchTuiApp()
    app_tui.run()


def _client() -> XnchCliClient:
    return XnchCliClient()


def _print_json(data: object) -> None:
    typer.echo(json.dumps(data, indent=2))


def _handle_error(exc: Exception) -> None:
    if isinstance(exc, httpx.HTTPStatusError):
        detail = exc.response.text
        try:
            detail = exc.response.json().get("detail", detail)
        except Exception:
            pass
        typer.secho(f"HTTP {exc.response.status_code}: {detail}", fg=typer.colors.RED, err=True)
    else:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1)


@app.command()
def health(
    nexi: bool = typer.Option(False, "--nexi", help="Also check nexi health"),
    json_out: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """Check xnch (and optionally nexi) health."""
    try:
        with _client() as client:
            result: dict[str, object] = {"xnch": client.health()}
            if nexi:
                result["nexi"] = client.nexi_health()
    except Exception as exc:
        _handle_error(exc)

    if json_out:
        _print_json(result)
        return

    xnch = result["xnch"]
    assert isinstance(xnch, dict)
    status = xnch.get("status", "unknown")
    color = typer.colors.GREEN if status == "ok" else typer.colors.YELLOW
    typer.secho(f"xnch: {status}", fg=color)
    if redis := xnch.get("redis"):
        typer.echo(f"  redis: {redis}")
    if version := xnch.get("version"):
        typer.echo(f"  version: {version}")

    if nexi:
        nexi_data = result.get("nexi")
        assert isinstance(nexi_data, dict)
        typer.secho(f"nexi: {nexi_data.get('status', 'unknown')}", fg=typer.colors.GREEN)


@app.command()
def status(json_out: bool = typer.Option(False, "--json", help="Output raw JSON")) -> None:
    """Show system and policy versions."""
    try:
        with _client() as client:
            data = client.system_state()
    except Exception as exc:
        _handle_error(exc)

    if json_out:
        _print_json(data)
        return

    typer.echo(f"system_state_version: {data.get('system_state_version')}")
    typer.echo(f"policy_version:       {data.get('policy_version')}")


@app.command("run")
def session_run(
    input_text: Annotated[list[str], typer.Argument(help="Intent / command to execute")],
    priority: str = typer.Option("NORMAL", "--priority", "-p", help="NORMAL or CRITICAL"),
    json_out: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """Run the decision pipeline via /session/init."""
    raw_input = join_args(input_text)
    if not raw_input:
        typer.secho("Input cannot be empty.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    try:
        with _client() as client:
            data = client.session_init(raw_input, priority=priority)
    except Exception as exc:
        _handle_error(exc)

    if json_out:
        _print_json(data)
        return

    typer.secho(f"status: {data.get('status')}", bold=True)
    for key in ("decision_id", "execution_ref", "audit_ref", "hold_id", "error"):
        if value := data.get(key):
            typer.echo(f"{key}: {value}")


@app.command()
def chat(
    message: Annotated[list[str] | None, typer.Argument(help="Message to send (omit for interactive REPL)")] = None,
    stream: bool = typer.Option(False, "--stream", "-s", help="Stream the response"),
    session_id: str | None = typer.Option(None, "--session", help="Session ID override"),
    new_session: bool = typer.Option(False, "--new-session", help="Start a fresh session and persist it"),
    continue_session: bool = typer.Option(False, "--continue", "-c", help="Reuse the stored session (one-shot default)"),
    json_out: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """Chat with Nexi via /nexi/chat."""
    message_text = join_args(message)
    try:
        with _client() as client:
            if new_session:
                session_id = client.new_session()
            elif message_text is None and not continue_session:
                session_id = client.new_session()
            if message_text is None:
                _repl(stream=stream, session_id=session_id, json_out=json_out)
                return

            if stream:
                typer.echo("nexi> ", nl=False)
                text = client.chat_stream(message_text, session_id=session_id)
                if json_out:
                    _print_json({"response": text, "session_id": session_id or client._load_session_id()})
                return
            data = client.chat(message_text, session_id=session_id)
    except Exception as exc:
        _handle_error(exc)

    if json_out:
        _print_json(data)
        return

    typer.echo(data.get("response", ""))


def _repl(*, stream: bool, session_id: str | None, json_out: bool) -> None:
    try:
        with _client() as client:
            sid = session_id or client._load_session_id()
            typer.secho(f"session: {sid}", fg=typer.colors.BRIGHT_BLACK)
            typer.echo("Nexi chat (Ctrl+C or /quit to exit)")
            while True:
                try:
                    user_input = typer.prompt("you")
                except (EOFError, KeyboardInterrupt, click.exceptions.Abort):
                    typer.echo()
                    break

                if not user_input.strip():
                    continue
                stripped = user_input.strip()
                if stripped.lower() in ("/quit", "/exit", "/q"):
                    break
                if stripped.lower() == "/recall":
                    typer.secho("Usage: /recall <query>  (or: recall memory <query>)", fg=typer.colors.BRIGHT_BLACK)
                    continue
                if recall_query := parse_recall_intent(user_input):
                    try:
                        results = client.memory_recall(recall_query)
                    except Exception as exc:
                        _handle_error(exc)
                    _print_recall_results(results, unique=True)
                    continue

                try:
                    if stream:
                        typer.echo("nexi> ", nl=False)
                        client.chat_stream(user_input, session_id=sid)
                    else:
                        data = client.chat(user_input, session_id=sid)
                        if json_out:
                            _print_json(data)
                        else:
                            typer.echo(data.get("response", ""))
                except Exception as exc:
                    _handle_error(exc)
    except KeyboardInterrupt:
        typer.echo()


@auth_app.command("token")
def auth_token(
    actor: str | None = typer.Option(None, "--actor", "-a", help="Actor ID (default: XNCH_ACTOR)"),
    ttl: int = typer.Option(3600, "--ttl", help="Token TTL in seconds"),
) -> None:
    """Mint an HS256 dev token (requires XNCH_AUTH_SECRET)."""
    try:
        with _client() as client:
            token = client.mint_token(actor=actor, ttl_s=ttl)
    except Exception as exc:
        _handle_error(exc)

    typer.echo(token)
    typer.echo()
    typer.secho("Use with: export XNCH_AUTH_TOKEN=\"Bearer <token>\"", fg=typer.colors.BRIGHT_BLACK)


@memory_app.command("recall")
def memory_recall(
    query: Annotated[list[str], typer.Argument(help="Semantic search query (multi-word ok)")],
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of results"),
    unique: bool = typer.Option(True, "--unique/--all", help="Hide duplicate episode content"),
    json_out: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """Recall similar episodes from memory."""
    query_text = join_args(query)
    if not query_text:
        typer.secho("Query cannot be empty.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    try:
        with _client() as client:
            results = client.memory_recall(query_text, top_k=top_k)
    except Exception as exc:
        _handle_error(exc)

    if json_out:
        _print_json(results)
        return

    _print_recall_results(results, unique=unique)


def _print_recall_results(results: list[dict[str, Any]], *, unique: bool = True) -> None:
    if not results:
        typer.echo("No results.")
        return

    display = dedupe_memory_results(results) if unique else results
    hidden = len(results) - len(display)
    if hidden:
        typer.secho(f"({hidden} duplicate result{'s' if hidden != 1 else ''} hidden)", fg=typer.colors.BRIGHT_BLACK)

    for i, item in enumerate(display, 1):
        sim = item.get("similarity", 0.0)
        typer.secho(f"[{i}] similarity={sim:.3f}  type={item.get('type')}", bold=True)
        content = item.get("content", "")
        typer.echo(content[:300] + ("..." if len(content) > 300 else ""))
        typer.echo()


@memory_app.command("surface")
def memory_surface(json_out: bool = typer.Option(False, "--json", help="Output raw JSON")) -> None:
    """Show pending proactivity events."""
    try:
        with _client() as client:
            events = client.memory_surface()
    except Exception as exc:
        _handle_error(exc)

    if json_out:
        _print_json(events)
        return

    if not events:
        typer.echo("No pending events.")
        return

    for event in events:
        typer.echo(json.dumps(event, indent=2))


@session_app.command("show")
def session_show(json_out: bool = typer.Option(False, "--json", help="Output raw JSON")) -> None:
    """Show the currently persisted session id."""
    try:
        with _client() as client:
            session_id = client._load_session_id()
    except Exception as exc:
        _handle_error(exc)

    if json_out:
        _print_json({"session_id": session_id})
        return

    typer.echo(session_id)


@session_app.command("clear")
def session_clear(json_out: bool = typer.Option(False, "--json", help="Output raw JSON")) -> None:
    """Reset to a fresh session (server has no clear endpoint yet)."""
    try:
        with _client() as client:
            session_id = client.clear_session()
    except Exception as exc:
        _handle_error(exc)

    if json_out:
        _print_json({"session_id": session_id})
        return

    typer.secho(f"Session cleared. New session: {session_id}", fg=typer.colors.GREEN)
    typer.secho(
        "Note: server-side working memory has no clear endpoint; a fresh session id avoids stale context.",
        fg=typer.colors.BRIGHT_BLACK,
    )


class _SystemdError(RuntimeError):
    """Raised when a local systemd command cannot be run."""


def _run_systemd(cmd: list[str]) -> str:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except FileNotFoundError as exc:
        raise _SystemdError(f"{cmd[0]} is not available on this host") from exc
    except subprocess.TimeoutExpired as exc:
        raise _SystemdError(f"{cmd[0]} timed out") from exc
    if proc.returncode != 0:
        detail = proc.stderr.strip() or f"exited with code {proc.returncode}"
        raise _SystemdError(detail)
    return proc.stdout.strip()


@consolidate_app.command("status")
def consolidate_status(json_out: bool = typer.Option(False, "--json", help="Output raw JSON")) -> None:
    """Show last consolidation run from the 02:00 UTC timer (systemd)."""
    try:
        timer_out = _run_systemd(
            ["systemctl", "list-timers", "consolidation.timer", "--no-pager", "--no-legend"]
        )
        journal_out = _run_systemd(
            ["journalctl", "-u", "consolidation.service", "--since", "yesterday", "--no-pager", "-n", "30"]
        )
    except _SystemdError as exc:
        if json_out:
            _print_json({"error": str(exc)})
        else:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    timer_row: dict[str, str] | None = None
    for line in timer_out.splitlines():
        timer_row = parse_timer_line(line)
        if timer_row:
            break

    if json_out:
        _print_json({"timer": timer_row, "journal": journal_out})
        return

    typer.echo("consolidation.timer (02:00 UTC daily)")
    if timer_row:
        typer.echo(f"  next:   {timer_row.get('next')}")
        typer.echo(f"  left:   {timer_row.get('left')}")
        typer.echo(f"  last:   {timer_row.get('last')}")
        typer.echo(f"  passed: {timer_row.get('passed')}")
    else:
        typer.secho("  (timer row not found)", fg=typer.colors.YELLOW)
    typer.echo("last journal output (consolidation.service):")
    for line in journal_out.splitlines()[-10:]:
        typer.echo(f"  {line}")


def _parse_mcp_args(args: list[str]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for item in args:
        if "=" not in item:
            raise typer.BadParameter(f"Expected key=value, got: {item!r}")
        key, _, raw = item.partition("=")
        key = key.strip()
        raw = raw.strip()
        if not key:
            raise typer.BadParameter(f"Empty key in: {item!r}")
        try:
            parsed[key] = json.loads(raw)
        except json.JSONDecodeError:
            parsed[key] = raw
    return parsed


@mcp_app.command("servers")
def mcp_servers(
    actor: str = typer.Option("nexi", "--actor", "-a", help="Actor role header"),
    json_out: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """List MCP bridge server status."""
    try:
        with _client() as client:
            data = client.mcp_servers(actor_role=actor)
    except Exception as exc:
        _handle_error(exc)

    if json_out:
        _print_json(data)
        return

    if not data.get("enabled"):
        typer.secho("MCP bridge disabled", fg=typer.colors.YELLOW)
        return

    for srv in data.get("servers", []):
        connected = "connected" if srv.get("connected") else "down"
        color = typer.colors.GREEN if srv.get("connected") else typer.colors.RED
        typer.secho(
            f"{srv.get('server_id')}: {connected}  "
            f"tools={srv.get('tool_count')}  prefix={srv.get('tool_prefix')}",
            fg=color,
        )


@mcp_app.command("tools")
def mcp_tools(
    actor: str = typer.Option("nexi", "--actor", "-a", help="Actor role header"),
    prefix: str | None = typer.Option(None, "--prefix", "-p", help="Filter by name prefix"),
    json_out: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """List MCP tools available to an actor."""
    try:
        with _client() as client:
            data = client.mcp_tools(actor_role=actor)
    except Exception as exc:
        _handle_error(exc)

    tools = data.get("tools", [])
    if prefix:
        tools = [t for t in tools if str(t.get("name", "")).startswith(prefix)]

    if json_out:
        _print_json({"actor": data.get("actor", actor), "tools": tools})
        return

    typer.echo(f"actor: {data.get('actor', actor)}  tools: {len(tools)}")
    for tool in tools:
        typer.echo(f"  {tool.get('name')}  [{tool.get('tier')}]")


@mcp_app.command("call")
def mcp_call(
    tool_name: Annotated[str, typer.Argument(help="Tool name, e.g. crg_list_graph_stats_tool")],
    arg: list[str] = typer.Option([], "--arg", help="Tool argument as key=value (JSON values ok)"),
    actor: str = typer.Option("nexi", "--actor", "-a", help="Actor role header"),
    json_out: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """Invoke an MCP tool via /mcp/call."""
    try:
        arguments = _parse_mcp_args(arg)
        with _client() as client:
            data = client.mcp_call(tool_name, arguments, actor_role=actor)
    except typer.BadParameter:
        raise
    except Exception as exc:
        _handle_error(exc)

    if json_out:
        _print_json(data)
        return

    result = data.get("result")
    if isinstance(result, (dict, list)):
        _print_json(result)
    else:
        typer.echo(result)


@mcp_app.command("test")
def mcp_test(
    skip_chat: bool = typer.Option(False, "--skip-chat", help="Skip live /nexi/chat tool-loop tests"),
    json_out: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """Run MCP bridge integration tests (tools + optional Nexi chat)."""
    cases = list(MCP_TOOL_TESTS)
    if not skip_chat:
        cases.extend(CHAT_TESTS)

    results: list[dict[str, str]] = []
    passed = failed = 0

    try:
        with _client() as client:
            for case in cases:
                try:
                    detail = case.run(client)
                    results.append({"name": case.name, "status": "pass", "detail": detail})
                    passed += 1
                    if not json_out:
                        typer.secho(f"✓ {case.name}", fg=typer.colors.GREEN)
                except Exception as exc:
                    results.append({"name": case.name, "status": "fail", "detail": str(exc)})
                    failed += 1
                    if not json_out:
                        typer.secho(f"✗ {case.name}: {exc}", fg=typer.colors.RED)
    except Exception as exc:
        _handle_error(exc)

    summary = {"passed": passed, "failed": failed, "results": results}
    if json_out:
        _print_json(summary)
    else:
        typer.echo()
        typer.echo(f"Result: {passed} passed, {failed} failed")

    if failed:
        raise typer.Exit(code=1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
