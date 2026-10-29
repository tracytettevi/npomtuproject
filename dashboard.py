"""Build a dependency-free HTML dashboard from the campaign SQLite database."""

from __future__ import annotations

import html
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "campaigns.sqlite"
OUTPUT_DIR = ROOT / "outputs"
OUTPUT_PATH = OUTPUT_DIR / "dashboard.html"


def fetch_all(connection: sqlite3.Connection, query: str) -> list[dict]:
    connection.row_factory = sqlite3.Row
    return [dict(row) for row in connection.execute(query)]


def load_dashboard_data() -> dict:
    if not DB_PATH.exists() or DB_PATH.stat().st_size == 0:
        raise FileNotFoundError("campaigns.sqlite is missing or empty. Run data.py first.")
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        totals = dict(connection.execute("""SELECT
            (SELECT COUNT(*) FROM customers) AS customers,
            (SELECT COUNT(*) FROM campaigns) AS campaigns,
            COUNT(*) AS messages,
            SUM(CASE WHEN delivery_status='delivered' THEN 1 ELSE 0 END) AS delivered,
            SUM(CASE WHEN delivery_status='delivered' THEN responded ELSE 0 END) AS responses,
            SUM(CASE WHEN delivery_status='delivered' THEN converted ELSE 0 END) AS conversions
            FROM messages""").fetchone())
        campaigns = fetch_all(connection, """SELECT c.campaign_id, c.campaign_name,
            c.offer_type, c.send_date, COUNT(m.message_id) AS sent,
            SUM(CASE WHEN m.delivery_status='delivered' THEN 1 ELSE 0 END) AS delivered,
            SUM(CASE WHEN m.delivery_status='delivered' THEN m.responded ELSE 0 END) AS responses,
            SUM(CASE WHEN m.delivery_status='delivered' THEN m.converted ELSE 0 END) AS conversions,
            1.0*SUM(CASE WHEN m.delivery_status='delivered' THEN m.responded ELSE 0 END)/
              NULLIF(SUM(CASE WHEN m.delivery_status='delivered' THEN 1 ELSE 0 END),0) AS response_rate,
            1.0*SUM(CASE WHEN m.delivery_status='delivered' THEN m.converted ELSE 0 END)/
              NULLIF(SUM(CASE WHEN m.delivery_status='delivered' THEN 1 ELSE 0 END),0) AS conversion_rate
            FROM campaigns c JOIN messages m ON m.campaign_id=c.campaign_id
            GROUP BY c.campaign_id,c.campaign_name,c.offer_type,c.send_date ORDER BY c.send_date""")
        segments = fetch_all(connection, """SELECT cu.segment,
            SUM(CASE WHEN m.delivery_status='delivered' THEN 1 ELSE 0 END) AS delivered,
            SUM(CASE WHEN m.delivery_status='delivered' THEN m.responded ELSE 0 END) AS responses,
            SUM(CASE WHEN m.delivery_status='delivered' THEN m.converted ELSE 0 END) AS conversions,
            1.0*SUM(CASE WHEN m.delivery_status='delivered' THEN m.responded ELSE 0 END)/
              NULLIF(SUM(CASE WHEN m.delivery_status='delivered' THEN 1 ELSE 0 END),0) AS response_rate,
            1.0*SUM(CASE WHEN m.delivery_status='delivered' THEN m.converted ELSE 0 END)/
              NULLIF(SUM(CASE WHEN m.delivery_status='delivered' THEN 1 ELSE 0 END),0) AS conversion_rate
            FROM customers cu JOIN messages m ON m.customer_id=cu.customer_id
            GROUP BY cu.segment ORDER BY response_rate DESC""")
        offers = fetch_all(connection, """SELECT c.offer_type,
            SUM(CASE WHEN m.delivery_status='delivered' THEN 1 ELSE 0 END) AS delivered,
            SUM(CASE WHEN m.delivery_status='delivered' THEN m.responded ELSE 0 END) AS responses,
            SUM(CASE WHEN m.delivery_status='delivered' THEN m.converted ELSE 0 END) AS conversions,
            1.0*SUM(CASE WHEN m.delivery_status='delivered' THEN m.responded ELSE 0 END)/
              NULLIF(SUM(CASE WHEN m.delivery_status='delivered' THEN 1 ELSE 0 END),0) AS response_rate,
            1.0*SUM(CASE WHEN m.delivery_status='delivered' THEN m.converted ELSE 0 END)/
              NULLIF(SUM(CASE WHEN m.delivery_status='delivered' THEN 1 ELSE 0 END),0) AS conversion_rate
            FROM campaigns c JOIN messages m ON m.campaign_id=c.campaign_id
            GROUP BY c.offer_type ORDER BY response_rate DESC""")
    report_path = OUTPUT_DIR / "model_report.json"
    model = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else None
    insight_path = OUTPUT_DIR / "ai_insights.txt"
    ai_insights = insight_path.read_text(encoding="utf-8").strip() if insight_path.exists() else ""
    return {"totals": totals, "campaigns": campaigns, "segments": segments,
            "offers": offers, "model": model, "ai_insights": ai_insights,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}


def build_dashboard(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    model = data["model"]
    if model:
        m = model["test_metrics"]
        target = html.escape(model.get("prediction_target", "campaign outcome"))
        drivers = model.get("top_model_drivers", [])
        driver_html = (
            "<h4>Model feature associations</h4><ul>"
            + "".join(
                f"<li>{html.escape(item['feature'])}: {html.escape(item['direction'])} "
                f"(coefficient {item['coefficient']:+.4f})</li>"
                for item in drivers[:5]
            )
            + "</ul><p class=\"muted\">These are associations learned by this model, not evidence of cause.</p>"
            if drivers else "<p class=\"note\">Feature explanations are not available yet.</p>"
        )
        ml_html = f"""<div class="metric-grid compact">
          <div class="metric"><span>Test ROC AUC</span><strong>{m['roc_auc']:.3f}</strong></div>
          <div class="metric"><span>Test precision</span><strong>{m['precision']:.1%}</strong></div>
          <div class="metric"><span>Test recall</span><strong>{m['recall']:.1%}</strong></div>
          <div class="metric"><span>Test F1</span><strong>{m['f1_score']:.3f}</strong></div></div>
          <p class="note"><b>Interpretation:</b> ROC AUC near 0.5 means the model ranks responders only slightly better than chance on these held-out campaigns. Treat it as a pipeline demonstration, not a campaign decision tool.</p>
          <p class="muted">Predicting {target} · {m['records']:,} delivered messages in test set · train through {html.escape(model['train_through_date'])} · test from {html.escape(model['test_from_date'])} · threshold {m['decision_threshold']:.2f} selected using training data</p>
          {driver_html}"""
    else:
        ml_html = '<p class="note">Model report not found. Run <code>model.py</code> to add evaluation metrics.</p>'
    if data.get("ai_insights"):
        ai_html = f'<div class="ai-answer">{html.escape(data["ai_insights"])}</div><p class="muted">AI-generated from aggregate synthetic results. Review against the source metrics before acting.</p>'
    else:
        ai_html = '<p class="note">No Snwolley brief is available yet. The local key is configured; run <code>snwolley_agent.py</code> when the Snwolley service is reachable, then rebuild this dashboard.</p>'
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Campaign Analytics | Npontu Assignment</title><style>
:root{{--ink:#172b3a;--muted:#667887;--line:#e3eaf0;--paper:#f4f7fa;--white:#fff;--teal:#087f8c;--blue:#3666a8}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
header{{background:#122d40;color:white;padding:34px max(24px,calc((100vw - 1180px)/2)) 28px}}header .eyebrow{{text-transform:uppercase;letter-spacing:.13em;font-size:11px;color:#8ed2d4;font-weight:700}}h1{{font-size:30px;line-height:1.15;margin:9px 0}}header p{{margin:0;color:#c4d2dc}}main{{max-width:1180px;margin:26px auto;padding:0 22px 44px}}
.metric-grid{{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:14px}}.metric-grid.compact{{grid-template-columns:repeat(4,minmax(0,1fr));margin:18px 0}}.metric,.panel{{background:var(--white);border:1px solid var(--line);border-radius:12px;box-shadow:0 2px 8px #1c3b5010}}.metric{{padding:17px 18px}}.metric span{{display:block;color:var(--muted);font-size:12px}}.metric strong{{display:block;font-size:25px;margin-top:4px;letter-spacing:-.03em}}.section-title{{font-size:20px;margin:30px 0 12px}}.grid-two{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}.panel{{padding:19px 20px;min-width:0}}.panel h3{{margin:0 0 4px;font-size:16px}}.panel .sub{{margin:0 0 17px;color:var(--muted);font-size:12px}}.bar-row{{display:grid;grid-template-columns:minmax(100px,145px) 1fr 52px;gap:12px;align-items:center;margin:12px 0;font-size:13px}}.bar-track{{height:10px;border-radius:8px;background:#edf1f4;overflow:hidden}}.bar-fill{{height:100%;background:var(--teal);border-radius:8px}}.bar-value{{font-variant-numeric:tabular-nums;text-align:right;font-weight:650}}.line-chart{{width:100%;height:245px;overflow:visible}}.line-chart .axis{{stroke:#dfe7ed;stroke-width:1}}.line-chart .line{{fill:none;stroke:var(--blue);stroke-width:3}}.line-chart .dot{{fill:var(--blue);stroke:white;stroke-width:2}}.line-chart text{{fill:var(--muted);font-size:10px}}.table-wrap{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;font-size:13px;white-space:nowrap}}th,td{{padding:10px 9px;border-bottom:1px solid var(--line);text-align:right}}th:first-child,td:first-child{{text-align:left}}th{{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}}.note{{background:#fff6e8;border:1px solid #f0d9ad;color:#67481b;padding:12px 14px;border-radius:8px;font-size:13px}}.ai-answer{{white-space:pre-wrap;font-size:14px;line-height:1.65;color:#23394a}}.muted,footer{{color:var(--muted);font-size:12px}}footer{{padding:22px 0 6px}}.pill{{display:inline-block;background:#e8f3f4;color:#17616a;border-radius:30px;padding:4px 9px;font-size:11px;font-weight:650}}@media(max-width:800px){{.metric-grid{{grid-template-columns:repeat(2,1fr)}}.grid-two{{grid-template-columns:1fr}}.metric-grid.compact{{grid-template-columns:repeat(2,1fr)}}}}@media(max-width:460px){{main{{padding:0 14px 30px}}header{{padding-left:18px;padding-right:18px}}.bar-row{{grid-template-columns:95px 1fr 45px;gap:7px}}}}
</style></head><body><header><div class="eyebrow">Intelligent Systems Services · Assignment</div><h1>Campaign Analytics</h1><p>SMS campaign performance, customer response patterns, and model evaluation</p></header><main>
<div id="summary" class="metric-grid"></div><h2 class="section-title">Performance patterns</h2><div class="grid-two">
<section class="panel"><h3>Response rate by customer segment</h3><p class="sub">Responses ÷ delivered messages</p><div id="segment-chart"></div></section>
<section class="panel"><h3>Response rate by offer</h3><p class="sub">Compare offer types across delivered messages</p><div id="offer-chart"></div></section>
<section class="panel"><h3>Campaign response over time</h3><p class="sub">Each point is one campaign; exact values are in the table</p><svg class="line-chart" id="campaign-chart" viewBox="0 0 700 245" role="img" aria-label="Campaign response rates over time"></svg></section>
<section class="panel" id="part-4"><h3>Part 4 · Machine learning results</h3><p class="sub">Logistic regression evaluated on later campaigns</p>{ml_html}</section>
<section class="panel" id="part-5"><h3>Part 5 · Snwolley Agent insight brief</h3><p class="sub">AI narrative grounded in the displayed aggregate results</p>{ai_html}</section></div>
<h2 class="section-title">Campaign detail</h2><section class="panel table-wrap"><table><thead><tr><th>Campaign</th><th>Date</th><th>Offer</th><th>Delivered</th><th>Responses</th><th>Response rate</th><th>Conversions</th><th>Conversion rate</th></tr></thead><tbody id="campaign-table"></tbody></table></section>
<footer>Source: synthetic project database · Dashboard generated {html.escape(data['generated_at'])} · Results describe this dataset only.</footer></main>
<script>const DATA={payload};const pct=x=>x==null?'—':(x*100).toFixed(1)+'%';const number=x=>Number(x||0).toLocaleString();
const t=DATA.totals,d=Number(t.delivered||0);document.getElementById('summary').innerHTML=[['Customers',number(t.customers)],['Campaigns',number(t.campaigns)],['Messages sent',number(t.messages)],['Delivered',number(d)],['Response rate',pct(d?Number(t.responses)/d:0)]].map(([a,b])=>`<div class="metric"><span>${{a}}</span><strong>${{b}}</strong></div>`).join('');
function bars(target,items,label){{const max=Math.max(...items.map(x=>Number(x.response_rate||0)),.01);document.getElementById(target).innerHTML=items.map(x=>`<div class="bar-row"><span>${{x[label]}}</span><div class="bar-track"><div class="bar-fill" style="width:${{Math.max(2,Number(x.response_rate||0)/max*100)}}%"></div></div><span class="bar-value">${{pct(x.response_rate)}}</span></div><div class="muted" style="margin:-8px 0 12px 157px">${{number(x.responses)}} responses · ${{number(x.delivered)}} delivered</div>`).join('')||'<p class="muted">No records available.</p>'}}bars('segment-chart',DATA.segments,'segment');bars('offer-chart',DATA.offers,'offer_type');
const cs=DATA.campaigns,svg=document.getElementById('campaign-chart'),W=700,H=245,L=42,R=12,T=18,B=34,maxRate=Math.max(.2,...cs.map(c=>Number(c.response_rate||0)));let markup='';for(let i=0;i<5;i++){{const y=T+(H-T-B)*i/4;markup+=`<line class="axis" x1="${{L}}" y1="${{y}}" x2="${{W-R}}" y2="${{y}}"/><text x="2" y="${{y+4}}">${{(maxRate*(1-i/4)*100).toFixed(0)}}%</text>`}}const pts=cs.map((c,i)=>[L+(W-L-R)*(cs.length===1?0:i/(cs.length-1)),T+(H-T-B)*(1-Number(c.response_rate||0)/maxRate)]);markup+=`<polyline class="line" points="${{pts.map(p=>p.join(',')).join(' ')}}"/>`;pts.forEach((p,i)=>{{markup+=`<circle class="dot" cx="${{p[0]}}" cy="${{p[1]}}" r="4"><title>${{cs[i].campaign_name}}: ${{pct(cs[i].response_rate)}}</title></circle>`}});for(let i=0;i<cs.length;i+=Math.max(1,Math.floor(cs.length/6))){{markup+=`<text x="${{pts[i][0]}}" y="${{H-8}}" text-anchor="middle">${{cs[i].campaign_id}}</text>`}}svg.innerHTML=markup;
document.getElementById('campaign-table').innerHTML=cs.map(c=>`<tr><td>${{c.campaign_name}}</td><td>${{c.send_date}}</td><td><span class="pill">${{c.offer_type}}</span></td><td>${{number(c.delivered)}}</td><td>${{number(c.responses)}}</td><td>${{pct(c.response_rate)}}</td><td>${{number(c.conversions)}}</td><td>${{pct(c.conversion_rate)}}</td></tr>`).join('');</script></body></html>'''


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(build_dashboard(load_dashboard_data()), encoding="utf-8")
    print(f"Dashboard created: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
