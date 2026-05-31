# LCrack Sovereign

Site estático generado desde el notebook **VOLVEMOS A LCRACK**.
Lógica 100% fiel al notebook original — sin cambios.

## Uso

```bash
pip install -r requirements.txt
python main.py          # ~10-15 min
open site/index.html
```

## Estructura generada

```
site/
├── index.html              ← abre esto en el navegador
└── data/
    └── charts/
        └── AAPL.b64        ← PNG en base64 por ticker
```

## Pestañas

### 📊 Dashboard
Tabla idéntica a `print_dashboard()` del notebook (Cell 0).
- Columnas: Señal · Score · Tendencia · RSI · MACD · Koncorde · PVI · Bitman · Div · BBWP · Velas
- Filtros: por señal (Compra 100%, Compra 50%, Venta…) y búsqueda de ticker
- Ordenación por señal (igual que el notebook) o alfabética
- Clic en ticker → abre el Graficador

### 📈 Graficador
Gráfico multipanel idéntico a `plot_dashboard()` del notebook (Cell 1).
- Panel 0: Velas + McGinley 25 + EMA 200
- Panel 1: ADX + ±DI + Awesome Oscillator
- Panel 2: Blai5 Koncorde (Verde/Marrón/Azul/Media)
- Panel 3: BBWP 13/252
- Panel 4: PVI + EMA 25
- Panel 5: MACD 12/26/9
- Panel 6: RSI 14 + divergencias
- Recuadro informativo + barra de señales (igual que el notebook)

## Tickers

Los 105 tickers exactos de la lista `tickers` del notebook (Cell 0).
Edita `TICKERS` en `main.py` para modificarlos.
