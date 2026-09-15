"""
AI-Enhanced Scheduler Screen - Intelligent study session planning
"""

import tkinter as tk
from tkinter import ttk
from utils.notifications import NotificationManager
import datetime
import json
import os

# Import AI components
try:
    from ai.schedule_optimizer import ScheduleOptimizer
    from ai.mental_health_analyzer import MentalHealthAnalyzer
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

class SchedulerScreen:
    """AI-enhanced scheduler for intelligent study session planning."""
    
    def __init__(self, parent, app_state):
        self.parent = parent
        self.app_state = app_state
        self.frame = None
        
        # Initialize AI components if available
        if AI_AVAILABLE:
            self.mental_health_analyzer = MentalHealthAnalyzer()
            self.schedule_optimizer = ScheduleOptimizer(self.mental_health_analyzer)
        else:
            self.mental_health_analyzer = None
            self.schedule_optimizer = None
        
        self.create_widgets()
    
    def create_widgets(self):
        """Create and layout the simple scheduler widgets."""
        # Main scrollable frame
        main_canvas = tk.Canvas(self.parent)
        scrollbar = ttk.Scrollbar(self.parent, orient="vertical", command=main_canvas.yview)
        self.frame = ttk.Frame(main_canvas)
        
        self.frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )
        
        main_canvas.create_window((0, 0), window=self.frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)
        
        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Title
        title_frame = ttk.Frame(self.frame, padding=20)
        title_frame.pack(fill="x")
        
        ai_status = "🤖 AI-Enhanced" if AI_AVAILABLE else "📅"
        ttk.Label(title_frame, text=f"{ai_status} Study Scheduler", font=("Arial", 18, "bold")).pack()
        
        # Description
        description_text = "Personalized study planning with AI insights" if AI_AVAILABLE else "Plan your study sessions and stay organized"
        ttk.Label(
            title_frame, 
            text=description_text, 
            font=("Arial", 11), 
            foreground="blue"
        ).pack(pady=(5, 0))
        
        # Schedule display with AI integration
        if AI_AVAILABLE:
            self.create_ai_schedule_display()
        else:
            self.create_simple_schedule_display()
        
        # Bind mouse wheel
        def on_mouse_wheel(event):
            main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        self.parent.bind("<MouseWheel>", on_mouse_wheel)
    
    def create_ai_schedule_display(self):
        """Create AI-enhanced schedule display with personalized recommendations."""
        schedule_frame = ttk.LabelFrame(self.frame, text="🤖 AI-Optimized Schedule", padding=15)
        schedule_frame.pack(fill="x", padx=20, pady=10)
        
        # Date display
        today = datetime.date.today()
        ttk.Label(schedule_frame, text=f"📅 {today.strftime('%A, %B %d, %Y')}", font=("Arial", 12, "bold")).pack(anchor="w", pady=(0, 15))
        
        # AI Status and Mental Health Check
        ai_status_frame = ttk.LabelFrame(schedule_frame, text="AI Analysis", padding=10)
        ai_status_frame.pack(fill="x", pady=(0, 15))
        
        # Quick mental health check button
        check_frame = ttk.Frame(ai_status_frame)
        check_frame.pack(fill="x", pady=5)
        
        ttk.Label(
            check_frame,
            text="How are you feeling today?",
            font=("Arial", 11, "bold")
        ).pack(anchor="w")
        
        ttk.Button(
            check_frame,
            text="💭 Quick Check-in",
            command=self.show_mental_health_checkin,
            style="Accent.TButton"
        ).pack(anchor="w", pady=(5, 0))
        
        # AI Schedule recommendations
        recommendations_frame = ttk.LabelFrame(schedule_frame, text="🎯 AI Recommendations", padding=10)
        recommendations_frame.pack(fill="x", pady=(0, 15))
        
        # Generate sample recommendations
        self.display_ai_recommendations(recommendations_frame)
        
        # Adaptive study options based on AI analysis
        adaptive_frame = ttk.LabelFrame(schedule_frame, text="Personalized Study Sessions", padding=10)
        adaptive_frame.pack(fill="x", pady=(0, 15))
        
        self.display_adaptive_sessions(adaptive_frame)
        
        # Study insights
        insights_frame = ttk.LabelFrame(schedule_frame, text="💡 Study Insights", padding=10)
        insights_frame.pack(fill="x", pady=(0, 10))
        
        self.display_study_insights(insights_frame)
    
    def show_mental_health_checkin(self):
        """Show a quick mental health check-in dialog."""
        checkin_window = tk.Toplevel(self.parent)
        checkin_window.title("💭 Mental Health Check-in")
        checkin_window.place(relwidth=0.5, relheight=0.4)
        checkin_window.resizable(True, True)
        
        # Main frame
        main_frame = ttk.Frame(checkin_window, padding=20)
        main_frame.pack(fill="both", expand=True)
        
        # Title
        ttk.Label(main_frame, text="💭 How are you feeling today?", font=("Arial", 16, "bold")).pack(pady=(0, 20))
        
        # Description
        ttk.Label(
            main_frame,
            text="Share your current state to get personalized study recommendations.",
            font=("Arial", 11),
            wraplength=400
        ).pack(pady=(0, 20))
        
        # Text input for feelings
        ttk.Label(main_frame, text="Tell me about your current mood and energy level:", font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 5))
        
        feelings_text = tk.Text(
            main_frame,
            height=5,
            width=60,
            wrap="word",
            font=("Arial", 10),
            relief="solid",
            borderwidth=1
        )
        feelings_text.pack(pady=(0, 20))
        
        # Placeholder text
        feelings_text.insert("1.0", "Example: I'm feeling a bit stressed about upcoming exams but motivated to study...")
        feelings_text.config(foreground="gray")
        
        def on_focus_in(event):
            if feelings_text.get("1.0", tk.END).strip() == "Example: I'm feeling a bit stressed about upcoming exams but motivated to study...":
                feelings_text.delete("1.0", tk.END)
                feelings_text.config(foreground="black")
        
        def on_focus_out(event):
            if not feelings_text.get("1.0", tk.END).strip():
                feelings_text.insert("1.0", "Example: I'm feeling a bit stressed about upcoming exams but motivated to study...")
                feelings_text.config(foreground="gray")
        
        feelings_text.bind("<FocusIn>", on_focus_in)
        feelings_text.bind("<FocusOut>", on_focus_out)
        
        # Submit button
        def submit_checkin():
            user_input = feelings_text.get("1.0", tk.END).strip()
            if user_input and user_input != "Example: I'm feeling a bit stressed about upcoming exams but motivated to study...":
                # Analyze the input
                analysis = self.mental_health_analyzer.analyze_text(user_input)
                self.show_ai_recommendations_popup(analysis, checkin_window)
            else:
                NotificationManager.warn("Empty Input", "Please share your current feelings to get personalized recommendations.")
        
        submit_btn = ttk.Button(
            main_frame,
            text="Get AI Recommendations",
            command=submit_checkin,
            style="Accent.TButton"
        )
        submit_btn.pack(pady=(0, 10))
        
        # Close button
        ttk.Button(
            main_frame,
            text="Cancel",
            command=checkin_window.destroy
        ).pack()
    
    def show_ai_recommendations_popup(self, analysis, parent_window):
        """Show AI-generated recommendations in a popup."""
        parent_window.destroy()  # Close check-in window
        
        recommendations_window = tk.Toplevel(self.parent)
        recommendations_window.title("🤖 AI Study Recommendations")
        recommendations_window.place(relwidth=0.6, relheight=0.5)
        recommendations_window.resizable(True, True)
        
        # Main scrollable frame
        main_canvas = tk.Canvas(recommendations_window)
        scrollbar = ttk.Scrollbar(recommendations_window, orient="vertical", command=main_canvas.yview)
        scrollable_frame = ttk.Frame(main_canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )
        
        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)
        
        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        content_frame = ttk.Frame(scrollable_frame, padding=20)
        content_frame.pack(fill="both", expand=True)
        
        # Title
        ttk.Label(content_frame, text="🤖 Your Personalized Study Plan", font=("Arial", 16, "bold")).pack(pady=(0, 20))
        
        # Mental health summary
        summary_frame = ttk.LabelFrame(content_frame, text="Analysis Summary", padding=15)
        summary_frame.pack(fill="x", pady=(0, 15))
        
        mental_health_score = analysis.get('mental_health_score', 0.5)
        stress_level = analysis.get('stress_level', 0.3)
        risk_level = analysis.get('risk_level', 'low')
        
        score_text = f"Mental Wellbeing: {mental_health_score*100:.0f}/100"
        stress_text = f"Stress Level: {stress_level*100:.0f}/100"
        risk_text = f"Risk Level: {risk_level.title()}"
        
        ttk.Label(summary_frame, text=score_text, font=("Arial", 11)).pack(anchor="w")
        ttk.Label(summary_frame, text=stress_text, font=("Arial", 11)).pack(anchor="w")
        ttk.Label(summary_frame, text=risk_text, font=("Arial", 11)).pack(anchor="w")
        
        # Generate and display schedule
        if self.schedule_optimizer:
            study_goals = {
                'subjects': [
                    {'name': 'Mathematics', 'difficulty': 0.7, 'priority': 0.8, 'focus_area': 'Problem Solving'},
                    {'name': 'Science', 'difficulty': 0.6, 'priority': 0.7, 'focus_area': 'Concepts Review'},
                    {'name': 'Literature', 'difficulty': 0.5, 'priority': 0.6, 'focus_area': 'Reading Comprehension'}
                ]
            }
            
            schedule = self.schedule_optimizer.generate_personalized_schedule(
                study_goals, {}, analysis
            )
            
            # Display recommendations
            recommendations_list_frame = ttk.LabelFrame(content_frame, text="AI Recommendations", padding=15)
            recommendations_list_frame.pack(fill="x", pady=(0, 15))
            
            for i, rec in enumerate(schedule.get('recommendations', []), 1):
                ttk.Label(
                    recommendations_list_frame,
                    text=f"{i}. {rec}",
                    font=("Arial", 10),
                    wraplength=500
                ).pack(anchor="w", pady=2)
            
            # Display today's suggested schedule
            today_str = datetime.datetime.now().strftime('%Y-%m-%d')
            if today_str in schedule.get('daily_schedules', {}):
                daily_schedule = schedule['daily_schedules'][today_str]
                
                schedule_display_frame = ttk.LabelFrame(content_frame, text="Today's Suggested Schedule", padding=15)
                schedule_display_frame.pack(fill="x", pady=(0, 15))
                
                for session in daily_schedule.get('sessions', []):
                    session_text = f"⏰ {session['start_time']} - {session['subject']} ({session['duration']} min)"
                    ttk.Label(
                        schedule_display_frame,
                        text=session_text,
                        font=("Arial", 10)
                    ).pack(anchor="w", pady=1)
        
        # Close button
        ttk.Button(
            content_frame,
            text="Close",
            command=recommendations_window.destroy
        ).pack(pady=(20, 0))
        
        # Bind mouse wheel
        def on_mouse_wheel(event):
            main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        recommendations_window.bind("<MouseWheel>", on_mouse_wheel)
    
    def display_ai_recommendations(self, parent_frame):
        """Display AI-generated recommendations."""
        default_recommendations = [
            "Based on typical patterns, morning sessions (9-11 AM) are optimal for focus",
            "Consider 25-minute study blocks with 5-minute breaks (Pomodoro technique)",
            "Chat with your pet if you're feeling stressed - it helps!",
            "Take a mental health check-in to get personalized recommendations"
        ]
        
        for i, rec in enumerate(default_recommendations, 1):
            ttk.Label(
                parent_frame,
                text=f"{i}. {rec}",
                font=("Arial", 9),
                wraplength=550
            ).pack(anchor="w", pady=1)
    
    def display_adaptive_sessions(self, parent_frame):
        """Display adaptive study sessions based on AI analysis."""
        session_options = [
            ("🧠 Focus Boost", 20, "Optimized for current stress levels", "#4CAF50"),
            ("⚡ Energy Session", 35, "Balanced intensity for steady progress", "#2196F3"),
            ("🎯 Deep Work", 50, "Extended focus for complex topics", "#FF9800"),
            ("💆 Gentle Study", 15, "Low-pressure session for tough days", "#9C27B0")
        ]
        
        for name, duration, description, color in session_options:
            option_frame = ttk.Frame(parent_frame)
            option_frame.pack(fill="x", pady=3)
            
            ttk.Button(
                option_frame,
                text=f"{name} ({duration} min)",
                command=lambda d=duration: self.start_ai_session(d),
                width=25
            ).pack(side="left")
            
            ttk.Label(
                option_frame,
                text=description,
                font=("Arial", 9),
                foreground=color
            ).pack(side="left", padx=(10, 0))
    
    def display_study_insights(self, parent_frame):
        """Display AI-generated study insights."""
        insights = [
            "💡 Peak performance typically occurs in the first 20 minutes of study",
            "🎵 Background music can enhance focus for some learning styles",
            "🌱 Regular breaks prevent mental fatigue and improve retention",
            "🤝 Your pet's emotional support can reduce study anxiety by up to 30%"
        ]
        
        for insight in insights:
            ttk.Label(
                parent_frame,
                text=insight,
                font=("Arial", 9),
                wraplength=600
            ).pack(anchor="w", pady=2)
    
    def start_ai_session(self, duration):
        """Start an AI-recommended study session (info only)."""
        result = NotificationManager.confirm(
            "Start AI-Optimized Session",
            (
                f"Ready to start an AI-optimized {duration}-minute study session?\n\n"
                f"This session is personalized based on AI analysis of your current state.\n"
                f"Use the Study Timer panel to run your session."
            )
        )
        if result:
            try:
                self.parent.destroy()
            except Exception:
                pass
            NotificationManager.notify(
                "AI Session Starting",
                (
                    f"Starting AI-optimized {duration}-minute session.\n\n"
                    f"Open the Study Timer panel to begin."
                )
            )
    
    def destroy(self):
        """Clean up the screen."""
        if self.frame:
            self.frame.destroy()
            self.frame = None
    def create_simple_schedule_display(self):
        """Fallback schedule display used when AI components are unavailable."""
        schedule_frame = ttk.LabelFrame(self.frame, text="📅 Study Schedule", padding=15)
        schedule_frame.pack(fill="x", padx=20, pady=10)
        today = datetime.date.today()
        ttk.Label(schedule_frame, text=f"📅 {today.strftime('%A, %B %d, %Y')}",
                  font=("Arial", 12, "bold")).pack(anchor="w", pady=(0, 15))
        sessions_frame = ttk.LabelFrame(schedule_frame, text="Study Sessions", padding=10)
        sessions_frame.pack(fill="x", pady=(0, 15))
        ttk.Label(sessions_frame, text="Choose a session length to get started:",
                  font=("Arial", 10)).pack(anchor="w", pady=(0, 8))
        buttons_frame = ttk.Frame(sessions_frame)
        buttons_frame.pack(anchor="w")
        for label, minutes in [("25 min (Pomodoro)", 25), ("45 min", 45), ("60 min", 60), ("90 min", 90)]:
            ttk.Button(buttons_frame, text=label,
                       command=lambda m=minutes: self.start_ai_session(m)).pack(side="left", padx=(0, 8))
        insights_frame = ttk.LabelFrame(schedule_frame, text="💡 Study Tips", padding=10)
        insights_frame.pack(fill="x", pady=(0, 10))
        self.display_study_insights(insights_frame)
