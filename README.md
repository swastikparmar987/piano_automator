<p align="center">
  <h1 align="center">🎹 Piano Automator</h1>
  <p align="center">
    <strong>Play piano sheets automatically in Roblox, Virtual Piano & more.</strong>
  </p>
  <p align="center">
    <a href="#features">Features</a> •
    <a href="#installation">Installation</a> •
    <a href="#usage">Usage</a> •
    <a href="#keyboard-shortcuts">Shortcuts</a> •
    <a href="#contributing">Contributing</a>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/platform-macOS-blue?style=flat-square&logo=apple" />
    <img src="https://img.shields.io/badge/python-3.10+-yellow?style=flat-square&logo=python" />
    <img src="https://img.shields.io/github/license/swastikparmar987/piano_automator?style=flat-square" />
    <img src="https://img.shields.io/github/v/release/swastikparmar987/piano_automator?style=flat-square&color=00d4ff" />
  </p>
</p>

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🎵 **Auto Playback** | Paste any piano sheet and play it automatically with a 3-second countdown |
| 🎮 **Roblox Mode** | Native macOS Quartz key simulation that works in Roblox & fullscreen apps |
| 🎭 **Humanizer Engine** | Realistic timing jitter, key hold variation & chord arpeggiation |
| 🎹 **Sustain Pedal** | Simulated sustain (hold Space) for richer sound |
| 📚 **Song Library** | 35+ pre-loaded songs with searchable browser popup |
| 🗗 **Mini Player** | Compact always-on-top mode for playing while browsing sheets |
| 🎯 **Syntax Highlighting** | Color-coded editor — chords (cyan), notes (green), pauses (purple) |
| ⌨️ **Hotkeys** | Control playback without switching windows |
| 🔁 **Auto Repeat** | Loop songs indefinitely |

## 📦 Installation

### Option 1: Download the App (Recommended)

1. Go to the [**Releases**](https://github.com/swastikparmar987/piano_automator/releases) page
2. Download `Piano.Automator.dmg`
3. Open the DMG → drag **Piano Automator** to **Applications**
4. Grant **Accessibility permission** when prompted:
   - System Settings → Privacy & Security → Accessibility → enable Piano Automator

### Option 2: Run from Source

```bash
git clone https://github.com/swastikparmar987/piano_automator.git
cd piano_automator
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python automator.py
```

## 🚀 Usage

1. **Paste notes** in the editor — e.g. `e [tu] e [tu] | d f g`
2. Click **📥 Parse Notes** (or load from the Song Library)
3. Switch to your piano app (Roblox, Virtual Piano, etc.)
4. Press **`=`** or click **▶ Autoplay** — a 3-second countdown starts, then it plays!

### Note Format

| Syntax | Meaning |
|--------|---------|
| `a` `s` `d` | Individual notes |
| `[asd]` | Chord — all keys pressed simultaneously |
| `\|` | Pause — waits one beat |

## ⌨️ Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `=` | Toggle Autoplay |
| `-` | Play next note (manual mode) |
| `[` | Decrease BPM by 10 |
| `]` | Increase BPM by 10 |

## 🛠 Tech Stack

- **Python 3.10+** with CustomTkinter for the dark-themed UI
- **Quartz CoreGraphics** for native macOS hardware key simulation
- **PyAutoGUI** as fallback for standard key simulation
- **pynput** for global hotkey listening

## 🤝 Contributing

1. Fork the repo
2. Create a branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push (`git push origin feature/amazing`)
5. Open a Pull Request

## 📄 License

[MIT License](LICENSE) — free for personal and commercial use.

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/swastikparmar987">Swastik Parmar</a>
</p>
