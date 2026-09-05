"""
FinancePulse WebUI - NAS/Docker 可视化配置控制台
提供浏览器端配置编辑、手动运行、资讯预览、推送历史与实时日志
"""
import os
import threading

from flask import Flask, request, jsonify

import config
import history_db
import runtime

app = Flask(__name__)

# 允许通过 WebUI 修改的配置白名单
EDITABLE_FIELDS = {
    "smtp_server": str, "smtp_port": int,
    "sender_email": str, "sender_auth_code": str, "receiver_email": str,
    "news_limit": int, "enable_dedup": bool,
    "sources": list, "categories": list,
    "schedule_times": list,
    "llm_enabled": bool, "llm_api_key": str, "llm_base_url": str,
    "llm_model": str, "llm_reasoning_level": str, "llm_max_concurrent": int,
    "custom_prompt": str,
    "watchlist": str, "flash_enabled": bool,
    "flash_keywords": str, "flash_interval_minutes": int,
}

def _check_auth() -> bool:
    """可选 WebUI 访问令牌 (设置环境变量 WEBUI_PASSWORD 后启用)"""
    token = os.getenv("WEBUI_PASSWORD", "").strip()
    if not token:
        return True
    return request.headers.get("X-WebUI-Token", "") == token

def start_webui(port: int = None):
    """启动 WebUI 服务 (阻塞调用，请放入线程运行)"""
    port = port or int(os.getenv("WEBUI_PORT", "6888"))
    app.run(host="0.0.0.0", port=port, threaded=True, use_reloader=False)

@app.before_request
def _gate():
    if request.path.startswith("/api/") and not _check_auth():
        return jsonify({"ok": False, "msg": "未授权，请配置 X-WebUI-Token"}), 401

@app.route("/")
def index():
    return PAGE_HTML

@app.route("/api/config", methods=["GET"])
def api_get_config():
    cfg = config.load_config()
    return jsonify({"ok": True, "config": cfg})

@app.route("/api/config", methods=["POST"])
def api_save_config():
    data = request.get_json(silent=True) or {}
    cfg = config.load_config()
    applied = []
    for key, expect_type in EDITABLE_FIELDS.items():
        if key not in data:
            continue
        val = data[key]
        try:
            if expect_type is int:
                cfg[key] = max(1, int(val))
            elif expect_type is bool:
                cfg[key] = bool(val)
            elif expect_type is list:
                cfg[key] = list(val)[:10] if key != "schedule_times" else [t.strip() for t in val if t.strip()]
            else:
                cfg[key] = str(val).strip()
            applied.append(key)
        except (ValueError, TypeError):
            return jsonify({"ok": False, "msg": f"字段 {key} 类型错误"}), 400
    if config.save_config(cfg):
        return jsonify({"ok": True, "msg": f"已保存 {len(applied)} 项配置，下次运行生效"})
    return jsonify({"ok": False, "msg": "保存失败，检查 data 目录写权限"}), 500

@app.route("/api/run", methods=["POST"])
def api_run_now():
    import main
    if runtime.state.get("running"):
        return jsonify({"ok": False, "msg": "已有任务在运行中，请稍候"})
    threading.Thread(target=main.run_once, daemon=True).start()
    return jsonify({"ok": True, "msg": "已触发一次完整抓取与推送，请稍候刷新资讯与日志"})

@app.route("/api/status")
def api_status():
    return jsonify({
        "ok": True,
        "state": runtime.state,
        "news_count": len(runtime.latest_news),
    })

@app.route("/api/news")
def api_news():
    return jsonify({"ok": True, "news": runtime.latest_news})

@app.route("/api/history")
def api_history():
    return jsonify({"ok": True, "records": history_db.recent_pushes(limit=30)})

@app.route("/api/logs")
def api_logs():
    return jsonify({"ok": True, "logs": runtime.get_logs(200)})

PAGE_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FinancePulse 控制台</title>
<style>
:root{--blue:#2563eb;--green:#16a34a;--red:#dc2626;--purple:#7c3aed;--bg:#f1f5f9;--card:#fff;--txt:#0f172a;--muted:#64748b;--line:#e2e8f0}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--txt);padding:20px}
.wrap{max-width:960px;margin:0 auto}
h1{font-size:22px;margin-bottom:4px}
.sub{color:var(--muted);font-size:13px;margin-bottom:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.04)}
.card h2{font-size:15px;margin-bottom:12px}
.row{display:flex;align-items:center;margin-bottom:10px;flex-wrap:wrap;gap:6px}
label{width:150px;font-size:13px;color:var(--muted);flex-shrink:0}
input[type=text],input[type=password],input[type=number],select{flex:1;min-width:220px;padding:8px 10px;border:1px solid var(--line);border-radius:8px;font-size:13px}
input:focus,select:focus{outline:2px solid #bfdbfe}
.chk{display:inline-flex;align-items:center;gap:5px;margin-right:14px;font-size:13px}
.chk input{width:15px;height:15px}
.btn{border:none;border-radius:9px;padding:10px 18px;font-size:14px;font-weight:600;cursor:pointer;color:#fff;background:var(--blue)}
.btn:hover{filter:brightness(.92)}
.btn.green{background:var(--green)}.btn.purple{background:var(--purple)}
.btn:disabled{opacity:.5;cursor:not-allowed}
.msg{margin-left:12px;font-size:13px;color:var(--muted)}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{background:#f8fafc;color:var(--muted);text-align:left;padding:7px 8px;border-bottom:2px solid var(--line)}
td{padding:8px;border-bottom:1px solid #f1f5f9;vertical-align:top;line-height:1.5}
.tag{display:inline-block;padding:1px 8px;border-radius:99px;font-size:11px;font-weight:600}
.bull{background:#fee2e2;color:#dc2626}.bear{background:#dcfce7;color:#16a34a}.neu{background:#f1f5f9;color:#64748b}
.watch{color:var(--red);font-weight:700}
.ai{color:var(--purple);background:#f5f3ff;padding:4px 8px;border-radius:6px;display:inline-block}
#logs{background:#0f172a;color:#a5f3fc;font-family:Consolas,monospace;font-size:12px;border-radius:10px;padding:12px;height:230px;overflow-y:auto;white-space:pre-wrap;word-break:break-all}
.status{display:flex;gap:20px;align-items:center;flex-wrap:wrap}
.dot{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:5px}
.hist td{font-size:12px;color:#334155}
.note{font-size:12px;color:var(--muted);margin-top:6px}
</style>
</head>
<body>
<div class="wrap">
  <h1>FinancePulse 控制台</h1>
  <div class="sub">财经早报 · 突发监控 · 微信推送 —— NAS/Docker 可视化配置中心</div>

  <div class="card">
    <div class="status">
      <span><span class="dot" id="st-dot" style="background:#94a3b8"></span><span id="st-txt">空闲</span></span>
      <span style="color:var(--muted);font-size:13px" id="st-last">最近运行: -</span>
      <span style="color:var(--muted);font-size:13px" id="st-count">资讯缓存: 0 条</span>
      <button class="btn green" id="btn-run" onclick="runNow()">立即运行一次</button>
    </div>
  </div>

  <div class="card">
    <h2>邮箱推送与微信提醒</h2>
    <div class="row"><label>发件人 QQ 邮箱</label><input type="text" id="sender_email"></div>
    <div class="row"><label>16 位 SMTP 授权码</label><input type="password" id="sender_auth_code"></div>
    <div class="row"><label>接收邮箱 (微信)</label><input type="text" id="receiver_email" placeholder="多邮箱用逗号隔开即可群发，留空发给自己"></div>
    <div class="row"><label>SMTP 服务器</label><input type="text" id="smtp_server" style="max-width:180px"><span style="width:20px"></span><label style="width:80px">端口</label><input type="number" id="smtp_port" style="max-width:90px"></div>
  </div>

  <div class="card">
    <h2>大模型 AI 分析</h2>
    <div class="row"><label>启用 AI 分析</label><label class="chk"><input type="checkbox" id="llm_enabled">开启后自动提炼利好/利空与投研视点</label></div>
    <div class="row"><label>API Key</label><input type="password" id="llm_api_key"></div>
    <div class="row"><label>Base URL</label><input type="text" id="llm_base_url"></div>
    <div class="row"><label>模型名称</label><input type="text" id="llm_model" style="max-width:220px">
      <label style="width:90px">思考强度</label>
      <select id="llm_reasoning_level"><option value="fast">快速精炼</option><option value="balanced" selected>深度研判 (推荐)</option><option value="deep">长链推演</option></select>
      <label style="width:70px">并发</label>
      <select id="llm_max_concurrent"><option value="1">串行保守</option><option value="2">2 路</option><option value="3">3 路</option></select>
    </div>
    <div class="row"><label>自定义 Prompt</label><input type="text" id="custom_prompt" placeholder="留空使用内置专业投研提示词"></div>
  </div>

  <div class="card">
    <h2>抓取与领域过滤</h2>
    <div class="row"><label>抓取条数</label><input type="number" id="news_limit" style="max-width:90px" min="3" max="50">
      <label style="width:60px">信源</label>
      <label class="chk"><input type="checkbox" id="src_sina">新浪 7x24</label>
      <label class="chk"><input type="checkbox" id="src_wscn">华尔街见闻</label>
      <label class="chk"><input type="checkbox" id="src_cls">财联社</label>
    </div>
    <div class="row"><label>关注领域</label>
      <label class="chk"><input type="checkbox" value="宏观政策" class="cat">宏观政策</label>
      <label class="chk"><input type="checkbox" value="A股市场" class="cat">A股市场</label>
      <label class="chk"><input type="checkbox" value="科技产业" class="cat">科技产业</label>
      <label class="chk"><input type="checkbox" value="大宗商品" class="cat">大宗商品</label>
      <label class="chk"><input type="checkbox" value="全球要闻" class="cat">全球要闻</label>
      <label class="chk"><input type="checkbox" value="社会民生" class="cat">社会民生</label>
    </div>
    <div class="row"><label>跨源去重</label><label class="chk"><input type="checkbox" id="enable_dedup">自动合并多源重复报道</label></div>
    <div class="row"><label>定时推送时点</label><input type="text" id="schedule_times" placeholder="08:30,12:00,16:00"></div>
  </div>

  <div class="card">
    <h2>自选监控与突发要闻</h2>
    <div class="row"><label>自选股/关键词</label><input type="text" id="watchlist" placeholder="逗号分隔，如: 宁德时代,半导体，命中即推送并置顶"></div>
    <div class="row"><label>突发关键词</label><input type="text" id="flash_keywords"></div>
    <div class="row"><label>突发监控</label><label class="chk"><input type="checkbox" id="flash_enabled">开启后台实时监控</label>
      <label style="width:110px">轮询间隔(分)</label><input type="number" id="flash_interval_minutes" style="max-width:80px" min="1" max="10"></div>
  </div>

  <div style="margin-bottom:16px">
    <button class="btn" onclick="saveCfg()" id="btn-save">保存全部配置</button><span class="msg" id="save-msg"></span>
  </div>

  <div class="card">
    <h2>最新资讯预览 <span style="font-weight:400;color:var(--muted);font-size:12px">(点击"立即运行一次"后刷新)</span></h2>
    <div style="overflow-x:auto"><table id="news-tbl"><thead><tr><th>时间</th><th>领域</th><th>要闻</th><th>情绪</th><th>受益/受损板块</th><th>AI 视点</th></tr></thead><tbody></tbody></table></div>
  </div>

  <div class="card">
    <h2>推送历史 (最近 30 条)</h2>
    <table class="hist" id="hist-tbl"><thead><tr><th style="width:110px">时间</th><th style="width:70px">领域</th><th>标题</th></tr></thead><tbody></tbody></table>
  </div>

  <div class="card">
    <h2>运行日志 (每 3 秒自动刷新)</h2>
    <div id="logs">加载中...</div>
  </div>
</div>

<script>
const TOKEN = localStorage.getItem("fp_token") || "";
const H = {"Content-Type":"application/json","X-WebUI-Token":TOKEN};
if (!TOKEN) { const t = prompt("如设置了 WEBUI_PASSWORD 请输入访问令牌 (留空可直接进入):"); if (t!==null) localStorage.setItem("fp_token", t); location.reload(); }

async function jget(u){ const r = await fetch(u, {headers:H}); if(r.status===401){alert("访问令牌错误");throw 0;} return r.json(); }
async function jpost(u,b){ const r = await fetch(u,{method:"POST",headers:H,body:JSON.stringify(b||{})}); return r.json(); }

function esc(s){ return String(s==null?"":s).replace(/[&<>"']/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }

async function loadConfig(){
  const d = await jget("/api/config"); if(!d.ok) return;
  const c = d.config;
  for (const k of ["sender_email","sender_auth_code","receiver_email","smtp_server","llm_api_key","llm_base_url","llm_model","custom_prompt","watchlist","flash_keywords","schedule_times"]) document.getElementById(k).value = c[k]||"";
  document.getElementById("smtp_port").value = c.smtp_port||465;
  document.getElementById("news_limit").value = c.news_limit||20;
  document.getElementById("flash_interval_minutes").value = c.flash_interval_minutes||2;
  document.getElementById("llm_enabled").checked = !!c.llm_enabled;
  document.getElementById("enable_dedup").checked = !!c.enable_dedup;
  document.getElementById("flash_enabled").checked = !!c.flash_enabled;
  document.getElementById("llm_reasoning_level").value = c.llm_reasoning_level||"balanced";
  document.getElementById("llm_max_concurrent").value = c.llm_max_concurrent||1;
  const srcs = c.sources||[]; document.getElementById("src_sina").checked = srcs.includes("sina");
  document.getElementById("src_wscn").checked = srcs.includes("wscn"); document.getElementById("src_cls").checked = srcs.includes("cls");
  document.querySelectorAll(".cat").forEach(x => x.checked = (c.categories||[]).includes(x.value));
}

async function saveCfg(){
  const btn = document.getElementById("btn-save"); btn.disabled = true;
  const cats = [...document.querySelectorAll(".cat:checked")].map(x=>x.value);
  const srcs = [];
  if (document.getElementById("src_sina").checked) srcs.push("sina");
  if (document.getElementById("src_wscn").checked) srcs.push("wscn");
  if (document.getElementById("src_cls").checked) srcs.push("cls");
  const payload = {
    sender_email:v("sender_email"), sender_auth_code:v("sender_auth_code"), receiver_email:v("receiver_email"),
    smtp_server:v("smtp_server"), smtp_port:+v("smtp_port")||465,
    llm_enabled:document.getElementById("llm_enabled").checked, llm_api_key:v("llm_api_key"),
    llm_base_url:v("llm_base_url"), llm_model:v("llm_model"), custom_prompt:v("custom_prompt"),
    llm_reasoning_level:document.getElementById("llm_reasoning_level").value,
    llm_max_concurrent:+document.getElementById("llm_max_concurrent").value,
    news_limit:+v("news_limit")||20, sources:srcs, categories:cats,
    enable_dedup:document.getElementById("enable_dedup").checked,
    schedule_times:v("schedule_times").split(",").map(s=>s.trim()).filter(Boolean),
    watchlist:v("watchlist"), flash_keywords:v("flash_keywords"),
    flash_enabled:document.getElementById("flash_enabled").checked,
    flash_interval_minutes:+v("flash_interval_minutes")||2
  };
  const d = await jpost("/api/config", payload);
  document.getElementById("save-msg").textContent = d.msg || (d.ok ? "已保存" : "保存失败");
  btn.disabled = false; setTimeout(()=>document.getElementById("save-msg").textContent="", 4000);
}
function v(id){ return document.getElementById(id).value.trim(); }

async function runNow(){
  const btn = document.getElementById("btn-run"); btn.disabled = true; btn.textContent = "运行中...";
  const d = await jpost("/api/run");
  if (!d.ok) { alert(d.msg); btn.disabled=false; btn.textContent="立即运行一次"; return; }
  const timer = setInterval(async () => {
    const s = await (await fetch("/api/status", {headers:H})).json();
    if (!s.state.running) { clearInterval(timer); btn.disabled=false; btn.textContent="立即运行一次"; loadNews(); loadLogs(); }
    else pollStatus();
  }, 3000);
}

async function pollStatus(){
  const s = await (await fetch("/api/status", {headers:H})).json();
  const dot = document.getElementById("st-dot"), txt = document.getElementById("st-txt");
  if (s.state.running){ dot.style.background="#f59e0b"; txt.textContent="任务运行中..."; }
  else { dot.style.background="#16a34a"; txt.textContent="空闲"; }
  document.getElementById("st-last").textContent = "最近运行: " + (s.state.last_run || "-");
  document.getElementById("st-count").textContent = "资讯缓存: " + s.news_count + " 条";
}

async function loadNews(){
  const d = await (await fetch("/api/news", {headers:H})).json();
  const tb = document.querySelector("#news-tbl tbody"); tb.innerHTML = "";
  for (const n of (d.news||[])) {
    const s = n.sentiment||"中性"; const cls = s.includes("利好")?"bull":(s.includes("利空")?"bear":"neu");
    tb.innerHTML += `<tr><td>${esc(n.time)}</td><td>${esc(n.tag||"")}</td><td><b>${esc(n.title)}</b>${n.watch_hit?`<div class="watch">⭐ 自选命中: ${esc(n.watch_hit)}</div>`:""}</td><td><span class="tag ${cls}">${esc(s)}${n.impact_degree?" · "+esc(n.impact_degree):""}</span></td><td>${esc(n.beneficiary&&n.beneficiary!=="无"?"益: "+n.beneficiary:"")}${n.adverse&&n.adverse!=="无"?"<br>损: "+esc(n.adverse):""}</td><td>${n.ai_comment?`<span class="ai">${esc(n.ai_comment)}</span>`:esc((n.content||"").slice(0,50))}</td></tr>`;
  }
  if (!(d.news||[]).length) tb.innerHTML = '<tr><td colspan="6" style="color:#94a3b8;text-align:center;padding:20px">暂无数据，点击上方「立即运行一次」</td></tr>';
}

async function loadHist(){
  const d = await (await fetch("/api/history", {headers:H})).json();
  const tb = document.querySelector("#hist-tbl tbody"); tb.innerHTML = "";
  for (const r of (d.records||[])) tb.innerHTML += `<tr><td>${esc((r.pushed_at||"").slice(5,16).replace("T"," "))}</td><td>${esc(r.tag||"")}</td><td>${esc(r.title)}</td></tr>`;
  if (!(d.records||[]).length) tb.innerHTML = '<tr><td colspan="3" style="color:#94a3b8;text-align:center;padding:14px">暂无推送历史</td></tr>';
}

async function loadLogs(){
  const d = await (await fetch("/api/logs", {headers:H})).json();
  const el = document.getElementById("logs");
  el.textContent = (d.logs||[]).join("\n");
  el.scrollTop = el.scrollHeight;
}

loadConfig(); loadNews(); loadHist(); loadLogs(); pollStatus();
setInterval(loadLogs, 3000); setInterval(pollStatus, 5000);
</script>
</body>
</html>"""

if __name__ == "__main__":
    start_webui()
