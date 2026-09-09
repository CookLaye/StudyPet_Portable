"""
Music Player - Manages background music for the study app
"""

import os
from typing import List, Optional
try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

class MusicPlayer:
    """Music player for background study music."""
    
    def __init__(self):
        self.is_initialized = False
        self.current_track = None
        self.is_playing = False
        self.volume = 0.7
        self.playlist = []
        self.current_track_index = 0
        
        # Pre-installed track names
        self.default_tracks = [
            "study_ambient.mp3",
            "focus_piano.mp3",
            "concentration_nature.mp3"
        ]
        
        self._setup_pygame()
        self._load_default_tracks()
    
    def _setup_pygame(self):
        """Initialize pygame mixer for music playback."""
        if not PYGAME_AVAILABLE:
            return
        
        try:
            # Ensure our settings actually apply.
            # If something else initialized the mixer first, pre_init() won't take effect.
            try:
                if pygame.mixer.get_init():
                    pygame.mixer.quit()
            except Exception:
                pass

            # Higher buffer reduces crackling on some Windows devices at the cost of latency.
            pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=4096)
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)
            self.is_initialized = True
        except pygame.error:
            self.is_initialized = False
    
    def _load_default_tracks(self):
        """Load music tracks from bgm folder."""
        music_dir = os.path.join(
            os.path.dirname(__file__), 
            '..', '..', 'bgm'
        )
        
        self.playlist = []
        
        # Check if bgm directory exists
        if os.path.exists(music_dir):
            # Get all audio files from bgm folder
            supported_formats = ['.mp3', '.wav', '.ogg', '.m4a']
            
            for filename in os.listdir(music_dir):
                if any(filename.lower().endswith(fmt) for fmt in supported_formats):
                    track_path = os.path.join(music_dir, filename)
                    # Use exact filename (without extension) as the display name
                    display_name = os.path.splitext(filename)[0]
                    
                    self.playlist.append({
                        "name": display_name,
                        "path": track_path,
                        "exists": True
                    })
        
        # Sort playlist by name for better organization
        self.playlist.sort(key=lambda x: x['name'])
    
    def add_track(self, track_path: str, track_name: str = None):
        """Add a custom track to the playlist."""
        if not track_name:
            track_name = os.path.basename(track_path).replace('.mp3', '').replace('_', ' ').title()
        
        track_info = {
            "name": track_name,
            "path": track_path,
            "exists": os.path.exists(track_path)
        }
        
        self.playlist.append(track_info)
    
    def get_playlist(self) -> List[dict]:
        """Get the current playlist."""
        return self.playlist.copy()
    
    def get_available_tracks(self) -> List[dict]:
        """Get only tracks that exist on the filesystem."""
        return [track for track in self.playlist if track["exists"]]
    
    def play_track(self, track_index: int = None):
        """Play a specific track by index."""
        if not self.is_initialized:
            # Simulate playback in environments without pygame so the UI stays responsive
            available_tracks = self.get_available_tracks()
            if not available_tracks:
                return False
            
            if track_index is None:
                track_index = self.current_track_index
            
            if track_index >= len(available_tracks):
                track_index = 0
            
            track = available_tracks[track_index]
            self.current_track = track
            self.current_track_index = track_index
            self.is_playing = True
            return True
        
        available_tracks = self.get_available_tracks()
        if not available_tracks:
            return False
        
        if track_index is None:
            track_index = self.current_track_index
        
        if track_index >= len(available_tracks):
            track_index = 0
        
        track = available_tracks[track_index]
        
        try:
            # Stop any currently playing music first
            if self.is_playing:
                pygame.mixer.music.stop()
            
            # Load and play the new track
            pygame.mixer.music.load(track["path"])
            pygame.mixer.music.set_volume(self.volume)
            pygame.mixer.music.play(-1)  # Loop indefinitely
            
            self.current_track = track
            self.current_track_index = track_index
            self.is_playing = True
            
            return True
            
        except pygame.error:
            return False
    
    def stop_playback(self):
        """Stop music playback."""
        if not self.is_initialized:
            # Simulated stop
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
            # Simulated pause
            if self.is_playing:
                self.is_playing = False
            return
        if not self.is_playing:
            return
        
        try:
            pygame.mixer.music.pause()
        except pygame.error:
            pass
    
    def resume(self):
        """Resume paused music."""
        if not self.is_initialized:
            # Simulated resume
            if self.current_track:
                self.is_playing = True
            return
        
        try:
            pygame.mixer.music.unpause()
        except pygame.error:
            pass
    
    def next_track(self):
        """Play the next track in the playlist."""
        available_tracks = self.get_available_tracks()
        if not available_tracks:
            return False
        
        next_index = (self.current_track_index + 1) % len(available_tracks)
        return self.play_track(next_index)
    
    def previous_track(self):
        """Play the previous track in the playlist."""
        available_tracks = self.get_available_tracks()
        if not available_tracks:
            return False
        
        prev_index = (self.current_track_index - 1) % len(available_tracks)
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
        available_tracks = self.get_available_tracks()
        if not available_tracks:
            return False
        
        if track_index is None:
            track_index = self.current_track_index
        
        if track_index >= len(available_tracks):
            track_index = 0
        
        track = available_tracks[track_index]
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
        if not self.is_initialized:
            return
            
        if self.is_music_playing():
            self.pause()
            self.is_playing = False
        elif self.current_track and not self.is_music_playing():
            # Resume paused music or play selected track
            if self.is_playing:
                # Was paused, resume
                self.resume()
            else:
                # Track selected but not playing, start playing it
                self.play_track(self.current_track_index)
            self.is_playing = True
    
    def cleanup(self):
        """Clean up pygame mixer resources."""
        if self.is_initialized:
            try:
                self.stop_playback()
                pygame.mixer.quit()
            except pygame.error:
                pass