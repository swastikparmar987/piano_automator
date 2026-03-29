import customtkinter as ctk
import pyautogui
from pynput import keyboard as pynput_keyboard
import threading
import time
import os
import sys
import re
import random
import json
from tkinter import simpledialog, messagebox
from Quartz.CoreGraphics import CGEventCreateKeyboardEvent, CGEventPost, kCGHIDEventTap

# ─── Performance: disable pyautogui's default 0.1s pause between calls ───
pyautogui.PAUSE = 0
pyautogui.FAILSAFE = False

# ─── Path Resolution (works both in dev and PyInstaller .app) ───
if getattr(sys, 'frozen', False):
    # Running as bundled app — use ~/Documents for user-writable songs
    APP_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = sys._MEIPASS
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = APP_DIR

# ─── App Config ──────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# ─── Colors ──────────────────────────────────────────────────
C = {
    "bg":        "#0e0e1a",
    "card":      "#16162a",
    "card_alt":  "#1c1c36",
    "accent":    "#00d4ff",
    "accent2":   "#7b61ff",
    "text":      "#e0e0e8",
    "dim":       "#6b6b80",
    "success":   "#3ddc84",
    "warn":      "#ffb347",
    "danger":    "#ff4d6a",
    "btn":       "#1e1e3a",
    "btn_hov":   "#2a2a50",
}

# ─── State ───────────────────────────────────────────────────
notes_list, highlight_indices = [], []
current_index, bpm = 0, 400
stop_flag, auto_repeat = False, True
song_name = ""
notes_folder = os.path.join(APP_DIR, "saved_notes")

# Copy bundled songs to user folder on first launch
if getattr(sys, 'frozen', False):
    bundled_songs = os.path.join(BUNDLE_DIR, "saved_notes")
    if os.path.isdir(bundled_songs) and not os.path.isdir(notes_folder):
        import shutil
        shutil.copytree(bundled_songs, notes_folder)
playback_lock = threading.Lock()
is_playing = False
is_mini_mode = False

# Options
opt_humanize = False
opt_sustain = False
opt_roblox = False

# Mac Keycode map for Quartz (ANSI US layout approximations)
MAC_KEYCODES = {
    'a': 0, 's': 1, 'd': 2, 'f': 3, 'h': 4, 'g': 5, 'z': 6, 'x': 7, 'c': 8, 'v': 9, 'b': 11, 'q': 12, 'w': 13,
    'e': 14, 'r': 15, 'y': 16, 't': 17, '1': 18, '2': 19, '3': 20, '4': 21, '6': 22, '5': 23, '=': 24, '9': 25,
    '7': 26, '-': 27, '8': 28, '0': 29, ']': 30, 'o': 31, 'u': 32, '[': 33, 'i': 34, 'p': 35, 'l': 37, 'j': 38,
    '\'': 39, 'k': 40, ';': 41, '\\': 42, ',': 43, '/': 44, 'n': 45, 'm': 46, '.': 47, ' ': 49
}

# ─── Pre-compiled Regexes (avoid recompiling every call) ─────
_RE_PARSE = re.compile(r'\[.*?\]|[a-zA-Z0-9!@#\$%\^\&\*\(\)]|\|| ')
_RE_CHORD = re.compile(r'\[.*?\]')
_RE_PAUSE = re.compile(r'\|')
_RE_SINGLE = re.compile(r'(?<!\[)[a-zA-Z0-9!@#\$%\^\&\*\(\)](?!\])')

# ─── Parsing ─────────────────────────────────────────────────
def parse_input(text):
    chunks = _RE_PARSE.findall(text)
    result, positions = [], []
    index = 0
    for chunk in chunks:
        start, end = index, index + len(chunk)
        index = end
        if chunk.strip() == '':
            continue
        if chunk.startswith('['):
            result.append({'type': 'chord', 'keys': list(chunk[1:-1])})
        elif chunk == '|':
            result.append({'type': 'pause'})
        else:
            result.append({'type': 'single', 'key': chunk})
        positions.append((start, end))
    return result, positions

# ─── Editor Highlighting (debounced — 150ms delay) ───────────
_highlight_pending = None

def _do_highlight():
    """Actual highlighting work — runs only after 150ms of no typing."""
    global _highlight_pending
    _highlight_pending = None
    try:
        inputbox.tag_remove("chord", "1.0", "end")
        inputbox.tag_remove("single", "1.0", "end")
        inputbox.tag_remove("pause", "1.0", "end")
        
        text = inputbox.get("1.0", "end")
        
        for match in _RE_CHORD.finditer(text):
            inputbox.tag_add("chord", f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")
        for match in _RE_PAUSE.finditer(text):
            inputbox.tag_add("pause", f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")
        for match in _RE_SINGLE.finditer(text):
            inputbox.tag_add("single", f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")
    except Exception:
        pass

def on_text_changed(event=None):
    """Debounced: schedules highlighting 150ms from now, cancels previous."""
    global _highlight_pending
    if _highlight_pending is not None:
        root.after_cancel(_highlight_pending)
    _highlight_pending = root.after(150, _do_highlight)

# ─── Humanizer Engine & Playback ────────────────────────────────
def direct_tap(char, hold_duration):
    """Low level Quartz hardware tap with a variable hold duration"""
    is_shift = char.isupper() or char in '!@#$%^&*()'
    char_lower = char.lower()
    
    shift_map = {'!':'1', '@':'2', '#':'3', '$':'4', '%':'5', '^':'6', '&':'7', '*':'8', '(':'9', ')':'0'}
    if char in shift_map:
        char_lower = shift_map[char]
        
    keycode = MAC_KEYCODES.get(char_lower)
    if keycode is None:
        return
        
    # Shift Down
    if is_shift:
        ev_shift_d = CGEventCreateKeyboardEvent(None, 56, True)
        CGEventPost(kCGHIDEventTap, ev_shift_d)
        
    # Key Down
    ev_d = CGEventCreateKeyboardEvent(None, keycode, True)
    CGEventPost(kCGHIDEventTap, ev_d)
    
    # Human variable hold duration for this specific key
    time.sleep(hold_duration)
    
    # Key Up
    ev_u = CGEventCreateKeyboardEvent(None, keycode, False)
    CGEventPost(kCGHIDEventTap, ev_u)
    
    # Shift Up
    if is_shift:
        ev_shift_u = CGEventCreateKeyboardEvent(None, 56, False)
        CGEventPost(kCGHIDEventTap, ev_shift_u)

def tap(key):
    try:
        # A real human holds a key for 40-120ms before releasing it natively.
        hold_time = random.uniform(0.04, 0.12) if opt_humanize else 0.05
        
        if opt_roblox:
            direct_tap(key, hold_time)
        else:
            pyautogui.keyDown(key)
            time.sleep(hold_time)
            pyautogui.keyUp(key)
    except Exception as e:
        print(f"Key error: {e}")

def play_note(note):
    if note['type'] == 'chord':
        # Hyper-Realistic Arpeggiation: Humans don't hit 4 keys at the exact exact exact frame.
        # There's a 10-35ms stagger.
        for i, k in enumerate(note['keys']):
            threading.Thread(target=tap, args=(k,)).start()
            if opt_humanize and i < len(note['keys']) - 1:
                # Micro-roll between fingers striking the chord
                time.sleep(random.uniform(0.010, 0.035))
                
    elif note['type'] == 'single':
        tap(note['key'])
    elif note['type'] == 'pause':
        delay = 60 / bpm
        if opt_humanize: delay += random.uniform(0.03, 0.08) # Pauses fluctuate more
        time.sleep(max(0, delay))

def format_note(note):
    if note['type'] == 'chord': return '[' + ''.join(note['keys']) + ']'
    elif note['type'] == 'single': return note['key']
    elif note['type'] == 'pause': return '|'
    return ''

_last_progress_update = 0

def update_progress(force=False):
    """Throttled UI update — max ~30fps during playback to avoid lag."""
    global _last_progress_update
    now = time.monotonic()
    if not force and (now - _last_progress_update) < 0.033:  # ~30fps cap
        return
    _last_progress_update = now
    
    total = len(notes_list)
    if total == 0:
        progress_bar.set(0)
        progress_label.configure(text="0 / 0")
        now_playing_label.configure(text="—")
        if is_mini_mode:
            mini_progress_bar.set(0)
            mini_now_playing.configure(text="—")
        return
    
    prog = current_index / total
    progress_bar.set(prog)
    progress_label.configure(text=f"{current_index} / {total}")
    
    if current_index < total:
        note_str = f"♪  {format_note(notes_list[current_index])}"
        now_playing_label.configure(text=note_str)
    else:
        now_playing_label.configure(text="✅ Done")
    
    # Only update mini widgets when visible
    if is_mini_mode:
        mini_progress_bar.set(prog)
        if current_index < total:
            mini_now_playing.configure(text=note_str)
        else:
            mini_now_playing.configure(text="✅ Done")

def set_sustain(active):
    try:
        if active:
            if opt_roblox:
                ev = CGEventCreateKeyboardEvent(None, 49, True) # 49 space
                CGEventPost(kCGHIDEventTap, ev)
            else:
                pyautogui.keyDown('space')
        else:
            if opt_roblox:
                ev = CGEventCreateKeyboardEvent(None, 49, False)
                CGEventPost(kCGHIDEventTap, ev)
            else:
                pyautogui.keyUp('space')
    except: pass

def start_countdown_and_play():
    global is_playing, stop_flag
    stop_flag = False
    is_playing = True
    update_play_btn_state()
    root.focus() # blur text box
    
    cd_window = ctk.CTkToplevel(root)
    cd_window.overrideredirect(True)
    cd_window.geometry("200x120")
    cd_window.attributes("-topmost", True)
    cd_window.configure(fg_color=C["bg"])
    
    cd_window.update_idletasks()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    cd_window.geometry(f"+{int(sw/2 - 100)}+{int(sh/2 - 60)}")
    
    lbl = ctk.CTkLabel(cd_window, text="3", font=("Consolas", 80, "bold"), text_color=C["accent"])
    lbl.pack(expand=True)
    
    def count(n):
        if stop_flag:
            cd_window.destroy()
            return
        if n > 0:
            lbl.configure(text=str(n))
            root.after(1000, count, n-1)
        else:
            cd_window.destroy()
            autoplay_loop()
    
    count(3)

def autoplay_loop():
    def run():
        global current_index, stop_flag, is_playing
        if opt_sustain: set_sustain(True)
        
        update_counter = 0
        with playback_lock:
            while not stop_flag and current_index < len(notes_list):
                # Throttle UI updates: only every 3rd note or when pausing
                update_counter += 1
                if update_counter % 3 == 0 or notes_list[current_index]['type'] == 'pause':
                    root.after(0, update_progress)
                
                play_note(notes_list[current_index])
                current_index += 1
                
                delay = 60 / bpm
                if opt_humanize:
                    delay *= random.uniform(0.92, 1.08)
                time.sleep(max(0.005, delay))
                
            stop_flag = False
            is_playing = False
            root.after(0, lambda: update_progress(force=True))
            root.after(0, update_play_btn_state)
            
            if opt_sustain: set_sustain(False)
                
            if current_index >= len(notes_list) and auto_repeat:
                current_index = 0
                root.after(100, autoplay_loop)
                
    threading.Thread(target=run, daemon=True).start()

def toggle_autoplay():
    global stop_flag
    if is_playing:
        stop_playback()
    else:
        start_countdown_and_play()

def play_next():
    global current_index
    if current_index < len(notes_list):
        play_note(notes_list[current_index])
        current_index += 1
        update_progress()
    elif auto_repeat:
        current_index = 0
        update_progress()
    else:
        status_label.configure(text="✅ Manual playback finished.", text_color=C["success"])

def stop_playback():
    global stop_flag, is_playing
    with playback_lock:
        stop_flag = True
        is_playing = False
    
    if opt_sustain: set_sustain(False)
    update_play_btn_state()
    status_label.configure(text="⏹  Stopped.", text_color=C["warn"])

def restart_playback():
    global current_index
    stop_playback()
    time.sleep(0.1)
    current_index = 0
    update_progress()
    status_label.configure(text="⏮  Restarted.", text_color=C["accent"])

def update_play_btn_state():
    text = "⏸  Pause" if is_playing else "▶  Autoplay"
    color = C["warn"] if is_playing else C["accent"]
    play_btn.configure(text=text, fg_color=color)
    mini_play_btn.configure(text=text, fg_color=color)

# ─── Settings ─────────────────────────────────────────
def toggle_opt(var_name, ui_var):
    globals()[var_name] = ui_var.get()

# ─── File Ops ────────────────────────────────────────
def load_notes():
    global notes_list, highlight_indices, current_index, song_name
    stop_playback()
    raw = inputbox.get("1.0", "end").strip()
    if not raw: return
    os.makedirs(notes_folder, exist_ok=True)
    for file in os.listdir(notes_folder):
        try:
            with open(os.path.join(notes_folder, file), 'r', encoding='utf-8') as f:
                if f.read().strip() == raw:
                    notes_list, _ = parse_input(raw)
                    current_index, song_name = 0, os.path.splitext(file)[0]
                    update_progress()
                    refresh_saved_songs()
                    status_label.configure(text=f"🎵  Loaded '{song_name}'", text_color=C["success"])
                    return
        except UnicodeDecodeError: continue
    
    song_name = simpledialog.askstring("Save", "Song Name:") or "Untitled"
    if not song_name: song_name = "Untitled"
    notes_list, _ = parse_input(raw)
    current_index = 0
    save_note_if_unique(raw, song_name)
    update_progress()
    refresh_saved_songs()
    status_label.configure(text=f"🎵  Loaded '{song_name}'", text_color=C["success"])

def save_note_if_unique(raw, name):
    os.makedirs(notes_folder, exist_ok=True)
    with open(os.path.join(notes_folder, f"{name}.txt"), 'w', encoding='utf-8') as f:
        f.write(raw)

def clear_notes():
    inputbox.delete("1.0", "end")
    global notes_list, current_index
    notes_list, current_index = [], 0
    update_progress()
    on_text_changed()

def get_saved_songs():
    os.makedirs(notes_folder, exist_ok=True)
    return [os.path.splitext(f)[0] for f in sorted(os.listdir(notes_folder)) if f.endswith('.txt')]

def refresh_saved_songs():
    songs = get_saved_songs()
    vals = songs if songs else ["No songs saved"]
    saved_songs_menu.configure(values=vals)
    saved_songs_menu.set(vals[0])

def load_saved_song(choice):
    global notes_list, current_index, song_name
    if choice == "No songs saved": return
    filepath = os.path.join(notes_folder, f"{choice}.txt")
    if not os.path.exists(filepath): return
    with open(filepath, 'r', encoding='utf-8') as f: content = f.read()
    inputbox.delete("1.0", "end")
    inputbox.insert("1.0", content)
    on_text_changed()
    notes_list, _ = parse_input(content.strip())
    current_index, song_name = 0, choice
    update_progress()

def delete_saved_song():
    choice = saved_songs_menu.get()
    if choice == "No songs saved": return
    filepath = os.path.join(notes_folder, f"{choice}.txt")
    if os.path.exists(filepath) and messagebox.askyesno("Delete Song", f"Delete '{choice}' permanently?"):
        os.remove(filepath)
        refresh_saved_songs()

# ─── Song Library Browser ─────────────────────────────────────

def open_cloud_library():
    """Browse all saved songs in a searchable popup."""
    popup = ctk.CTkToplevel(root)
    popup.title("📚 Song Library")
    popup.geometry("520x600")
    popup.attributes("-topmost", True)
    popup.configure(fg_color=C["bg"])
    
    # Search bar
    search_frame = ctk.CTkFrame(popup, fg_color=C["card"], corner_radius=10)
    search_frame.pack(fill="x", padx=12, pady=(12, 6))
    ctk.CTkLabel(search_frame, text="🔍", font=("Helvetica", 16)).pack(side="left", padx=(12, 4))
    search_entry = ctk.CTkEntry(search_frame, placeholder_text="Search songs...", font=("Helvetica", 14), fg_color=C["card_alt"], border_width=0, height=36)
    search_entry.pack(side="left", fill="x", expand=True, padx=(0, 12), pady=8)
    
    count_label = ctk.CTkLabel(popup, text="", font=("Helvetica", 12), text_color=C["dim"])
    count_label.pack(anchor="w", padx=16, pady=(4, 2))
    
    scroll_frame = ctk.CTkScrollableFrame(popup, fg_color=C["bg"], corner_radius=10)
    scroll_frame.pack(fill="both", expand=True, padx=12, pady=(2, 12))
    
    def load_song_from_lib(title, filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        inputbox.delete("1.0", "end")
        inputbox.insert("1.0", content)
        on_text_changed()
        global notes_list, current_index, song_name
        notes_list, _ = parse_input(content.strip())
        current_index = 0
        song_name = title
        update_progress()
        refresh_saved_songs()
        status_label.configure(text=f"🎵  Loaded '{title}'", text_color=C["success"])
        popup.destroy()
    
    def populate(filter_text=""):
        for widget in scroll_frame.winfo_children():
            widget.destroy()
        
        os.makedirs(notes_folder, exist_ok=True)
        files = sorted([f for f in os.listdir(notes_folder) if f.endswith('.txt')])
        query = filter_text.lower().strip()
        matched = [f for f in files if query in f.lower()] if query else files
        
        count_label.configure(text=f"📚 {len(matched)} song{'s' if len(matched) != 1 else ''} found")
        
        for fname in matched:
            title = os.path.splitext(fname)[0]
            filepath = os.path.join(notes_folder, fname)
            
            try:
                size = os.path.getsize(filepath)
                size_str = f"{size:,} chars" if size < 10000 else f"{size/1000:.1f}K"
            except:
                size_str = ""
            
            card = ctk.CTkFrame(scroll_frame, fg_color=C["card"], corner_radius=8)
            card.pack(fill="x", pady=3, padx=2)
            
            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.pack(side="left", fill="x", expand=True, padx=12, pady=8)
            ctk.CTkLabel(info_frame, text=f"🎵 {title}", font=("Helvetica", 13, "bold"), text_color=C["text"], anchor="w").pack(anchor="w")
            ctk.CTkLabel(info_frame, text=size_str, font=("Helvetica", 10), text_color=C["dim"], anchor="w").pack(anchor="w")
            
            ctk.CTkButton(card, text="▶ Load", width=70, height=30,
                          fg_color=C["accent"], text_color="#000", hover_color="#00a8cc",
                          font=("Helvetica", 12, "bold"), corner_radius=6,
                          command=lambda t=title, fp=filepath: load_song_from_lib(t, fp)
                          ).pack(side="right", padx=12, pady=8)
        
        if not matched:
            ctk.CTkLabel(scroll_frame, text="No songs match your search.", font=("Helvetica", 13), text_color=C["dim"]).pack(pady=30)
    
    def on_search(*_):
        populate(search_entry.get())
    
    search_entry.bind("<KeyRelease>", on_search)
    populate()


# ─── BPM & Window ─────────────────────────────────────────
def update_bpm(val):
    global bpm
    bpm = int(float(val))
    bpm_value_label.configure(text=f"{bpm} BPM")
    mini_bpm_value.configure(text=f"{bpm} BPM")
    if mini_bpm_slider.get() != bpm: mini_bpm_slider.set(bpm)
    if bpm_slider.get() != bpm: bpm_slider.set(bpm)

def set_speed_preset(s):
    global bpm
    bpm = s
    bpm_slider.set(s); mini_bpm_slider.set(s)
    bpm_value_label.configure(text=f"{s} BPM")
    mini_bpm_value.configure(text=f"{s} BPM")

def toggle_repeat():
    global auto_repeat
    auto_repeat = not auto_repeat
    repeat_btn.configure(text=f"🔁  Repeat: {'ON' if auto_repeat else 'OFF'}", fg_color=C["success"] if auto_repeat else C["btn"])

def toggle_mini_mode():
    global is_mini_mode
    is_mini_mode = not is_mini_mode
    if is_mini_mode:
        for f in [header, songs_frame, editor_frame, controls_frame, status_frame]:
            f.pack_forget()
        mini_frame.pack(fill="both", expand=True)
        root.geometry("340x160"); root.minsize(300, 140); root.attributes("-topmost", True)
    else:
        mini_frame.pack_forget()
        for f, p in [(header, (12,6)), (songs_frame, 6), (editor_frame, 6), (controls_frame, 6), (status_frame, (6,12))]:
            f.pack(fill="x" if f != editor_frame else "both", expand=(f == editor_frame), padx=16, pady=p)
        root.geometry("900x720"); root.minsize(800, 650); root.attributes("-topmost", False)

# ─── Keyboard Listener ──────────────────────────────────────
def monitor_keys():
    def on_press(key):
        try:
            global stop_flag, bpm
            if key.char == '-': root.after(0, play_next)
            elif key.char == '=': root.after(0, toggle_autoplay)
            elif key.char == '[': root.after(0, lambda: update_bpm(max(10, bpm - 10)))
            elif key.char == ']': root.after(0, lambda: update_bpm(min(1000, bpm + 10)))
        except: pass
    pynput_keyboard.Listener(on_press=on_press).start()

# ═══════════════════════════════════════════════════════════════
# GUI Setup
# ═══════════════════════════════════════════════════════════════
root = ctk.CTk()
root.geometry("900x720")
root.title("🎹 Piano Automator")
root.configure(fg_color=C["bg"])
root.minsize(800, 650)

header = ctk.CTkFrame(root, fg_color=C["card"], corner_radius=12); header.pack(fill="x", padx=16, pady=(12, 6))
ctk.CTkLabel(header, text="🎹  Piano Automator", font=("Helvetica", 26, "bold"), text_color=C["accent"]).pack(side="left", padx=16, pady=12)

# Cloud & Mini Buttons
ctk.CTkButton(header, text="🗗  Mini Player", command=toggle_mini_mode, fg_color=C["btn"], hover_color=C["accent2"], font=("Helvetica", 12, "bold"), width=100, height=32, corner_radius=8).pack(side="right", padx=16)
ctk.CTkButton(header, text="📚  Song Library", command=open_cloud_library, fg_color=C["accent"], hover_color="#00a8cc", text_color="#111", font=("Helvetica", 12, "bold"), width=120, height=32, corner_radius=8).pack(side="right", padx=0)


songs_frame = ctk.CTkFrame(root, fg_color=C["card"], corner_radius=12); songs_frame.pack(fill="x", padx=16, pady=6)
ctk.CTkLabel(songs_frame, text="📁  Local Songs", font=("Helvetica", 13, "bold"), text_color=C["text"]).pack(side="left", padx=(16, 8), pady=10)
saved_songs_menu = ctk.CTkOptionMenu(songs_frame, values=["No songs saved"], command=load_saved_song, width=220, fg_color=C["btn"], button_color=C["accent2"], button_hover_color=C["btn_hov"], font=("Helvetica", 12))
saved_songs_menu.pack(side="left", padx=4, pady=10)
ctk.CTkButton(songs_frame, text="🗑", command=delete_saved_song, width=36, height=32, fg_color=C["danger"], hover_color="#cc3355", corner_radius=8, font=("Helvetica", 14)).pack(side="left", padx=(4, 16), pady=10)

# Settings Row
rblx_var = ctk.BooleanVar(value=False); sus_var = ctk.BooleanVar(value=False); hum_var = ctk.BooleanVar(value=False)
ctk.CTkCheckBox(songs_frame, text="🎮 Roblox Mode", font=("Helvetica", 12, "bold"), variable=rblx_var, command=lambda: toggle_opt("opt_roblox", rblx_var), fg_color=C["accent"], text_color=C["text"]).pack(side="right", padx=16)
ctk.CTkCheckBox(songs_frame, text="Sustain", variable=sus_var, command=lambda: toggle_opt("opt_sustain", sus_var), fg_color=C["accent"], text_color=C["dim"]).pack(side="right", padx=16)
ctk.CTkCheckBox(songs_frame, text="Humanize", variable=hum_var, command=lambda: toggle_opt("opt_humanize", hum_var), fg_color=C["accent"], text_color=C["dim"]).pack(side="right", padx=16)

editor_frame = ctk.CTkFrame(root, fg_color=C["card"], corner_radius=12); editor_frame.pack(fill="both", expand=True, padx=16, pady=6)
inputbox = ctk.CTkTextbox(editor_frame, height=150, font=("Consolas", 16), fg_color=C["card_alt"], text_color=C["text"], border_color=C["accent"], border_width=1, corner_radius=8)
inputbox.pack(fill="both", expand=True, padx=16, pady=16)
inputbox.bind("<<Modified>>", on_text_changed); inputbox.bind("<KeyRelease>", on_text_changed)
inputbox.tag_config("chord", foreground=C["accent"]); inputbox.tag_config("single", foreground=C["success"]); inputbox.tag_config("pause", foreground=C["accent2"])

editor_btns = ctk.CTkFrame(editor_frame, fg_color="transparent"); editor_btns.pack(fill="x", padx=16, pady=(0, 16))
ctk.CTkButton(editor_btns, text="📥  Parse Notes", command=load_notes, fg_color=C["accent"], hover_color="#00a8cc", text_color="#000", font=("Helvetica", 13, "bold"), height=36, corner_radius=8).pack(side="left", padx=(0, 8))
ctk.CTkButton(editor_btns, text="🗑  Clear", command=clear_notes, fg_color=C["btn"], hover_color=C["btn_hov"], font=("Helvetica", 13), height=36, corner_radius=8).pack(side="left", padx=(0, 8))
repeat_btn = ctk.CTkButton(editor_btns, text="🔁  Repeat: ON", command=toggle_repeat, fg_color=C["success"], hover_color=C["btn_hov"], font=("Helvetica", 13), height=36, corner_radius=8)
repeat_btn.pack(side="left")

controls_frame = ctk.CTkFrame(root, fg_color=C["card"], corner_radius=12); controls_frame.pack(fill="x", padx=16, pady=6)

ctrl_top = ctk.CTkFrame(controls_frame, fg_color="transparent"); ctrl_top.pack(fill="x", padx=16, pady=(12, 6))
play_btn = ctk.CTkButton(ctrl_top, text="▶  Autoplay", command=toggle_autoplay, fg_color=C["accent"], text_color="#000", font=("Helvetica", 14, "bold"), width=140, height=40, corner_radius=10)
play_btn.pack(side="left", padx=(0, 8))
ctk.CTkButton(ctrl_top, text="⏹  Stop", command=stop_playback, fg_color=C["danger"], text_color="#fff", font=("Helvetica", 13, "bold"), width=100, height=40, corner_radius=10).pack(side="left", padx=(0, 8))
ctk.CTkButton(ctrl_top, text="⏮  Restart", command=restart_playback, fg_color=C["btn"], font=("Helvetica", 13), width=100, height=40, corner_radius=10).pack(side="left", padx=(0, 16))
now_playing_label = ctk.CTkLabel(ctrl_top, text="—", font=("Consolas", 22, "bold"), text_color=C["accent"]); now_playing_label.pack(side="right", padx=16)

prog_frame = ctk.CTkFrame(controls_frame, fg_color="transparent"); prog_frame.pack(fill="x", padx=16, pady=2)
progress_bar = ctk.CTkProgressBar(prog_frame, progress_color=C["accent"], fg_color=C["card_alt"], height=8, corner_radius=4); progress_bar.set(0)
progress_bar.pack(fill="x", side="left", expand=True, padx=(0, 10))
progress_label = ctk.CTkLabel(prog_frame, text="0 / 0", font=("Consolas", 12), text_color=C["dim"]); progress_label.pack(side="right")

bpm_frame = ctk.CTkFrame(controls_frame, fg_color="transparent"); bpm_frame.pack(fill="x", padx=16, pady=(8, 12))
for label, speed in [("Slow", 200), ("Medium", 400), ("Fast", 700)]:
    ctk.CTkButton(bpm_frame, text=label, command=lambda s=speed: set_speed_preset(s), fg_color=C["btn"], hover_color=C["accent2"], font=("Helvetica", 11), width=65, height=28, corner_radius=6).pack(side="left", padx=2)
bpm_slider = ctk.CTkSlider(bpm_frame, from_=10, to=1000, number_of_steps=99, command=update_bpm, progress_color=C["accent"], fg_color=C["card_alt"], button_color=C["accent"]); bpm_slider.set(bpm)
bpm_slider.pack(side="left", fill="x", expand=True, padx=(10, 8))
bpm_value_label = ctk.CTkLabel(bpm_frame, text=f"{bpm} BPM", font=("Consolas", 13, "bold"), text_color=C["accent"], width=80); bpm_value_label.pack(side="right")

status_frame = ctk.CTkFrame(root, fg_color=C["card_alt"], corner_radius=8); status_frame.pack(fill="x", padx=16, pady=(0, 8), side="bottom")
status_label = ctk.CTkLabel(status_frame, text="Ready.", font=("Helvetica", 13), text_color=C["dim"]); status_label.pack(side="left", padx=16, pady=6)

# Mini
mini_frame = ctk.CTkFrame(root, fg_color=C["bg"], corner_radius=0)
mini_top = ctk.CTkFrame(mini_frame, fg_color=C["card"]); mini_top.pack(fill="x", pady=(0, 2))
ctk.CTkLabel(mini_top, text="🎹 Piano", font=("Helvetica", 12, "bold"), text_color=C["accent"]).pack(side="left", padx=8, pady=4)
ctk.CTkButton(mini_top, text="⤢ Expand", command=toggle_mini_mode, fg_color=C["btn"], width=60, height=20, font=("Helvetica", 10, "bold")).pack(side="right", padx=8, pady=4)
mini_now = ctk.CTkFrame(mini_frame, fg_color="transparent"); mini_now.pack(fill="x", pady=4, padx=8)
mini_now_playing = ctk.CTkLabel(mini_now, text="—", font=("Consolas", 16, "bold"), text_color=C["text"]); mini_now_playing.pack()
mini_progress_bar = ctk.CTkProgressBar(mini_frame, progress_color=C["accent"], fg_color=C["card_alt"], height=4); mini_progress_bar.set(0); mini_progress_bar.pack(fill="x", padx=10, pady=2)
mini_ctrl = ctk.CTkFrame(mini_frame, fg_color="transparent"); mini_ctrl.pack(fill="x", pady=4, padx=8)
mini_play_btn = ctk.CTkButton(mini_ctrl, text="▶ Auto", command=toggle_autoplay, fg_color=C["accent"], text_color="#000", font=("Helvetica", 12, "bold"), width=80, height=28, corner_radius=6); mini_play_btn.pack(side="left", padx=2)
ctk.CTkButton(mini_ctrl, text="⏹ Stop", command=stop_playback, fg_color=C["danger"], text_color="#fff", font=("Helvetica", 12, "bold"), width=60, height=28, corner_radius=6).pack(side="left", padx=2)
mini_bpm_value = ctk.CTkLabel(mini_ctrl, text=f"{bpm} BPM", font=("Consolas", 10), text_color=C["accent"]); mini_bpm_value.pack(side="right")
mini_bpm_slider = ctk.CTkSlider(mini_ctrl, from_=10, to=1000, number_of_steps=99, command=update_bpm, progress_color=C["accent"], fg_color=C["card_alt"], height=12); mini_bpm_slider.set(bpm); mini_bpm_slider.pack(side="right", fill="x", expand=True, padx=4)

refresh_saved_songs()
monitor_keys()
root.mainloop()