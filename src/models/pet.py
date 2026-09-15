"""
Pet Model - Represents virtual pets with different stages and emotions
"""

from enum import Enum
from typing import Dict
import json
import os

class PetType(Enum):
    """Available pet types."""
    CAT = "cat"
    DOG = "dog"
    AXOLOTL = "axolotl"
    RACCOON = "raccoon"
    PENGUIN = "penguin"

class PetStage(Enum):
    """Pet evolution stages."""
    EGG = 1
    BABY = 2
    CHILD = 3
    GROWN = 4
    BATTLE_FIT = 5

class PetEmotion(Enum):
    """Pet emotions."""
    HAPPY = "happy"
    SAD = "sad"
    WORRIED = "worried"
    HUNGRY = "hungry"
    ANGRY = "angry"

class Pet:
    """Virtual pet class with stages, emotions, and affection system."""
    
    def _get_pet_theme_colors(self):
        """Get theme colors based on pet type."""
        pet_themes = {
            'axolotl': {'bg_main': '#FDF2F8', 'text_pink': '#EC4899'},
            'cat': {'bg_main': '#F8F9FA', 'text_pink': '#8B5CF6'},
            'dog': {'bg_main': '#FFFBF0', 'text_pink': '#F59E0B'},
            'raccoon': {'bg_main': '#FEF7ED', 'text_pink': '#DC2626'},
            'penguin': {'bg_main': '#FFFFFF', 'text_pink': '#000000'}
        }

        pet_type_str = self.pet_type.value.lower() if hasattr(self.pet_type, 'value') else str(self.pet_type).lower()
        return pet_themes.get(pet_type_str, pet_themes['penguin'])
    
    @property
    def affection_cap(self) -> int:
        """Get the current affection cap based on the pet's stage."""
        if not hasattr(self, '_stage'):
            return 200  # Default cap if stage not set
        return 1000 if self.stage == PetStage.BATTLE_FIT else 200
    
    @property
    def affection_percentage(self) -> float:
        """Get the current affection as a percentage of the current cap."""
        return (self.affection / self.affection_cap) * 100 if self.affection_cap > 0 else 0

    def __init__(self, pet_type: PetType, name: str = ""):
        self.pet_type = pet_type
        self.name = name or pet_type.value
        self._stage = PetStage.EGG
        self._emotion = PetEmotion.HAPPY
        self._affection = 0
        self.experience = 0
        self.level = 1
        self.hatch_time = None

        # Theme-related attributes
        self.theme_colors = self._get_pet_theme_colors()
        self.bg_color = self.theme_colors.get('bg_main', '#FFFFFF')
        self.accent_color = self.theme_colors.get('text_pink', '#000000')

        # Load pet configuration data
        self.pet_data = self._load_pet_data()
        self.stage_targets = self._build_stage_targets()
        
        # Initialize state with default emotion
        self._emotion = PetEmotion.HAPPY
    
    @property
    def stage(self) -> PetStage:
        return self._stage
    
    @stage.setter
    def stage(self, value):
        # Convert to PetStage if it's an int
        if isinstance(value, int):
            value = PetStage(value)
            
        old_stage = getattr(self, '_stage', None)
        
        # Only proceed if the stage is actually changing
        if old_stage == value:
            return
            
        # Update the stage
        self._stage = value
        
        # Reset affection when stage changes
        self._affection = 0
        self._update_emotion()
    
    @property
    def emotion(self) -> PetEmotion:
        return self._emotion
    
    @emotion.setter
    def emotion(self, value):
        # Handle both string and PetEmotion values
        if isinstance(value, str):
            try:
                self._emotion = PetEmotion(value.lower())
            except (ValueError, AttributeError):
                self._emotion = PetEmotion.HAPPY
        elif isinstance(value, int):
            try:
                self._emotion = PetEmotion(value)
            except (ValueError, AttributeError):
                self._emotion = PetEmotion.HAPPY
        elif isinstance(value, PetEmotion):
            self._emotion = value
        else:
            self._emotion = PetEmotion.HAPPY
    
    @property
    def affection(self) -> int:
        return self._affection
    
    @affection.setter
    def affection(self, value: int):
        old_value = self._affection
        self._affection = max(0, min(value, self.affection_cap))
        self._update_emotion()

        # Check for evolution only when affection actually changes and is positive
        if self._affection > 0 and self._affection != old_value:
            self._check_evolution()
        
    def _load_pet_data(self) -> Dict:
        """Load pet data from JSON configuration."""
        try:
            data_path = os.path.join(
                os.path.dirname(__file__), 
                '..', '..', 'game_data', 'pets.json'
            )
            with open(data_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # Return default data if file doesn't exist
            return self._get_default_pet_data()
    
    def _get_default_pet_data(self) -> Dict:
        """Return default pet configuration."""
        return {
            pet_type.value: {
                "stages": {
                    str(stage.value): {
                        "name": f"{pet_type.value.capitalize()} {stage.name.capitalize()}",
                        "affection_required": 200 if stage.value <= 4 else 1000,
                        "image": f"{pet_type.value}_{stage.value}.png"
                    } for stage in PetStage
                },
                "emotions": {
                    emotion.value: {
                        "image": f"{pet_type.value}_{emotion.value}.png",
                        "description": emotion.value.capitalize()
                    } for emotion in PetEmotion
                }
            } for pet_type in PetType
        }
    
    def get_current_stage_info(self) -> Dict:
        """Get information about the current stage."""
        pet_config = self.pet_data.get(self.pet_type.value, {})
        stages = pet_config.get("stages", {})
        return stages.get(str(self.stage.value), {})
    
    def get_current_emotion_info(self) -> Dict:
        """Get information about the current emotion."""
        pet_config = self.pet_data.get(self.pet_type.value, {})
        emotions = pet_config.get("emotions", {})
        return emotions.get(self.emotion.value, {})
    
    def _build_stage_targets(self) -> Dict[int, int]:
        """Build affection targets for each stage with fixed values."""
        return {
            PetStage.EGG.value: 200,
            PetStage.BABY.value: 200,
            PetStage.CHILD.value: 200,
            PetStage.GROWN.value: 200,
            PetStage.BATTLE_FIT.value: 1000
        }

    def add_affection(self, amount: int) -> bool:
        """Add affection points and check for stage evolution. Returns True if evolved."""
        if amount == 0:
            self._update_emotion_from_affection(amount)
            return False

        self.affection = max(0, self.affection + amount)
        if amount > 0:
            self.experience += amount

        evolved = self._check_evolution()

        # Update emotion based on affection gain
        self._update_emotion_from_affection(amount)

        # Ensure affection is not negative after adjustments
        if self.affection < 0:
            self.affection = 0
        if evolved and self.affection < 0:
            self.affection = 0

        # Return evolution status for UI updates
        return evolved
    
    def _check_evolution(self) -> bool:
        """Check if pet should evolve to the next stage. Returns True if evolved."""
        max_stage = max(stage.value for stage in PetStage)
        current_stage_value = self.stage.value
        required_affection = self.stage_targets.get(current_stage_value, 0)

        # Fallback if stage_targets not properly initialized
        if required_affection <= 0:
            if current_stage_value <= 4:
                required_affection = 200  # Stages 1-4
            else:
                required_affection = 1000  # Stage 5

        evolved = False
        while current_stage_value < max_stage and self.affection >= required_affection:
            self.affection = 0  # Reset affection to 0 when evolving
            current_stage_value += 1
            self.stage = PetStage(current_stage_value)
            self.level += 1
            self.emotion = PetEmotion.HAPPY

            # Set hatch time when evolving from egg (stage 1 to stage 2)
            if current_stage_value == 2:  # Just hatched
                import time
                self.hatch_time = time.time()

            evolved = True
            # Get requirement for next stage
            required_affection = self.stage_targets.get(current_stage_value, 200 if current_stage_value <= 4 else 1000)

        if current_stage_value >= max_stage:
            # Final stage (Battle-fit) cap at 1000 instead of 500
            cap = self.stage_targets.get(current_stage_value, 1000)
            if self.affection > cap:
                self.affection = cap

        return evolved
    
    def _update_emotion_from_affection(self, affection_gained: int):
        """Update pet emotion based on affection gained."""
        import random
        
        if affection_gained >= 30:
            # Large affection gain - happy
            self.emotion = PetEmotion.HAPPY
        elif affection_gained >= 10:
            # Medium affection gain - happy
            self.emotion = PetEmotion.HAPPY
        elif affection_gained >= 1:
            # Small affection gain - worried
            self.emotion = PetEmotion.WORRIED
        elif affection_gained == 0:
            # No affection change - stay current or become happy
            if random.random() < 0.7:  # 70% chance to stay current
                pass  # Keep current emotion
            else:
                self.emotion = PetEmotion.HAPPY
        else:
            # Negative affection (shouldn't happen normally) - sad or hungry
            self.emotion = random.choice([PetEmotion.SAD, PetEmotion.HUNGRY])
    
    def set_emotion(self, emotion: PetEmotion):
        """Manually set pet emotion."""
        self.emotion = emotion
    
    def update_emotion_over_time(self):
        """Update pet emotion based on time passage and current state."""
        import random
        import datetime
        
        # Get current hour to determine time-based emotions
        current_hour = datetime.datetime.now().hour
        
        # Random chance for emotion changes (10% chance every call)
        if random.random() < 0.1:
            # Time-based emotion tendencies
            if 22 <= current_hour or current_hour <= 6:  # Night/early morning
                # More likely to be happy or worried (night owls)
                if self.emotion not in [PetEmotion.SAD, PetEmotion.ANGRY]:
                    self.emotion = random.choice([PetEmotion.HAPPY, PetEmotion.WORRIED])
            elif 12 <= current_hour <= 14:  # Lunch time
                # More likely to be hungry or happy
                if random.random() < 0.3:
                    self.emotion = PetEmotion.HUNGRY
            elif 6 <= current_hour <= 12:  # Morning
                # More likely to be happy or worried (just woke up)
                if self.emotion != PetEmotion.ANGRY:
                    self.emotion = random.choice([PetEmotion.HAPPY, PetEmotion.WORRIED])
    
    def _update_emotion(self):
        """Update pet's emotion based on affection percentage."""
        if not hasattr(self, '_affection') or not hasattr(self, 'affection_cap'):
            self._emotion = PetEmotion.HAPPY
            return
            
        if self.affection_cap == 0:  # Prevent division by zero
            percentage = 0
        else:
            percentage = (self._affection / self.affection_cap) * 100
            
        if percentage < 20:
            self._emotion = PetEmotion.SAD
        elif percentage < 40:
            self._emotion = PetEmotion.WORRIED
        elif percentage < 60:
            self._emotion = PetEmotion.HUNGRY
        elif percentage < 80:
            self._emotion = PetEmotion.HAPPY
        else:
            self._emotion = PetEmotion.ANGRY

    def trigger_contextual_emotion(self, context: str):
        """Trigger emotions based on specific contexts."""
        import random
        
        context_emotions = {
            "study_success": [PetEmotion.HAPPY],
            "long_study": [PetEmotion.WORRIED, PetEmotion.HAPPY],
            "quiz_correct": [PetEmotion.HAPPY],
            "quiz_wrong": [PetEmotion.SAD, PetEmotion.HAPPY],
            "no_interaction": [PetEmotion.SAD, PetEmotion.HUNGRY],
            "feeding": [PetEmotion.HAPPY],
            "neglect": [PetEmotion.SAD, PetEmotion.ANGRY],
            "play": [PetEmotion.HAPPY, PetEmotion.WORRIED]
        }
        
        if context in context_emotions:
            self.emotion = random.choice(context_emotions[context])
    
    def get_image_path(self) -> str:
        """Get the image path for current stage and emotion."""
        stage_info = self.get_current_stage_info()
        if not stage_info:
            return os.path.join("assets", "img", "placeholder.png")
            
        # Try to get emotion-specific image first
        emotion_map = stage_info.get("emotions", {})
        emotion_image = emotion_map.get(self.emotion.value.lower(), "")
        
        if emotion_image:
            return os.path.join("assets", "img", emotion_image)
        
        # Fall back to stage image
        stage_image = stage_info.get("image", "")
        if stage_image:
            return os.path.join("assets", "img", stage_image)
        
        # Default placeholder
        return os.path.join("assets", "img", "placeholder.png")
    
    def get_current_stage_limit(self) -> int:
        """Get the affection limit for the current stage."""
        if self.stage == PetStage.BATTLE_FIT:
            return 1000
        return 200  # Default cap for other stages
    def to_dict(self) -> Dict:
        """Convert pet to dictionary for saving.
        
        Returns:
            dict: A dictionary containing only the essential pet data.
        """
        return {
            "pet_type": self.pet_type.value if hasattr(self.pet_type, 'value') else str(self.pet_type),
            "name": self.name
        }

    @classmethod
    def from_dict(cls, data: Dict):
        """Create pet from dictionary with validation."""
        try:
            # Validate required fields
            required_fields = ['pet_type', 'name', 'stage', 'emotion', 'affection', 'experience', 'level']
            for field in required_fields:
                if field not in data:
                    print(f"Warning: Missing required field '{field}' in pet data")
                    data[field] = 0 if field in ['affection', 'experience', 'level'] else ""

            # Create pet with validated data
            pet = cls(
                PetType(data["pet_type"]) if "pet_type" in data else PetType.PENGUIN,
                data.get("name", "Unnamed Pet")
            )

            # Set stage
            stage_value = data.get("stage", 1)
            if isinstance(stage_value, int):
                pet.stage = PetStage(min(max(1, stage_value), max(s.value for s in PetStage)))

            # Set emotion
            emotion_value = data.get("emotion", "happy")
            if isinstance(emotion_value, str):
                try:
                    pet.emotion = PetEmotion(emotion_value.lower())
                except ValueError:
                    pet.emotion = PetEmotion.HAPPY

            # Set other attributes
            pet.affection = max(0, int(data.get("affection", 0)))
            pet.experience = max(0, int(data.get("experience", 0)))
            pet.level = max(1, int(data.get("level", 1)))
            pet.hatch_time = data.get("hatch_time")

            return pet

        except Exception as e:
            print(f"Error creating pet from dict: {e}")
            # Return a default pet if there's an error
            return cls(PetType.PENGUIN, "Recovery Pet")