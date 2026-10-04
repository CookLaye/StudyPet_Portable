"""
Music Player - Manages background music for the study app
"""

import os
import re
import random
import threading
import queue
import shutil
from typing import List, Optional
try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

# Try importing analysis module with both common patterns
try:
    from src.utils import music_analysis as ma
except ImportError:
    try:
        import music_analysis as ma
    except ImportError:
        ma = None

SUPPORTED_FORMATS = ('.mp3', '.wav', '.ogg', '.m4a')
BGM_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'bgm'))
CACHE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'user_data', 'music_analysis_cache.json'))
DEFAULT_TRACK_RE = re.compile(r'^default_[123]$', re.IGNORECASE)

class MusicPlayer:
    """Music player for background study music."""

    def __init__(self):
        self.is_initialized = False
        self.current_track = None
        self.is_playing = False
        self.volume = 0.7
        self.playlist = []
        self.current_track_index = 0

        # Stress-aware state
        self.stress_mode = False
        self._features = {}
        self._pending = []
        self._worker = None
        self._lock = threading.Lock()
        self._shutdown = False
        self._last_sig = ()

        # Analysis Cache
        self._cache = None
        if ma:
            self._cache = ma.AnalysisCache(CACHE_PATH)
        else:
            print("music_analysis.py not found: stress hiding is disabled")

        self._setup_pygame()
        self._scan_bgm_folder()

    def _setup_pygame(self):
        """Initialize pygame mixer for music playback."""
        if not PYGAME_AVAILABLE:
            return

        try:
            try:
                if pygame.mixer.get_init():
                    pygame.mixer.quit()
            except Exception:
                pass

            pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=4096)
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)
            self.is_initialized = True
        except pygame.error:
            self.is_initialized = False

    def _scan_bgm_folder(self):
        """Load music tracks from bgm folder."""
        os.makedirs(BGM_DIR, exist_ok=True)

        self.playlist = []

        if os.path.exists(BGM_DIR):
            for filename in os.listdir(BGM_DIR):
                if filename.lower().endswith(SUPPORTED_FORMATS):
                    track_path = os.path.join(BGM_DIR, filename)
                    stem = os.path.splitext(filename)[0]

                    self.playlist.append({
                        "name": stem,
                        "path": track_path,
                        "exists": True,
                        "filename": filename,
                        "is_default": bool(DEFAULT_TRACK_RE.fullmatch(stem))
                    })

        self.playlist.sort(key=lambda t: (not t['is_default'], t['name'].lower()))

    def refresh_library(self):
        """Re-scans the BGM folder and updates analysis."""
        self._scan_bgm_folder()
        self.queue_analysis_for_library()
        self._resync_current_index()

    def is_hidden(self, track) -> bool:
        """Check if a track should be hidden during stress mode."""
        if not self.stress_mode or track.get("is_default"):
            return False

        feats = self._features.get(track["filename"])
        if not feats or not ma:
            return False # Fail-safe: unknown/error -> visible

        return ma.is_intense(feats)[0]

    def get_available_tracks(self) -> List[dict]:
        """Get only tracks that exist and are not hidden."""
        return [t for t in self.playlist if t["exists"] and not self.is_hidden(t)]

    def get_hidden_count(self) -> int:
        """Count tracks that are currently hidden."""
        return len([t for t in self.playlist if t["exists"] and self.is_hidden(t)])

    def analysis_pending_count(self) -> int:
        """Number of tracks waiting for analysis."""
        with self._lock:
            return len(self._pending)

    def _resync_current_index(self):
        """Sync current_track_index with the filtered available tracks list."""
        if self.current_track:
            for i, t in enumerate(self.get_available_tracks()):
                if t["path"] == self.current_track["path"]:
                    self.current_track_index = i
                    return
            # If current track is now hidden, index is effectively invalid until sync_library fixes it

    def play_track(self, track_index: int = None):
        """Play a specific track by index (index into available tracks)."""
        if not self.is_initialized:
            available_tracks = self.get_available_tracks()
            if not available_tracks: return False

            if track_index is None: track_index = self.current_track_index
            if track_index >= len(available_tracks): track_index = 0

            track = available_tracks[track_index]
            self.current_track = track
            self.current_track_index = track_index
            self.is_playing = True
            return True

        available_tracks = self.get_available_tracks()
        if not available_tracks: return False

        if track_index is None: track_index = self.current_track_index
        if track_index >= len(available_tracks): track_index = 0

        track = available_tracks[track_index]

        try:
            if self.is_playing:
                pygame.mixer.music.stop()

            pygame.mixer.music.load(track["path"])
            pygame.mixer.music.set_volume(self.volume)
            pygame.mixer.music.play(-1)

            self.current_track = track
            self.current_track_index = track_index
            self.is_playing = True
            return True
        except pygame.error:
            return False

    def play_random_default(self) -> bool:
        """Pick and play a random default track, trying others if one fails."""
        defaults = [t for t in self.get_available_tracks() if t["is_default"]]
        if not defaults: return False

        # Try available defaults in random order
        random.shuffle(defaults)
        for track in defaults:
            try:
                if self.is_playing:
                    pygame.mixer.music.stop()

                pygame.mixer.music.load(track["path"])
                pygame.mixer.music.set_volume(self.volume)
                pygame.mixer.music.play(-1)

                self.current_track = track
                # Update current_track_index relative to available tracks
                available = self.get_available_tracks()
                try:
                    self.current_track_index = next(i for i, t in enumerate(available) if t["path"] == track["path"])
                except StopIteration:
                    self.current_track_index = 0

                self.is_playing = True
                return True
            except pygame.error as e:
                print(f"Failed to load default track {track['name']}: {e}")

        return False

    def set_stress_mode(self, flag: bool):
        """Set stress mode (main thread only)."""
        if flag == self.stress_mode: return
        self.stress_mode = flag
        self.sync_library()

    def sync_library(self) -> bool:
        """
        Main thread only. Re-evaluates visibility and fixes playback.
        Returns True if the visible track list changed.
        """
        if self.current_track and self.is_hidden(self.current_track):
            was_playing = self.is_music_playing()
            if was_playing:
                if not self.play_random_default():
                    self.stop_playback()
            else:
                # Selected/Paused: try robust default selection without playing
                defaults = [t for t in self.get_available_tracks() if t["is_default"]]
                if not defaults:
                    self.current_track = None
                else:
                    random.shuffle(defaults)
                    found = False
                    for track in defaults:
                        try:
                            pygame.mixer.music.load(track["path"])
                            # Just select it, don't play yet
                            available = self.get_available_tracks()
                            self.current_track = track
                            self.current_track_index = next(i for i, t in enumerate(available) if t["path"] == track["path"])
                            found = True
                            break
                        except pygame.error as e:
                            print(f"Fallback default load failed {track['name']}: {e}")
                    if not found:
                        self.current_track = None

        self._resync_current_index()

        sig = tuple(t["path"] for t in self.get_available_tracks())
        changed = sig != self._last_sig
        self._last_sig = sig
        return changed

    def queue_analysis_for_library(self):
        """Queue non-default tracks for background analysis."""
        if not self.is_initialized or not ma: return

        for track in self.playlist:
            if track["is_default"]: continue

            path = track["path"]
            filename = track["filename"]

            # Fast check cache on main thread
            if self._cache:
                feats = self._cache.get(path)
                if feats:
                    self._features[filename] = feats
                    continue

            # Otherwise queue it
            with self._lock:
                if path not in self._pending:
                    self._pending.append(path)

        self._ensure_worker()

    def _ensure_worker(self):
        """Start worker thread if not already running."""
        with self._lock:
            if self._worker is None or not self._worker.is_alive():
                self._shutdown = False
                self._worker = threading.Thread(target=self._analysis_worker, daemon=True)
                self._worker.start()

    def _analysis_worker(self):
        """Background thread: analyzes audio files."""
        while not self._shutdown:
            path = None
            with self._lock:
                if not self._pending:
                    self._worker = None
                    return
                path = self._pending.pop(0)

            if not path: continue

            # Analyze file
            feats = ma.analyze_file(path)

            # Update cache
            if self._cache:
                self._cache.put(path, feats)

            # Update local features map
            # Need filename for mapping. Extract from path.
            filename = os.path.basename(path)
            self._features[filename] = feats

    def import_track(self, source_path: str):
        """Copy an audio file into BGM_DIR and add to library."""
        if not os.path.exists(source_path):
            return False, "Source file does not exist.", None

        if not source_path.lower().endswith(SUPPORTED_FORMATS):
            return False, "Unsupported audio format.", None

        basename = os.path.basename(source_path)
        stem, ext = os.path.splitext(basename)

        # Use commonpath and normcase for robust path comparison
        try:
            abs_source = os.path.abspath(source_path)
            if os.path.commonpath([os.path.normcase(abs_source), os.path.normcase(BGM_DIR)]) == os.path.normcase(BGM_DIR):
                self.refresh_library()
                return True, "Track already in library.", stem
        except ValueError:
            pass

        # Determine destination path with collision handling
        dest_path = os.path.join(BGM_DIR, basename)
        counter = 2
        while os.path.exists(dest_path):
            # If exactly same size, it's the same file
            if os.path.getsize(dest_path) == os.path.getsize(source_path):
                return False, "That track is already in your library.", None

            dest_path = os.path.join(BGM_DIR, f"{stem} ({counter}){ext}")
            counter += 1

        try:
            shutil.copy2(source_path, dest_path)
            self.refresh_library()
            return True, "Track added.", os.path.splitext(os.path.basename(dest_path))[0]
        except OSError as e:
            return False, f"Could not copy the file: {e}", None

    def stop_playback(self):
        """Stop music playback."""
        if not self.is_initialized:
            self.is_playing = False
            self.current_track = None
            return

        try:
            pygame.mixer.music.stop()
            self.is_playing = False
            self.current_track = None
        except pygame.error:
            pass

    def pause(self):
        """Pause music playback."""
        if not self.is_initialized:
            if self.is_playing: self.is_playing = False
            return
        if not self.is_playing: return
        try:
            pygame.mixer.music.pause()
        except pygame.error:
            pass

    def resume(self):
        """Resume paused music."""
        if not self.is_initialized:
            if self.current_track: self.is_playing = True
            return
        try:
            pygame.mixer.music.unpause()
        except pygame.error:
            pass

    def next_track(self):
        """Play the next track in the available playlist."""
        available = self.get_available_tracks()
        if not available: return False
        next_index = (self.current_track_index + 1) % len(available)
        return self.play_track(next_index)

    def previous_track(self):
        """Play the previous track in the available playlist."""
        available = self.get_available_tracks()
        if not available: return False
        prev_index = (self.current_track_index - 1) % len(available)
        return self.play_track(prev_index)

    def set_volume(self, volume: float):
        """Set playback volume (0.0 to 1.0)."""
        self.volume = max(0.0, min(1.0, volume))
        if self.is_initialized and self.is_playing:
            try:
                pygame.mixer.music.set_volume(self.volume)
            except pygame.error:
                pass

    def get_volume(self) -> float:
        """Get current volume level."""
        return self.volume

    def select_track(self, track_index: int = None):
        """Select a track without playing it."""
        available = self.get_available_tracks()
        if not available: return False

        if track_index is None: track_index = self.current_track_index
        if track_index >= len(available): track_index = 0

        track = available[track_index]
        self.current_track = track
        self.current_track_index = track_index
        return True

    def get_current_track_info(self) -> Optional[dict]:
        """Get information about the currently playing track."""
        return self.current_track

    def is_music_playing(self) -> bool:
        """Check if music is currently playing."""
        if not self.is_initialized:
            return self.is_playing
        try:
            return pygame.mixer.music.get_busy() and self.is_playing
        except pygame.error:
            return False

    def toggle_playback(self):
        """Toggle between play and pause."""
        if not self.is_initialized: return
        if self.is_music_playing():
            self.pause()
            self.is_playing = False
        elif self.current_track and not self.is_music_playing():
            if self.is_playing:
                self.resume()
            else:
                self.play_track(self.current_track_index)
            self.is_playing = True

    def cleanup(self):
        """Clean up pygame mixer resources and worker thread."""
        self._shutdown = True
        if self._worker:
            self._worker.join(timeout=3)

        if self.is_initialized:
            try:
                self.stop_playback()
                pygame.mixer.quit()
            except pygame.error:
                pass
