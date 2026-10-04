# 🐾 StudyPet

StudyPet is an AI-powered emotional companion designed to help students find balance and relaxation amidst academic pressure. Rather than just a productivity tool, StudyPet serves as a digital sanctuary—a supportive virtual pet that grows with you, listens to your stresses, and provides a calming presence during the most demanding times of student life.

## ✨ Key Features

- **Emotional Support Companion**: A local, private virtual pet that offers a listening ear and a cute persona. It supports multiple languages (including English and Vietnamese), providing a safe space for students to express themselves.
- **Stress-Relief Rant**: A dedicated space to let it all out. Users can rant about their stressors, and the pet will visually "consume" the stress, transforming negative energy into support. Based on the detected stress level, the pet provides tailored advice to help the user relax and recharge.
- **Vietnamese Student Specialist**: The AI is specifically attuned to the unique pressures faced by high school students in Vietnam, offering empathetic guidance on navigating final examinations and the high-stakes process of university selection.
- **Well-being Monitoring**: Real-time drowsiness detection using computer vision ensures you're taking necessary breaks, reminding you that rest is just as important as study.
- **Holistic Evolution System**: Watch your pet evolve from an Egg $\rightarrow$ Baby $\rightarrow$ Child $\rightarrow$ Grown, not just through productivity, but through the bond and emotional balance you maintain.
- **Emotion Engine**: A reactive pet that mirrors and responds to your emotional state, providing companionship when you feel worried or sad.
- **Zero-Internet AI**: Once set up, the chatbot runs entirely on your local machine—no API keys or internet connection required.
- **Crash Recovery System**: Built-in session tracking and runtime backups ensure your pet's progress is preserved even if the application closes unexpectedly.

## 🛠 Technical Architecture

### AI Stack
StudyPet utilizes a high-performance, lightweight AI architecture optimized for medium-range laptops:
- **Model**: `Llama 3.2 1B Instruct` (Quantized GGUF).
- **Backend**: Standalone `llama-server` binary (via `llama.cpp`).
- **Architecture**: Client-Server pattern. The app acts as a client communicating with a local C++ server, ensuring an extremely responsive UI.
- **Bilingual Engine**: A "Hub-and-Spoke" translation wrapper that processes inputs in English for maximum model coherence and translates responses back to the user's language with a custom pronoun-polishing layer for Vietnamese.

### Core Tech
- **Language**: Python 3.13 (Managed by `uv` for zero-setup)
- **GUI**: Tkinter
- **Audio**: Pygame
- **Computer Vision**: OpenCV, MediaPipe & ONNX Runtime (facial stress scan)

## 🚀 Getting Started (Zero-Setup)

StudyPet now uses a standalone environment manager (`uv`) to ensure it runs on any device without requiring you to manually install Python or configure system paths.

**Requirements**
- The launchers set everything up automatically; **first launch needs internet** and downloads a ~0.8 GB model; later launches work offline (English chat; Vietnamese needs internet for translation).
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
- `assets/`: Model files, binaries, images, and audio.
- `user_data/`: Local save files and settings.
- `game_data/`: Static pet data.

## 🤝 Contributing
Feel free to open issues or submit pull requests to help make StudyPet the ultimate study companion!
