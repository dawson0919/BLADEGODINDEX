const express = require('express');
const https   = require('https');
const path    = require('path');

const app  = express();
const PORT = process.env.PORT || 7788;

// ── SPX K-line proxy ── (avoids browser CORS on Yahoo Finance)
app.get('/api/spx-klines', (req, res) => {
  const range    = req.query.range || 'max';   // max = full history
  const interval = '1d';
  const options  = {
    hostname: 'query1.finance.yahoo.com',
    path: `/v8/finance/chart/%5EGSPC?interval=${interval}&range=${range}&includePrePost=false&events=div%7Csplit`,
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
      'Accept': 'application/json',
    },
  };

  const request = https.get(options, (yRes) => {
    let raw = '';
    yRes.on('data', chunk => raw += chunk);
    yRes.on('end', () => {
      try {
        const json   = JSON.parse(raw);
        const result = json.chart.result[0];
        const ts     = result.timestamp;
        const q      = result.indicators.quote[0];

        const candles = ts
          .map((t, i) => {
            if (q.open[i] == null) return null;
            // Convert Unix timestamp → YYYY-MM-DD
            const d   = new Date(t * 1000);
            const yy  = d.getUTCFullYear();
            const mm  = String(d.getUTCMonth() + 1).padStart(2, '0');
            const dd  = String(d.getUTCDate()).padStart(2, '0');
            return {
              time:   `${yy}-${mm}-${dd}`,
              open:   +q.open[i].toFixed(2),
              high:   +q.high[i].toFixed(2),
              low:    +q.low[i].toFixed(2),
              close:  +q.close[i].toFixed(2),
              volume: q.volume[i] || 0,
            };
          })
          .filter(Boolean);

        res.json({ candles, total: candles.length });
      } catch (e) {
        res.status(500).json({ error: e.message, raw: raw.slice(0, 300) });
      }
    });
  });

  request.on('error', e => res.status(500).json({ error: e.message }));
  request.setTimeout(10000, () => {
    request.destroy();
    res.status(504).json({ error: 'Yahoo Finance timeout' });
  });
});

// Serve the dashboard folder as static files
app.use(express.static(path.join(__dirname, 'dashboard')));

// Fallback to index.html
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'dashboard', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`🗡️  刀神指標 running at http://localhost:${PORT}`);
});

