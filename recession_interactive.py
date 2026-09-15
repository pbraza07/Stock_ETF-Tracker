"""Self-contained interactive charts independent of Streamlit's Plotly loader."""
import json
from functools import lru_cache
from plotly.offline import get_plotlyjs
from recession_chart_svg import indicator_svg


@lru_cache(maxsize=1)
def chart_script():
    # Escape closing script tags defensively without fetching any CDN assets.
    return get_plotlyjs().replace('</script', '<\\/script')


def interactive_html(series, records, years=10):
    from recession_indicators import indicator_figure
    fig = indicator_figure(series, records, years)
    fig.update_layout(height=400, dragmode='zoom')
    payload = fig.to_json().replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    config = json.dumps({'responsive':True,'displaylogo':False,'scrollZoom':True,
                        'toImageButtonOptions':{'filename':series,'format':'png'}})
    return '''<!doctype html><html><head><meta charset="utf-8">
<style>body{margin:0;background:#06101A;color:#E2E8F0;font:13px Arial,sans-serif}#fallback svg{width:100%;height:auto}#chart{width:100%;height:400px}#status{padding:6px 12px}</style>
</head><body><div id="fallback">'''+indicator_svg(series,records,years)+'''</div>
<div id="chart" style="display:none"></div><div id="status" role="status">Loading interactive chart…</div>
<script>window.addEventListener('error',function(){document.getElementById('status').textContent='Interactive chart could not load. The static graph remains available.';});</script>
<script>'''+chart_script()+'''</script>
<script>
(function(){
const chart=document.getElementById('chart'), fallback=document.getElementById('fallback'),status=document.getElementById('status');
try {
const figure='''+payload+''';
chart.style.display='block';
Plotly.newPlot(chart,figure.data,figure.layout,'''+config+''').then(function(){
fallback.style.display='none';status.textContent='Hover for values · Drag to zoom · Double-click to reset · Toolbar for pan and download';
}).catch(failed);
} catch(error){failed(error);}
function failed(error){chart.style.display='none';fallback.style.display='block';status.textContent='Interactive chart could not load. The static graph remains available.';}
})();
</script></body></html>'''
