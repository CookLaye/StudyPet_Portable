# 🐾 StudyPet

StudyPet is an AI-powered emotional companion designed to help students find balance and relaxation amidst academic pressure. Rather than just a productivity tool, StudyPet serves as a digital sanctuary—a supportive virtual pet that grows with you, listens to your stresses, and provides a calming presence during the most demanding times of student life.

## ✨ Key Features

- **Emotional Support Companion**: A local, private virtual pet that offers a listening ear and a cute persona. It supports multiple languages (including English and Vietnamese), providing a safe space for students to express themselves.
- **Stress-Relief Rant**: A dedicated space to let it all out. Users can rant about their stressors, and the pet will visually "consume" the stress, transforming negative energy into support. Based on the detected stress level, the pet provides tailored advice to help the user relax and recharge.
- **Vietnamese Student Specialist**: The AI is specifically attuned to the unique pressures faced by high school students in Vietnam, offering empathetic guidance on navigating final examinations and the high-stakes process of university selection.
- **Well-being Monitoring**: A local facial stress scan (see below) helps you notice tension early, reminding you that rest is just as important as study. *(The older real-time drowsiness detection is currently disabled.)*
- **Facial Stress Scan with Live Model Read-out**: A short, fully local camera scan estimates how tense you look. While it runs, a read-out under the camera preview shows exactly what the emotion model predicts right now, so you can see that it is really working: the top emotion with its probability (e.g. "Model sees: Neutral 62%"), valence and arousal, a running tension estimate, a "model runs" counter that keeps climbing during the scan, and eight bars for the model's full emotion output (greyed out when no face is in view). It appears on both the start-up scan and the Diagnosis window, is display-only (it never changes the scan result), and can be switched off with `SHOW_MODEL_READOUT = False` in `src/screens/stress_panels.py`.
- **Holistic Evolution System**: Watch your pet evolve from an Egg $\rightarrow$ Baby $\rightarrow$ Child $\rightarrow$ Grown, not just through productivity, but through the bond and emotional balance you maintain.
- **Emotion Engine**: A reactive pet that mirrors and responds to your emotional state, providing companionship when you feel worried or sad.
- **Zero-Internet AI**: Once set up, the chatbot runs entirely on your local machine—no API keys or internet connection required.
- **Crash Recovery System**: Built-in session tracking and runtime backups ensure your pet's progress is preserved even if the application closes unexpectedly.

## 🛠 Technical Architecture

### AI Stack
StudyPet utilizes a high-performance, lightweight AI architecture optimized for medium-range laptops:
- **Model**: Model is chosen automatically by RAM at first launch (tiers Lite / Standard / Plus), stored in `assets/models/gpt_pet/`, can be forced with the `STUDYPET_MODEL_TIER` environment variable or by deleting `selected_model.json`.
- **Backend**: Standalone `llama-server` binary (via `llama.cpp`).
- **Architecture**: Client-Server pattern. The app acts as a client communicating with a local C++ server, ensuring an extremely responsive UI.

### Core Tech
- **Language**: Python 3.13 (Managed by `uv` for zero-setup)
- **GUI**: Tkinter
- **Audio**: Pygame
- **Computer Vision**: OpenCV, MediaPipe & ONNX Runtime (facial stress scan with live model read-out; all processing is local, no video is saved)

## 🧭 In Design: Focus Tracking for the Pomodoro Timer

*Planned, not implemented yet.* The idea is to use the camera during Pomodoro work sessions to estimate whether you are paying attention to the screen:

- It is **opt-in**: a "Focus tracking (camera)" checkbox under the timer buttons, plus a one-time consent prompt the first time you start a timer. When on, starting a work session opens a small, always-on-top window (it never steals keyboard focus) with the camera preview, the current state, the attention percentage over the last minute and a "Warnings k/N" counter. You can hide the preview while tracking continues, and the window's X only minimises it.
- The first ~12 seconds of the first session calibrate your normal head position (look at your screen); a "Recalibrate" button repeats it, since cameras sit at different angles.
- Tracking only runs during work phases. Pausing the timer releases the camera and hides the window (warnings are kept); resuming shows it again immediately. Breaks or ending the session release the camera and close the window. If the camera or a model cannot be loaded, the timer still runs normally and the window explains why.
- Attention is judged from facial landmarks (head direction, eyes open or closed), plus body presence from MediaPipe Pose, so that leaving the desk is told apart from your face simply being hidden. The small pose model is downloaded once on first use. It is far lighter than the stress scan: a few frames per second, no emotion model.
- When focus is lost for several seconds (about 12 s looking away, 15 s away from the desk, 10 s with eyes closed), the pet scolds you through the existing system notification, plus a speech bubble and a red window flash in case Windows silences notifications. After *session minutes / 5* warnings (minimum 3) the session ends immediately with no points; the second-to-last warning says it is the last one. Warnings are at least 45 seconds apart, and a distraction that simply continues warns again every 45 seconds, so a single glance away never adds up but walking away does. Nothing is counted when the camera cannot see you well (for example in a very dark room).
- Everything is processed on your computer; only summary numbers could ever be stored, never video.

### Known limitations of focus tracking
- **Looking down is not counted as losing focus.** A webcam cannot tell reading or writing in a notebook from looking at a phone in your lap, and penalising it would wrongly punish note-taking. For now the tracker only counts looking away from the screen (sideways or up), eyes staying closed, and leaving the desk. If the face is lost because your head is tilted down but your body is still in view, that is treated as present. This also means looking at a phone below the camera view will not be caught. This may be revisited later.
- **It measures where you are looking, not how well you are concentrating.** Reading a book, a second monitor, or thinking while looking away can look like distraction, and fidgeting or looking away can be part of concentrating. Short calibration and generous time allowances reduce this, but do not remove it.
- Poor lighting, glasses, and unusual camera angles reduce accuracy.

## 🚀 Getting Started (Zero-Setup)

StudyPet now uses a standalone environment manager (`uv`) to ensure it runs on any device without requiring you to manually install Python or configure system paths.

**Requirements**
- The launchers set everything up automatically; **first launch needs internet** and downloads a 1 to 3 GB model, depending on the computer; later launches work fully offline.
- Python **3.13** is installed automatically by the launcher (no manual Python install).
- No C++ compiler / CUDA is needed; Windows uses the CPU build. The facial stress scan needs an Apple Silicon Mac (M1 or newer) on macOS 14 or newer; on other Macs StudyPet still runs, but without the face scan.
- Developers: `uv pip install -r requirements-dev.txt`.

### 🪟 Windows Setup
1. **Clone the repository** or download the portable folder.
2. **Run `start_windows.bat`**.
   - The script will automatically download `uv` (a fast Python manager).
   - It creates a standalone Python virtual environment in the `.venv` folder.
   - It installs all dependencies.
   - It downloads the `llama-server` binary and the AI model.
   - Finally, it launches the application.

### 🍎 macOS Setup
1. **Clone the repository** or download the portable folder.
2. **Double-click `start_mac.command`** (or run `bash start_mac.sh` in Terminal). The first time, macOS may ask to let Terminal use the camera: click Allow.
   - The script detects your Mac's architecture (Intel or Apple Silicon).
   - It downloads `uv` and sets up a standalone Python environment.
   - It downloads the pre-compiled `llama-server` binary specifically for your Mac.
   - It downloads the AI model and launches the application.

## ❓ Troubleshooting
- *Chat says it can't reach its brain:* open `assets/models/gpt_pet/server.log` (in the project folder) and read the last lines.
- *Windows, log/console shows exit code 3221225781 (0xC0000135):* install the Microsoft Visual C++ Redistributable (x64) from https://aka.ms/vc14/vc_redist.x64.exe , restart Windows, start StudyPet again.
- *Windows, exit code 3221225501 (0xC000001D):* the CPU is too old for the AI server build; the rest of StudyPet still works.
- *Repair everything:* close StudyPet, delete the `.venv` folder and the `assets/models/gpt_pet/bin` folder, run the launcher again (the model file is kept).
- *Camera does not start:* run `.venv/bin/python -m stress_scan.camera_check` (macOS) or `.venv\Scripts\python.exe -m stress_scan.camera_check` (Windows) from the project folder and send the output. Also close other apps using the camera (Zoom, Teams, browser tabs) and check the OS camera privacy settings.
- *Not sure the face scan model is working:* during the scan, watch the read-out under the camera preview. "model runs" should keep increasing, and "Model sees" and the bars should change when you change your expression. If the counter freezes, the model is not running; if the line says no face detected, check lighting and camera position.
- *Model download fails:* the console prints the real error for each attempt. Common causes: no internet, a VPN/proxy/antivirus inspecting HTTPS, or a wrong system date.
- *Face scan libraries could not be installed:* expected on Intel Macs and macOS 13 or older; the rest of StudyPet works.
- *Something else uses port 8080:* nothing to do — StudyPet picks a free port by itself.

## 📁 Project Structure
- `src/`: Main source code.
    - `models/`: Game state and pet logic.
    - `screens/`: GUI screen definitions.
    - `graphics/`: Pet graphics and playground rendering.
    - `ui/`: Theme and custom widgets.
    - `utils/`: AI Model Manager, Chatbot client, and hardware utilities.
- `stress_scan/`: Camera and computer-vision code for the facial stress scan (face landmarks, emotion model, scoring, baseline, and the pure `live_readout.py` helpers behind the live read-out).
- `tests/`: Automated tests (for example `python tests/test_live_readout.py`).
- `assets/`: Model files, binaries, images, and audio.
- `user_data/`: Local save files and settings.
- `game_data/`: Static pet data.

## 🤝 Contributing
Feel free to open issues or submit pull requests to help make StudyPet the ultimate study companion!
