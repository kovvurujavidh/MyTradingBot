<div align="center">
  <img src="assets/quiet-luxury-banner.svg" alt="Javidh Algo Pro" width="100%" />
  <h1>Javidh Algo Pro</h1>
  <p><strong>A calm, real-time WinGo research terminal for disciplined session tracking.</strong></p>
  <p>
    <a href="#run-locally">Run locally</a> ·
    <a href="#features">Features</a> ·
    <a href="#deploy">Deploy</a>
  </p>
</div>

<br />

<table>
  <tr>
    <td width="50%"><strong>Quiet luxury UI</strong><br />Ivory day mode, charcoal night mode, Playfair Display headings, and Inter controls.</td>
    <td width="50%"><strong>Live session workflow</strong><br />Period sync, one-click result recording, daily summary, risk progression, and CSV export.</td>
  </tr>
</table>

## Features

- Mobile-first responsive dashboard for 320–430px screens and desktop.
- Website-native period sync dialog with no browser prompt interruption.
- 30S / 1M mode switching with live countdown and freeze warning.
- Recency-weighted Markov analysis and recent-trend ensemble signal.
- Conservative confidence reporting when the evidence is weak.
- Today’s trades, win rate, PnL, staked amount, won-back amount, and balance.
- Reduced-motion support and subtle viewport reveal animations.
- One-click CSV export for session review.

## Run locally

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000).

> This is a research and session-tracking tool. Historical patterns do not guarantee future outcomes. Use responsible limits and never risk money you cannot afford to lose.

## Project map

| Path | Purpose |
| --- | --- |
| `index.html` | Static dashboard (runs entirely in browser) |
| `app.py` | Python server version (local use) |
| `assets/` | Repository presentation assets |
| `netlify.toml` | Netlify deployment config |
| `_redirects` | Netlify routing rules |
| `.gitignore` | Git ignore rules |

## Deploy to Netlify

### Option 1: Drag & Drop
1. Go to [app.netlify.com](https://app.netlify.com)
2. Drag this entire folder onto the deploy area
3. Done! Your site is live

### Option 2: Git Integration (Recommended)
1. Push this repo to GitHub
2. Go to [app.netlify.com](https://app.netlify.com)
3. Click **Add new site** → **Import an existing project**
4. Select GitHub and your repo
5. Click **Deploy site**

### Option 3: Netlify CLI
```bash
npm install -g netlify-cli
netlify login
netlify init
netlify deploy --prod
```

> Your data stays in your browser (localStorage). No server needed.

<details>
<summary><strong>Design direction</strong></summary>
<br />

The interface is intentionally restrained: warm ivory surfaces, deep charcoal type, thin champagne-gold rules, generous whitespace, and soft content emergence as sections enter the viewport.

</details>

<div align="center">
  <sub>Built for clarity, reviewability, and deliberate decisions.</sub>
</div>
