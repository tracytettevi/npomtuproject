"""Small local workspace app for the campaign analytics assignment demo.

Run with the project's Python interpreter, then open http://127.0.0.1:8000.
The server listens on localhost only and uses no third-party packages.
"""

from __future__ import annotations

import html
import json
import os
import secrets
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "outputs"
WORKSPACE_PATH = OUTPUT_DIR / "workspace.json"
PROGRESS_PATH = OUTPUT_DIR / "workflow_progress.json"
PORT = int(os.environ.get("PORT", "8000"))
CSRF_TOKEN = secrets.token_urlsafe(24)

PIPELINE = {
    "data": ("Generate synthetic datasets", "data.py", "Recreates the synthetic databases for both scenarios."),
    "sql": ("Run SQL checks and analysis", "run_sql.py", "Quality checks and findings for the selected scenario."),
    "model": ("Train and evaluate selected model", "model.py", "Predicts the selected campaign outcome or subscription churn."),
    "ai": ("Generate Snwolley insight brief", "snwolley_agent.py", "Sends aggregate synthetic results to Snwolley."),
    "dashboard": ("Build business dashboard", "dashboard.py", "Refreshes the HTML dashboard from available outputs."),
}


def load_workspace() -> dict | None:
    if not WORKSPACE_PATH.exists():
        return None
    try:
        value = json.loads(WORKSPACE_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def load_progress() -> dict[str, bool]:
    if PROGRESS_PATH.is_file():
        try:
            saved = json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                return {key: bool(saved.get(key, False)) for key in PIPELINE}
        except (OSError, json.JSONDecodeError):
            pass
    return {key: False for key in PIPELINE}


def save_progress(progress: dict[str, bool]) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    PROGRESS_PATH.write_text(json.dumps(progress, indent=2), encoding="utf-8")


def next_action(progress: dict[str, bool]) -> str | None:
    return next((key for key in PIPELINE if not progress.get(key, False)), None)


def load_snwolley_brief() -> str:
    """Read the latest Snwolley brief for display in the workspace."""
    workspace = load_workspace() or {}
    selected = workspace.get("use_case", "campaigns")
    scenario_path = OUTPUT_DIR / f"ai_insights_{selected}.txt"
    if scenario_path.is_file():
        try:
            content = scenario_path.read_text(encoding="utf-8").strip()
            if content:
                return content
        except OSError:
            return ""
    marker = OUTPUT_DIR / "ai_insights_use_case.txt"
    if marker.exists():
        try:
            if marker.read_text(encoding="utf-8").strip() != selected:
                return ""
        except OSError:
            return ""
    elif selected != "campaigns":
        # Legacy briefs were campaign-specific and must never appear as churn advice.
        return ""
    for filename in ("ai_insights.txt", "ai_insights.md"):
        path = OUTPUT_DIR / filename
        if path.is_file():
            try:
                content = path.read_text(encoding="utf-8").strip()
                if content:
                    return content
            except OSError:
                continue
    return ""


def page(message: str = "") -> bytes:
    workspace = load_workspace()
    brief = load_snwolley_brief()
    brief_section = (
        f'<section class="card result"><div class="eyebrow">SNWOLLEY INSIGHT BRIEF</div>'
        f'<pre>{esc(brief)}</pre></section>'
        if brief else
        '<section class="card"><div class="eyebrow">SNWOLLEY INSIGHT BRIEF</div>'
        '<p class="muted">No brief yet. Run “Generate Snwolley insight brief” to show it here.</p></section>'
    )
    if workspace:
        is_retention = workspace.get("use_case") == "retention"
        target_label = ("customer churn" if is_retention else
                        "message conversion" if workspace.get("model_target") == "converted" else "message response")
        use_case_label = "Subscription retention" if is_retention else "SMS campaign analytics"
        workspace_card = f"""<section class="card profile"><div><div class="eyebrow">ACTIVE WORKSPACE</div>
          <h2>{esc(workspace['business_name'])}</h2><p>{esc(workspace['industry'])} · Owner: {esc(workspace['owner'])}</p>
          <p><b>Business scenario:</b> {esc(use_case_label)}</p><p><b>Business question:</b> {esc(workspace['business_question'])}</p><p><b>Prediction goal:</b> {esc(target_label)}</p></div>
          <form method="post" action="/reset-workspace"><input type="hidden" name="csrf" value="{CSRF_TOKEN}"><button class="secondary" type="submit">Edit workspace</button></form></section>"""
        workspace_form = ""
    else:
        workspace_card = ""
        workspace_form = f"""<section class="card"><div class="eyebrow">WORKSPACE ONBOARDING</div><h2>Set up your analysis workspace</h2>
          <p class="muted">Choose one of the implemented synthetic business scenarios, then run its complete analytics workflow.</p>
          <form method="post" action="/workspace"><input type="hidden" name="csrf" value="{CSRF_TOKEN}">
          <label>Business or team name<input name="business_name" required maxlength="80" placeholder="e.g. Acme Retail"></label>
          <div class="form-row"><label>Industry<input name="industry" required maxlength="60" placeholder="e.g. Retail"></label>
          <label>Workspace owner<input name="owner" required maxlength="60" placeholder="Your name"></label></div>
          <label>Business scenario<select name="use_case"><option value="campaigns">SMS campaign performance and response</option><option value="retention">Subscription customer retention and churn</option></select></label>
          <label>Business question<input id="business-question" name="business_question" required maxlength="180" value="Which SMS campaigns and customer segments show stronger response or conversion?"></label>
          <label id="campaign-target">Campaign prediction goal<select name="model_target"><option value="responded">Predict message response</option><option value="converted">Predict conversion</option></select></label>
          <p class="muted" id="scenario-help">Choose which campaign outcome the model should predict.</p>
          <button type="submit">Create workspace</button></form>
          <script>const scenario=document.querySelector('[name=use_case]'),target=document.getElementById('campaign-target'),question=document.getElementById('business-question'),help=document.getElementById('scenario-help');scenario.addEventListener('change',()=>{{const retention=scenario.value==='retention';target.hidden=retention;help.textContent=retention?'The retention model predicts subscription churn from account history.':'Choose which campaign outcome the model should predict.';question.value=retention?'Which subscription accounts show higher churn risk, and what patterns should the business investigate?':'Which SMS campaigns and customer segments show stronger response or conversion?';}});</script></section>"""

    actions = []
    progress = load_progress()
    current_action = next_action(progress)
    for key, (title, script, description) in PIPELINE.items():
        complete = progress[key]
        is_next = key == current_action
        state = "Completed" if complete else ("Next step" if is_next else "Locked")
        button_disabled = not workspace or not is_next
        button_text = "Completed" if complete else ("Run this step" if is_next else "Complete the prior step first")
        actions.append(f"""<article class="step"><div class="step-top"><span class="step-number">{len(actions)+2:02d}</span>
          <span class="status">{esc(state)}</span></div>
          <h3>{esc(title)}</h3><p>{esc(description)}</p>
          <form method="post" action="/run"><input type="hidden" name="csrf" value="{CSRF_TOKEN}">
          <input type="hidden" name="action" value="{key}"><button type="submit" {'disabled' if button_disabled else ''}>{esc(button_text)}</button></form></article>""")

    result_section = f'<section class="card result"><div class="eyebrow">LATEST ACTION</div><pre>{esc(message)}</pre></section>' if message else ""
    body = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
      <title>Business Analytics Workspace</title><style>
      :root{{--ink:#183247;--muted:#64798a;--line:#e1e9ef;--bg:#f3f7fa;--teal:#087f8c;--white:#fff}}
      *{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
      header{{background:#122d40;color:white;padding:28px max(22px,calc((100vw - 1080px)/2))}}header .eyebrow{{color:#8ed2d4}}
      main{{max-width:1080px;margin:28px auto;padding:0 22px 44px}}h1{{margin:5px 0;font-size:28px}}h2{{margin:8px 0;font-size:21px}}p{{margin:5px 0 14px}}.eyebrow{{font-size:11px;font-weight:750;letter-spacing:.12em;color:var(--teal)}}
      .card,.step{{background:var(--white);border:1px solid var(--line);border-radius:12px;box-shadow:0 2px 8px #1832470d}}.card{{padding:22px;margin-bottom:18px}}.profile{{display:flex;align-items:center;justify-content:space-between;gap:18px}}.muted,.step p{{color:var(--muted);font-size:13px}}
      label{{display:block;font-weight:650;font-size:13px;margin:12px 0}}input{{display:block;width:100%;margin-top:5px;padding:10px 12px;border:1px solid #cbd8e1;border-radius:7px;font:inherit}}.form-row{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
      button{{background:var(--teal);color:white;border:0;border-radius:7px;padding:10px 14px;font:inherit;font-weight:700;cursor:pointer}}button:hover{{filter:brightness(.94)}}.button-link{{display:inline-block;background:var(--teal);color:white;text-decoration:none;border-radius:7px;padding:10px 14px;font-weight:700;margin:4px 8px 4px 0}}.button-link:hover{{filter:brightness(.94)}}button:disabled{{background:#9aabb7;cursor:not-allowed}}button.secondary{{background:#e8eff4;color:var(--ink)}}
      .grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}.step{{padding:18px}}.step-top{{display:flex;justify-content:space-between;align-items:center}}.step-number{{font-weight:800;color:var(--teal)}}.status{{font-size:11px;color:var(--muted);background:#edf2f5;border-radius:20px;padding:4px 8px}}.step h3{{font-size:16px;margin:13px 0 5px}}.step p{{min-height:40px}}.step form{{margin-top:12px}}.result pre{{white-space:pre-wrap;font:13px/1.5 ui-monospace,monospace;margin:8px 0 0}}.notice{{padding:13px;border:1px solid #edd6aa;background:#fff7e8;color:#634819;border-radius:8px;font-size:13px;margin-bottom:18px}}
      @media(max-width:760px){{.grid{{grid-template-columns:1fr 1fr}}}}@media(max-width:520px){{.grid,.form-row{{grid-template-columns:1fr}}.profile{{align-items:flex-start;flex-direction:column}}}}
      </style></head><body><header><div class="eyebrow">INTELLIGENT SYSTEMS SERVICES · ASSIGNMENT DEMO</div><h1>Business Analytics Workspace</h1><p>From business question to SQL analysis, machine learning, AI insight and report</p></header><main>
      <div class="notice"><b>Prototype scope:</b> choose SMS campaign performance or subscription retention. Each scenario has its own synthetic data, SQL analysis, prediction model, Snwolley prompt, and dashboard. Loading arbitrary external datasets and production access controls remain future extensions.</div>
      {workspace_form}{workspace_card}{result_section}{brief_section}
      <section class="card"><div class="eyebrow">ASSIGNMENT SECTIONS</div><h2>Jump to the evidence you need</h2>
      <p class="muted">Open the dashboard directly at the results for assignment Parts 4 and 5.</p>
      <p><a class="button-link" href="/dashboard#part-4">Open Part 4: Machine Learning</a>
      <a class="button-link" href="/dashboard#part-5">Open Part 5: Snwolley Insights</a></p></section>
      <h2>Step-by-step process</h2><p class="muted">Follow the numbered steps in order. Step 1 is creating the workspace. Then run Step 2, Generate Data; Step 3, SQL Analysis; Step 4, Train and Evaluate the Model; Step 5, Generate the Snwolley Brief; and Step 6, Build the Dashboard. Only the next step will be available until the current step completes.</p>
      <div class="grid">{''.join(actions)}</div><p style="margin-top:18px"><a href="/dashboard">Open the current dashboard</a></p>
      <footer class="muted" style="margin-top:22px">This local demo is only available on this computer at 127.0.0.1:8000.</footer></main></body></html>"""
    return body.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def respond(self, status: int, content: bytes, content_type: str = "text/html; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:
        if self.path == "/" or self.path.startswith("/?"):
            self.respond(200, page())
            return
        if self.path == "/dashboard":
            target = OUTPUT_DIR / "dashboard.html"
            if target.is_file():
                self.respond(200, target.read_bytes())
            else:
                self.respond(404, b"Dashboard has not been generated yet.", "text/plain; charset=utf-8")
            return
        self.respond(404, b"Not found", "text/plain; charset=utf-8")

    def do_POST(self) -> None:
        length = min(int(self.headers.get("Content-Length", "0")), 16_384)
        fields = parse_qs(self.rfile.read(length).decode("utf-8", errors="replace"))
        if fields.get("csrf", [""])[0] != CSRF_TOKEN:
            self.respond(403, page("Request rejected: refresh the page and try again."))
            return
        if self.path == "/workspace":
            use_case = fields.get("use_case", ["campaigns"])[0]
            if use_case not in {"campaigns", "retention"}:
                use_case = "campaigns"
            workspace = {
                "business_name": fields.get("business_name", [""])[0].strip()[:80],
                "industry": fields.get("industry", [""])[0].strip()[:60],
                "owner": fields.get("owner", [""])[0].strip()[:60],
                "business_question": fields.get("business_question", [""])[0].strip()[:180],
                "use_case": use_case,
                "implemented_use_case": "subscription_retention" if use_case == "retention" else "sms_campaign_analytics",
                "model_target": fields.get("model_target", ["responded"])[0]
                if fields.get("model_target", ["responded"])[0] in {"responded", "converted"}
                else "responded",
            }
            if not all(workspace[key] for key in ("business_name", "industry", "owner", "business_question")):
                self.respond(400, page("Complete all workspace fields."))
                return
            OUTPUT_DIR.mkdir(exist_ok=True)
            WORKSPACE_PATH.write_text(json.dumps(workspace, indent=2), encoding="utf-8")
            save_progress({key: False for key in PIPELINE})
            for filename in ("model_report.json", "scored_messages.csv", "scored_accounts.csv",
                             "dashboard.html"):
                try:
                    (OUTPUT_DIR / filename).unlink()
                except FileNotFoundError:
                    pass
            self.redirect_home("Workspace created. You can now run the analysis workflow.")
            return
        if self.path == "/reset-workspace":
            for path in (WORKSPACE_PATH, PROGRESS_PATH):
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
            for filename in ("model_report.json", "scored_messages.csv", "scored_accounts.csv",
                             "dashboard.html"):
                try:
                    (OUTPUT_DIR / filename).unlink()
                except FileNotFoundError:
                    pass
            self.redirect_home("Workspace cleared. Enter the updated workspace details.")
            return
        if self.path == "/run":
            action = fields.get("action", [""])[0]
            if not load_workspace():
                self.respond(400, page("Create a workspace before running pipeline steps."))
                return
            if action not in PIPELINE:
                self.respond(400, page("Unknown workflow step."))
                return
            progress = load_progress()
            if action != next_action(progress):
                self.respond(409, page("Complete the currently enabled step before moving to the next one."))
                return
            title, script, _ = PIPELINE[action]
            try:
                command = [sys.executable, str(ROOT / script)]
                selected_workspace = load_workspace()
                selected_case = selected_workspace.get("use_case", "campaigns")
                if action == "sql":
                    command.extend(("--use-case", selected_case))
                if action == "model" and selected_case == "retention":
                    command = [sys.executable, str(ROOT / "retention_model.py")]
                elif action == "model":
                    model_target = selected_workspace.get("model_target", "responded")
                    if model_target not in {"responded", "converted"}:
                        model_target = "responded"
                    command.extend(("--target", model_target))
                result = subprocess.run(
                    command, cwd=ROOT,
                    capture_output=True, text=True, timeout=150, check=False,
                )
                output = result.stdout.strip() or result.stderr.strip() or "Completed without console output."
                status = "Completed" if result.returncode == 0 else f"Failed (exit {result.returncode})"
                if result.returncode == 0:
                    progress[action] = True
                    save_progress(progress)
                self.redirect_home(f"{title}: {status}\n\n{output[-5000:]}")
            except subprocess.TimeoutExpired:
                self.redirect_home(f"{title}: timed out. Check the PyCharm Run output and try again.")
            return
        self.respond(404, b"Not found", "text/plain; charset=utf-8")

    def redirect_home(self, message: str) -> None:
        content = page(message)
        self.respond(200, content)

    def log_message(self, format: str, *args: object) -> None:
        print("[local-app] " + (format % args))


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Campaign Analytics Workspace running at http://127.0.0.1:{PORT}")
    print("Press Ctrl+C in the PyCharm Run window to stop it.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nWorkspace app stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
