"""
User Model - Represents a user with study statistics and progress tracking
"""

from typing import Dict
from datetime import datetime, timedelta

class User:
    """User class for tracking study statistics and progress."""
    
    def __init__(self, username: str):
        self.username = username
        self.total_study_time = 0  # in minutes
        self.total_questions_answered = 0
        self.correct_answers = 0
        self.study_sessions = 0
        self.streak_days = 0
        self.last_study_date = None
        self.level = 1
        self.experience = 0
        self.achievements = []
        
        # Daily statistics
        self.daily_stats = {}
        
        # Friends list for leaderboard
        self.friends = []
    
    def add_study_time(self, minutes: int):
        """Add study time and update related statistics."""
        self.total_study_time += minutes
        self.study_sessions += 1
        
        # Update daily stats
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in self.daily_stats:
            self.daily_stats[today] = {"study_time": 0, "questions": 0}
        self.daily_stats[today]["study_time"] += minutes
        
        # Update streak
        self._update_study_streak()
        
        # Add experience and check for level up
        self.add_experience(minutes * 2)  # 2 XP per minute of study
    
    def add_questions_answered(self, count: int, correct: int = 0):
        """Add answered questions to statistics."""
        self.total_questions_answered += count
        self.correct_answers += correct
        
        # Update daily stats
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in self.daily_stats:
            self.daily_stats[today] = {"study_time": 0, "questions": 0}
        self.daily_stats[today]["questions"] += count
        
        # Add experience for correct answers
        self.add_experience(correct * 10)  # 10 XP per correct answer
    
    def add_experience(self, amount: int):
        """Add experience points and check for level up."""
        self.experience += amount
        
        # Check for level up (100 XP per level)
        new_level = (self.experience // 100) + 1
        if new_level > self.level:
            self.level = new_level
            # Award achievement for leveling up
            self.add_achievement(f"Reached Level {self.level}")
    
    def add_achievement(self, achievement: str):
        """Add an achievement if not already earned."""
        if achievement not in self.achievements:
            self.achievements.append(achievement)
    
    def _update_study_streak(self):
        """Update the study streak based on last study date."""
        today = datetime.now().date()
        
        if self.last_study_date is None:
            # First study session
            self.streak_days = 1
            self.last_study_date = today
        else:
            last_date = self.last_study_date
            if isinstance(last_date, str):
                last_date = datetime.strptime(last_date, "%Y-%m-%d").date()
            
            days_diff = (today - last_date).days
            
            if days_diff == 1:
                # Consecutive day
                self.streak_days += 1
                self.last_study_date = today
            elif days_diff == 0:
                # Same day, no change to streak
                pass
            else:
                # Streak broken
                self.streak_days = 1
                self.last_study_date = today
        
        # Award streak achievements
        if self.streak_days == 7:
            self.add_achievement("7-Day Study Streak")
        elif self.streak_days == 30:
            self.add_achievement("30-Day Study Streak")
        elif self.streak_days == 100:
            self.add_achievement("100-Day Study Streak")
    
    def get_accuracy_percentage(self) -> float:
        """Calculate answer accuracy percentage."""
        if self.total_questions_answered == 0:
            return 0.0
        return (self.correct_answers / self.total_questions_answered) * 100
    
    def get_average_session_time(self) -> float:
        """Get average study session time in minutes."""
        if self.study_sessions == 0:
            return 0.0
        return self.total_study_time / self.study_sessions
    
    @property
    def current_streak(self) -> int:
        """Alias for streak_days for naming consistency."""
        return self.streak_days
    
    def get_today_stats(self) -> Dict:
        """Get today's study statistics."""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.daily_stats.get(today, {"study_time": 0, "questions": 0})
    
    def get_week_stats(self) -> Dict:
        """Get this week's study statistics."""
        week_stats = {"study_time": 0, "questions": 0}
        today = datetime.now()
        
        for i in range(7):
            date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            day_stats = self.daily_stats.get(date, {"study_time": 0, "questions": 0})
            week_stats["study_time"] += day_stats["study_time"]
            week_stats["questions"] += day_stats["questions"]
        
        return week_stats
    
    def get_leaderboard_score(self) -> int:
        """Calculate leaderboard score based on various factors."""
        # Score calculation: 
        # - 1 point per minute studied
        # - 5 points per correct answer
        # - 50 points per level
        # - 10 points per streak day
        score = (self.total_study_time + 
                (self.correct_answers * 5) + 
                (self.level * 50) + 
                (self.streak_days * 10))
        return score
    
    def add_friend(self, friend_username: str):
        """Add a friend for leaderboard comparison."""
        if friend_username not in self.friends and friend_username != self.username:
            self.friends.append(friend_username)
    
    def remove_friend(self, friend_username: str):
        """Remove a friend from the friends list."""
        if friend_username in self.friends:
            self.friends.remove(friend_username)
    
    def to_dict(self) -> Dict:
        """Convert user to dictionary for saving."""
        return {
            "username": self.username,
            "total_study_time": self.total_study_time,
            "total_questions_answered": self.total_questions_answered,
            "correct_answers": self.correct_answers,
            "study_sessions": self.study_sessions,
            "streak_days": self.streak_days,
            "last_study_date": self.last_study_date.strftime("%Y-%m-%d") if self.last_study_date else None,
            "level": self.level,
            "experience": self.experience,
            "achievements": self.achievements,
            "daily_stats": self.daily_stats,
            "friends": self.friends
        }
    
    @classmethod
    def from_dict(cls, data: Dict):
        """Create user from dictionary."""
        user = cls(data["username"])
        user.total_study_time = data.get("total_study_time", 0)
        user.total_questions_answered = data.get("total_questions_answered", 0)
        user.correct_answers = data.get("correct_answers", 0)
        user.study_sessions = data.get("study_sessions", 0)
        user.streak_days = data.get("streak_days", 0)
        
        last_date = data.get("last_study_date")
        if last_date:
            user.last_study_date = datetime.strptime(last_date, "%Y-%m-%d").date()
        
        user.level = data.get("level", 1)
        user.experience = data.get("experience", 0)
        user.achievements = data.get("achievements", [])
        user.daily_stats = data.get("daily_stats", {})
        user.friends = data.get("friends", [])
        
        return user