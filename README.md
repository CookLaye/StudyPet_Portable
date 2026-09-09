# 🐾 StudyPet

StudyPet is an AI-powered virtual pet study companion designed to turn academic productivity into a gamified experience. By linking focus sessions and study goals to the growth and happiness of a virtual pet, StudyPet provides emotional support and motivation to students.

## ✨ Key Features

- **Bilingual AI Companion**: A local, private, and supportive virtual pet. It uses a specialized translation wrapper to support multiple languages (including English and Vietnamese) while maintaining a consistent, cute persona.
- **Drowsiness Detection**: Real-time monitoring using computer vision to alert you when you're falling asleep, keeping your study sessions effective.
- **Evolution System**: Watch your pet grow from an Egg $\rightarrow$ Baby $\rightarrow$ Child $\rightarrow$ Grown based on your productivity.
- **Emotion Engine**: The pet reacts with different emotions (Happy, Sad, Angry, Worried, Hungry) based on your interactions and study habits.
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
- **Language**: Python 3.x
- **GUI**: Tkinter
- **Audio**: Pygame
- **Computer Vision**: OpenCV & Keras (for drowsiness detection)

## 🚀 Getting Started (Self-Contained Setup)

StudyPet comes with a fully automated environment system to get you running in minutes.

### Installation
1.  **Clone the repository** and navigate to the root folder.
2.  **Run `StudyPet.bat`**.
    *   This script automatically creates a local Python virtual environment (`.venv`).
    *   It installs only the necessary lightweight dependencies.
    *   It detects your hardware (CPU/GPU) and downloads the matching `llama-server` binary and the Llama 3.2 1B model.
    *   Finally, it launches the application.

### Testing the AI
If you want to test the pet's conversational capabilities without launching the full game:
- Run **`TestChatbot.bat`**. This will start the local AI server and open an interactive terminal chat.

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
