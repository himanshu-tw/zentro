# Zentro

> A Loom-inspired screen & video recorder for Linux. Local, fast, no cloud.

Zentro lets you record your screen, webcam, and audio — then save it straight to disk. No account, no upload, no subscription. Built with Electron + Python.

---

## Features

- Screen recording (full screen or window)
- Webcam overlay support
- Microphone audio capture
- Local video processing via Python backend
- Clean, minimal UI

---

## Tech Stack

| Layer | Tech |
|---|---|
| Desktop App | Electron (JS/HTML/CSS) |
| Video Processing | Python |
| Monorepo | npm Workspaces |

---

## Project Structure

```
zentro/
├── apps/
│   └── desktop/        # Electron app
├── packages/
│   └── processor/      # Python video processor
├── shared/             # Shared utilities
└── package.json
```

---

## Getting Started

### Prerequisites

- Node.js v18+
- Python 3.10+
- Linux (primary target)

### Install

```bash
git clone https://github.com/himanshu-tw/zentro.git
cd zentro
npm run install:all
```

`install:all` installs both npm packages and sets up the Python virtualenv automatically.

### Run

```bash
npm start
```

---

## Scripts

| Script | What it does |
|---|---|
| `npm start` | Launch the Electron desktop app |
| `npm run setup:python` | Create venv + install Python deps |
| `npm run install:all` | Full setup (npm + Python) |

---

## Roadmap

- [ ] Recording countdown timer
- [ ] Clip trimming
- [ ] Export to GIF
- [ ] System tray support
- [ ] Keyboard shortcuts

---

## Contributing

PRs welcome. Open an issue first for big changes.

---

## License

MIT