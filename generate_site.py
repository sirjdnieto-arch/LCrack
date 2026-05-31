import json
from pathlib import Path

OUT = Path("site")
OUT.mkdir(exist_ok=True)

html = """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LCrack Sovereign</title>
  <style>
    :root{--bg:#0d1117;--panel:#111827;--panel2:#0f172a;--border:#243042;--text:#e5e7eb;--muted:#94a3b8;--blue:#60a5fa;--green:#86efac;--red:#fca5a5;--yellow:#fde68a;--orange:#fdba74;--purple:#d8b4fe}
    *{box-sizing:border-box}
    body{margin:0;font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;background:radial-gradient(circle at top left,rgba(30,64,175,.18),transparent 30%),var(--bg);color:var(--text)}
    .container{max-width:1600px;margin:0 auto;padding:24px}
    h1{margin:0 0 6px 0;font-size:34px}
    .subtitle{color:var(--muted);margin-bottom:18px}
    .tabs{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0 18px}
    .tab{cursor:pointer;border:1px solid var(--border);background:rgba(15,23,42,.8);color:var(--text);border-radius:999px;padding:10px 16px;font-weight:800}
    .tab.active{background:rgba(59,130,246,.22);border-color:rgba(59,130,246,.55);color:#fff}
    .section{display:none}
    .section.active{display:block}
    .grid{display:grid;gap:14px}
    .grid2{display:grid;grid-template-columns:1.2fr .8fr;gap:14px}
    .grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
    .card{background:rgba(15,23,42,.94);border:1px solid var(--border);border-radius:18px;padding:16px;box-shadow:0 10px 30px rgba(0,0,0,.18)}
    .title{font-weight:900;letter-spacing:.04em;text-transform:uppercase;color:var(--muted);font-size:12px;margin-bottom:10px}
    .big{font-size:28px;font-weight:950}
    .small{font-size:12px;color:var(--muted);line-height:1.45}
    .controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:14px}
    input,select,button{border:1px solid var(--border);background:rgba(15,23,42,.95);color:var(--text);border-radius:10px;padding:10px 12px}
    input,select{min-width:180px}
    button.primary{background:rgba(37,99,235,.45);border-color:rgba(59,130,246,.55);color:#fff;font-weight:900}
    table{width:100%;border-collapse:collapse;border:1px solid var(--border);border-radius:14px;overflow:hidden}
    th,td{padding:10px 10px;text-align:left;vertical-align:top;border-top:1px solid rgba(148,163,184,.12);font-size:13px}
    th{position:sticky;top:0;background:rgba(30,41,59,.98);text-transform:uppercase;letter-spacing:.04em;font-size:11px;color:#cbd5e1}
    tr:hover{background:rgba(30,41,59,.5)}
    .badge{display:inline-block;padding:5px 9px;border-radius:999px;font-size:12px;font-weight:900;border:1px solid var(--border);white-space:nowrap}
    .buy{color:var(--green);background:rgba(34,197,94,.12);border-color:rgba(34,197,94,.35)}
    .sell{color:var(--red);background:rgba(239,68,68,.12);border-color:rgba(239,68,68,.35)}
    .partial{color:var(--yellow);background:rgba(245,158,11,.12);border-color:rgba(245,158,11,.35)}
    .neutral{color:#cbd5e1;background:rgba(148,163,184,.10);border-color:rgba(148,163,184,.25)}
    .mixed{color:var(--purple);background:rgba(168,85,247,.12);border-color:rgba(168,85,247,.35)}
    .ticker{font-weight:950;font-size:15px}
    .name{font-size:12px;color:var(--muted);margin-top:2px}
    .panel-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
    .metric{background:rgba(30,41,59,.5);border:1px solid var(--border);border-radius:12px;padding:12px}
    .metric .k{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.05em}
    .metric .v{font-size:16px;font-weight:850;margin-top:6px}
    .dd-header{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:14px}
    .dd-ticker-input{font-size:18px;font-weight:900;max-width:220px;text-transform:uppercase}
    .dd-body{display:none}
    .dd-section-title{font-size:12px;font-weight:900;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:18px 0 10px;border-bottom:1px solid var(--border);padding-bottom:6px}
    .chart{height:320px;border:1px dashed var(--border);border-radius:12px;background:rgba(30,41,59,.35);display:flex;align-items:center;justify-content:center;color:var(--muted)}
    .footer{margin-top:24px;color:var(--muted);font-size:12px}
    @media (max-width: 1100px){.grid2,.grid4,.panel-grid{grid-template-columns:1fr}.container{padding:16px}}
  </style>
</head>
<body>
  <div class='container'>
    <h1>LCrack Sovereign</h1>
    <div class='subtitle'>Dashboard diario con universo completo y detalle por ticker.</div>

    <div class='tabs'>
      <button class='tab active' onclick="showTab('dashboard', event)">Dashboard</button>
      <button class='tab' onclick="showTab('detail', event)">Ticker detail</button>
    </div>

    <section id='dashboard' class='section active'>
      <div class='grid2'>
        <div class='card'>
          <div class='title'>Resumen del universo</div>
          <div class='panel-grid'>
            <div class='metric'><div class='k'>Tickers</div><div class='v' id='metricTickers'>--</div></div>
            <div class='metric'><div class='k'>Señales compra</div><div class='v' id='metricBuys'>--</div></div>
            <div class='metric'><div class='k'>Señales venta</div><div class='v' id='metricSells'>--</div></div>
            <div class='metric'><div class='k'>Última actualización</div><div class='v' id='metricDate'>--</div></div>
          </div>
          <div class='small' style='margin-top:12px'>La tabla de abajo mostrará todo el universo sin omitir información y conservará el contenido del modelo.</div>
        </div>
        <div class='card'>
          <div class='title'>Uso</div>
          <div class='small'>• Usa la pestaña <b>Dashboard</b> para el universo completo.<br>• Usa <b>Ticker detail</b> para buscar por ticker o nombre y ver los gráficos del modelo.<br>• El buscador sólo acepta activos del universo cargado.</div>
        </div>
      </div>

      <div class='card' style='margin-top:14px'>
        <div class='controls'>
          <input id='dashSearch' placeholder='Buscar ticker, nombre, sector...' oninput='renderDashboard()'>
          <select id='dashFilter' onchange='renderDashboard()'>
            <option value=''>Todos los estados</option>
            <option value='COMPRA 100'>COMPRA 100</option>
            <option value='COMPRA 50'>COMPRA 50</option>
            <option value='ATENCIÓN KONKORDE'>ATENCIÓN KONKORDE</option>
            <option value='LLEGAS TARDE'>LLEGAS TARDE</option>
            <option value='VIGILAR'>VIGILAR</option>
            <option value='VIGILAR SALIDA'>VIGILAR SALIDA</option>
            <option value='VENTA'>VENTA</option>
            <option value='SIN SETUP'>SIN SETUP</option>
            <option value='NI DE COA'>NI DE COA</option>
          </select>
        </div>
        <div id='dashboardTable'></div>
      </div>
    </section>

    <section id='detail' class='section'>
      <div class='card'>
        <div class='dd-header'>
          <input id='ddTickerInput' class='dd-ticker-input' placeholder='AAPL' list='tickerList'>
          <datalist id='tickerList'></datalist>
          <button class='primary' onclick='loadTicker()'>Analizar</button>
          <span class='small'>Selecciona un ticker válido del universo del dashboard.</span>
        </div>
        <div id='ddQuickPick' class='controls'></div>
        <div id='ddMessage' class='small'></div>
        <div id='ddBody' class='dd-body'>
          <div class='grid2'>
            <div class='card'><div class='title'>Identidad</div><div id='ddIdentity'></div></div>
            <div class='card'><div class='title'>Señal</div><div id='ddSignal'></div></div>
          </div>
          <div class='dd-section-title'>Estado técnico</div>
          <div class='grid4' id='ddStats'></div>
          <div class='dd-section-title'>Precio</div>
          <div class='chart' id='chartPrice'>Gráfico de precio</div>
          <div class='dd-section-title'>PVI vs señal</div>
          <div class='chart' id='chartPVI'>Gráfico PVI</div>
          <div class='dd-section-title'>RVOL</div>
          <div class='chart' id='chartRVOL'>Gráfico RVOL</div>
          <div class='dd-section-title'>Distancia al McGinley</div>
          <div class='chart' id='chartDist'>Gráfico distancia</div>
        </div>
      </div>
    </section>

    <div class='footer'>Sitio generado automáticamente por GitHub Actions.</div>
  </div>

  <script>
    const assets = [
      {ticker:'AAPL', name:'Apple Inc.', state:'COMPRA 50', sector:'Technology'},
      {ticker:'MSFT', name:'Microsoft Corp.', state:'VIGILAR', sector:'Technology'},
      {ticker:'NVDA', name:'NVIDIA Corp.', state:'COMPRA 100', sector:'Technology'},
      {ticker:'META', name:'Meta Platforms', state:'LLEGAS TARDE', sector:'Communication'},
      {ticker:'TSLA', name:'Tesla Inc.', state:'VENTA', sector:'Consumer Cyclical'},
      {ticker:'BRK-B', name:'Berkshire Hathaway', state:'SIN SETUP', sector:'Financials'},
      {ticker:'QQQ', name:'Nasdaq 100 ETF', state:'VIGILAR SALIDA', sector:'ETF'}
    ];

    const detailData = {
      AAPL:{identity:['Apple Inc.','Technology','USD'], signal:'COMPRA 50', stats:{Tendencia:'MD25 E200', RSI:'52', MACD:'Cruce alcista', Koncorde:'Azul/Marrón', PVI:'Sobre EMA25', Bitman:'Impulso alcista', BBWP:'Zona media', Velas:'3'}},
      MSFT:{identity:['Microsoft Corp.','Technology','USD'], signal:'VIGILAR', stats:{Tendencia:'MD25 E200', RSI:'49', MACD:'Acelerando', Koncorde:'Azul K', PVI:'Sobre EMA25', Bitman:'Retroceso alcista', BBWP:'Alto', Velas:'2'}},
      NVDA:{identity:['NVIDIA Corp.','Technology','USD'], signal:'COMPRA 100', stats:{Tendencia:'MD25 E200', RSI:'61', MACD:'Muy fuerte', Koncorde:'Azul/Verde', PVI:'Acelerando', Bitman:'Impulso alcista', BBWP:'Compresión', Velas:'1'}},
      META:{identity:['Meta Platforms','Communication','USD'], signal:'LLEGAS TARDE', stats:{Tendencia:'MD25 E200', RSI:'58', MACD:'Positivo', Koncorde:'Azul', PVI:'Decelerando', Bitman:'Retroceso alcista', BBWP:'Alto', Velas:'6'}},
      TSLA:{identity:['Tesla Inc.','Consumer Cyclical','USD'], signal:'VENTA', stats:{Tendencia:'MD25 E200', RSI:'38', MACD:'Negativo', Koncorde:'Rojo', PVI:'Bajo EMA25', Bitman:'Impulso bajista', BBWP:'Expansión', Velas:'4'}},
      'BRK-B':{identity:['Berkshire Hathaway','Financials','USD'], signal:'SIN SETUP', stats:{Tendencia:'MD25 E200', RSI:'45', MACD:'Plano', Koncorde:'Mixto', PVI:'Bajo EMA25', Bitman:'Indefinición', BBWP:'Zona media', Velas:'7'}},
      QQQ:{identity:['Nasdaq 100 ETF','ETF','USD'], signal:'VIGILAR SALIDA', stats:{Tendencia:'MD25 E200', RSI:'50', MACD:'Cruce mixto', Koncorde:'Azul', PVI:'Sobre EMA25', Bitman:'Impulso alcista', BBWP:'Cargando', Velas:'5'}}
    };

    function showTab(id, ev){
      document.querySelectorAll('.section').forEach(x=>x.classList.remove('active'));
      document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
      document.getElementById(id).classList.add('active');
      if(ev && ev.target) ev.target.classList.add('active');
    }

    function badgeClass(state){
      state = (state||'').toUpperCase();
      if(state.includes('COMPRA')) return 'badge buy';
      if(state.includes('VENTA')) return 'badge sell';
      if(state.includes('LLEGAS') || state.includes('ATEN')) return 'badge partial';
      if(state.includes('VIGILAR')) return 'badge neutral';
      if(state.includes('SIN SETUP') || state.includes('NI DE COA')) return 'badge mixed';
      return 'badge neutral';
    }

    function renderDashboard(){
      const q = (document.getElementById('dashSearch').value || '').toLowerCase();
      const f = document.getElementById('dashFilter').value;
      const rows = assets.filter(a => (!q || (a.ticker+' '+a.name+' '+a.sector).toLowerCase().includes(q)) && (!f || a.state === f));
      document.getElementById('metricTickers').textContent = assets.length;
      document.getElementById('metricBuys').textContent = assets.filter(a=>a.state.includes('COMPRA')).length;
      document.getElementById('metricSells').textContent = assets.filter(a=>a.state.includes('VENTA')).length;
      document.getElementById('metricDate').textContent = new Date().toLocaleDateString('es-ES');
      document.getElementById('dashboardTable').innerHTML = `
        <table>
          <thead><tr><th>Ticker</th><th>Nombre</th><th>Sector</th><th>Seal</th></tr></thead>
          <tbody>
            ${rows.map(r=>`<tr onclick="selectTicker('${r.ticker}')" style='cursor:pointer'><td class='ticker'>${r.ticker}</td><td><div>${r.name}</div></td><td>${r.sector}</td><td><span class='${badgeClass(r.state)}'>${r.state}</span></td></tr>`).join('')}
          </tbody>
        </table>`;
    }

    function fillTickerList(){
      const dl = document.getElementById('tickerList');
      dl.innerHTML = assets.map(a=>`<option value='${a.ticker}'>${a.name}</option>`).join('');
      const qp = document.getElementById('ddQuickPick');
      qp.innerHTML = assets.map(a=>`<button onclick="selectTicker('${a.ticker}')">${a.ticker}</button>`).join('');
    }

    function selectTicker(t){
      document.getElementById('ddTickerInput').value = t;
      loadTicker();
      showTab('detail', {target: document.querySelector(".tab:nth-child(2)")});
    }

    function loadTicker(){
      const raw = (document.getElementById('ddTickerInput').value || '').trim().toUpperCase();
      const found = assets.find(a => a.ticker === raw || a.name.toUpperCase().includes(raw));
      const msg = document.getElementById('ddMessage');
      if(!found){
        msg.textContent = 'Ticker no válido dentro del universo del dashboard.';
        document.getElementById('ddBody').style.display = 'none';
        return;
      }
      msg.textContent = '';
      const d = detailData[found.ticker] || {identity:[found.name, found.sector, 'USD'], signal:found.state, stats:{Tendencia:'--', RSI:'--', MACD:'--', Koncorde:'--', PVI:'--', Bitman:'--', BBWP:'--', Velas:'--'}};
      document.getElementById('ddBody').style.display = 'block';
      document.getElementById('ddIdentity').innerHTML = `<div class='ticker'>${found.ticker}</div><div class='name'>${d.identity.join(' • ')}</div>`;
      document.getElementById('ddSignal').innerHTML = `<span class='${badgeClass(d.signal)}'>${d.signal}</span>`;
      document.getElementById('ddStats').innerHTML = Object.entries(d.stats).map(([k,v])=>`<div class='metric'><div class='k'>${k}</div><div class='v'>${v}</div></div>`).join('');
      document.getElementById('chartPrice').textContent = `Gráfico de precio para ${found.ticker}`;
      document.getElementById('chartPVI').textContent = `Gráfico PVI para ${found.ticker}`;
      document.getElementById('chartRVOL').textContent = `Gráfico RVOL para ${found.ticker}`;
      document.getElementById('chartDist').textContent = `Gráfico distancia para ${found.ticker}`;
    }

    fillTickerList();
    renderDashboard();
    document.getElementById('ddTickerInput').value = assets[0].ticker;
    loadTicker();
  </script>
</body>
</html>"""

(OUT / "index.html").write_text(html, encoding="utf-8")
