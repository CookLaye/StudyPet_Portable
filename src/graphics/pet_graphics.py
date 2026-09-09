# src/graphics/pet_graphics.py
import os
import logging
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image, ImageTk
import tkinter as tk
logger = logging.getLogger('PetGraphics')
if not logger.handlers:
    logger.setLevel(logging.INFO)
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(_handler)
    logger.propagate = False

# Optional file logging (disabled):
# _file_handler = logging.FileHandler('pet_graphics.log')
# _file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
# logger.addHandler(_file_handler)

class PetGraphics:
    """
    Pet graphics system for loading and caching pet images.
    
    === Attributes ===
    image_cache: Dictionary of cached PIL Image objects
    img_base_path: Base path to pet images directory
    pets: Configuration dictionary for pet types
    stages: Mapping of stage numbers to stage names
    default_emotion: Default emotion for pets
    """
    def __init__(self):
        """Initialize the PetGraphics system with simplified image handling."""
        self.image_cache = {}
        
        # Get the project root directory (one level up from src)
        project_root = Path(__file__).parent.parent.parent
        self.img_base_path = os.path.join(project_root, 'assets', 'img')
        
        # Verify the img directory exists
        if not os.path.exists(self.img_base_path):
            logger.warning(f"Image directory not found: {self.img_base_path}")
            # Try to create the directory
            try:
                os.makedirs(self.img_base_path, exist_ok=True)
                logger.info(f"Created image directory: {self.img_base_path}")
            except Exception as e:
                logger.error(f"Failed to create image directory: {e}")
        
        logger.info(f"Initializing PetGraphics. Base image path: {self.img_base_path}")
        
    # === Configuration ===
    # Pet configuration - matches folder names exactly
        self.pets = {
            'cat': {'emoji': '🐱', 'folder': 'Cat'},
            'dog': {'emoji': '🐶', 'folder': 'Dog'},
            'axolotl': {'emoji': '🦎', 'folder': 'Axolotl'},
            'raccoon': {'emoji': '🦝', 'folder': 'Raccoon'},
            'penguin': {'emoji': '🐧', 'folder': 'Penguin'}
        }
        
        # Stage names (1-5) - must match the filenames exactly
        self.stages = {
            1: 'Egg',      # Filename: {PetType}_Egg.png
            2: 'Baby',     # Filename: {PetType}_Baby_{Emotion}.png
            3: 'Child',    # Filename: {PetType}_Child_{Emotion}.png
            4: 'Grown',    # Filename: {PetType}_Grown_{Emotion}.png
            5: 'Battle_Fit' # Filename: {PetType}_Battle_Fit_{Emotion}.png
        }

        # All supported emotions (must match capitalised filename suffixes)
        self.valid_emotions = {'Happy', 'Sad', 'Worried', 'Angry', 'Hungry'}

        # Default emotion if none specified
        self.default_emotion = 'Happy'  # Must match the case in filenames
        
        # Log available images at startup
        self.log_available_images()
        
    # === Helper Methods ===
    def _get_pet_folder(self, pet_type: str) -> str:
        """Get folder name for a pet type."""
        if not pet_type:
            return 'Cat'  # Default to Cat if pet_type is None or empty
        pet = self.pets.get(str(pet_type).lower())
        return pet['folder'] if pet else 'Cat'  # Default to Cat if pet type not found
    
    def get_fallback_emoji(self, pet_type: str) -> str:
        """Get fallback emoji for a pet type."""
        if not pet_type:
            return '❓'  # Default emoji if pet_type is None or empty
        pet = self.pets.get(str(pet_type).lower())
        return pet['emoji'] if pet else '❓'  # Default question mark emoji
    
    def _get_stage_name(self, stage: int) -> str:
        """Get display name for a stage."""
        return self.stages.get(stage, 'Egg')  # Default to Egg if stage not found
    
    # === Public API ===
    def get_pet_image(self, pet_type: str, stage: int = 1, 
                     emotion: str = None, size: Tuple[int, int] = (200, 200)) -> Optional[ImageTk.PhotoImage]:
        """
        Load a pet image and return a PhotoImage object.

        Args:
            pet_type: Type of pet (e.g., 'cat', 'dog')
            stage: Pet stage (1-5)
            emotion: Pet emotion (e.g., 'Happy', 'Sad')
            size: Size of image (width, height)
            
        Returns:
            A PhotoImage object or None if image not found
        """
        if not pet_type:
            logger.warning("No pet type provided")
            return None
            
        # Normalize inputs and validate
        try:
            pet_type = str(pet_type).lower()
            stage = int(stage) if stage else 1
            emotion = str(emotion) if emotion else self.default_emotion
            
            # Validate stage
            if stage not in self.stages:
                logger.warning(f"Invalid stage: {stage}. Defaulting to 1 (Egg)")
                stage = 1
                
            # Special case: Egg stage doesn't have emotions
            if stage == 1:
                emotion = None
                
            cache_key = f"{pet_type}_{stage}_{emotion}_{size[0]}x{size[1]}"
            
            # Check cache first
            if cache_key in self.image_cache:
                return self.image_cache[cache_key]
            
            # Get the image path
            image_path = self._get_pet_image_path(pet_type, stage, emotion)
            
            if not image_path or not os.path.exists(image_path):
                logger.warning(f"No image found for {pet_type} stage {stage} (emotion: {emotion})")
                return None
                
            # Try to load and process the image
            try:
                logger.info(f"Loading image: {image_path}")
                # Load and resize image
                pil_image = Image.open(image_path).convert('RGBA')
                
                # Resize while maintaining aspect ratio
                pil_image.thumbnail(size, Image.Resampling.LANCZOS)
                
                # Convert to PhotoImage
                photo_image = ImageTk.PhotoImage(pil_image)
                
                # Cache the image
                self.image_cache[cache_key] = photo_image
                logger.debug(f"Cached image as {cache_key}")
                
                return photo_image
                
            except Exception as e:
                logger.error(f"Error loading image {image_path}: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Error processing pet image request: {e}")
            return None
        
        # All image loading is now handled in the try-except block above
    
    def _get_pet_image_path(self, pet_type: str, stage: int, emotion: str) -> Optional[str]:
        """
        Get the file path for a pet image using the standardized naming convention:
        {PetType}_{Stage}_{Emotion}.png or {PetType}_Egg.png for egg stage
        
        Args:
            pet_type: Type of pet (e.g., 'cat', 'dog')
            stage: Pet stage (1-5)
            emotion: Pet emotion (e.g., 'Happy')
            
        Returns:
            Path to the image file or None if not found
        """
        if not pet_type:
            return None

        # Normalize inputs
        pet_type = str(pet_type).lower()
        stage = int(stage) if stage else 1
        emotion = str(emotion).capitalize() if emotion and stage > 1 else None

        # Validate emotion against known set; fall back to Happy if unrecognised
        if emotion and emotion not in self.valid_emotions:
            logger.warning(f"Unknown emotion '{emotion}', falling back to Happy")
            emotion = 'Happy'

        # Get folder and stage name
        folder_name = self._get_pet_folder(pet_type)
        stage_name = self._get_stage_name(stage)

        # Special case for egg stage (no emotion)
        if stage_name.lower() == 'egg':
            filename = f"{pet_type.capitalize()}_Egg.png"
        else:
            filename = f"{pet_type.capitalize()}_{stage_name}_{emotion}.png"

        # Check in the pet's folder
        pet_dir = os.path.join(self.img_base_path, folder_name)
        image_path = os.path.join(pet_dir, filename)

        if os.path.exists(image_path):
            logger.debug(f"Found image: {image_path}")
            return image_path

        # Try alternative paths for backward compatibility
        em_lower = emotion.lower() if emotion else ''
        alt_paths = [
            os.path.join(self.img_base_path, filename),
            os.path.join(pet_dir, f"{pet_type.capitalize()}_{stage_name.lower()}_{em_lower}.png"),
            os.path.join(pet_dir, f"{pet_type.lower()}_{stage_name.lower()}_{em_lower}.png")
        ]

        for alt_path in alt_paths:
            if os.path.exists(alt_path):
                logger.debug(f"Found image at alternative path: {alt_path}")
                return alt_path

        logger.warning(f"No image found for {pet_type} stage {stage} (emotion: {emotion}) at {image_path}")
        return None
    
    def create_pet_display_widget(self, parent, pet_type: str, stage: int = 1, 
                               emotion: str = None, size: Tuple[int, int] = (100, 100),
                               **kwargs) -> tk.Widget:
        """
        Create a widget displaying the pet's image or emoji fallback.
        
        Args:
            parent: Parent widget
            pet_type: Type of pet (e.g., 'cat', 'dog')
            stage: Pet stage (1-5)
            emotion: Pet emotion (e.g., 'Happy', 'Sad')
            size: Size of the image (width, height)
            **kwargs: Additional arguments to pass to the Label widget
            
        Returns:
            A Tkinter Label widget displaying the pet's image or emoji
        """
        # Try to load the pet image
        image = self.get_pet_image(pet_type, stage, emotion, size)
        
        # Create a label with default styling
        label = tk.Label(
            parent,
            bg=kwargs.pop('bg', 'white'),
            bd=kwargs.pop('bd', 0),
            highlightthickness=kwargs.pop('highlightthickness', 0),
            **kwargs
        )

        if image:
            # If we have an image, use it
            label.image = image  # Keep a reference to prevent garbage collection
            label.config(image=image)
        else:
            # Fallback to emoji
            emoji = self.get_fallback_emoji(pet_type)
            font_size = max(12, min(size) // 2)  # Ensure minimum font size
            label.config(
                text=emoji,
                font=('Arial', font_size, 'bold'),
                fg='black'
            )
            
        # Make the label clickable if needed
        if kwargs.get('clickable', True):
            # Store the data as attributes on the label
            label.pet_type = pet_type
            label.pet_stage = stage
            
            def on_click(event):
                # Create a custom event with the data
                event.widget.pet_type = pet_type
                event.widget.pet_stage = stage
                event.widget.event_generate('<<PetSelected>>')
                
            label.bind('<Button-1>', on_click)
        
        return label

    def log_available_images(self):
        """Log all available pet images in the img directory."""
        if not os.path.exists(self.img_base_path):
            logger.warning(f"Image directory not found: {self.img_base_path}")
            return
            
        logger.info("Available pet images:")
        try:
            for pet_type in os.listdir(self.img_base_path):
                pet_dir = os.path.join(self.img_base_path, pet_type)
                if os.path.isdir(pet_dir):
                    images = [f for f in os.listdir(pet_dir) 
                             if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
                    logger.info(f"  {pet_type}: {len(images)} images")
        except Exception as e:
            logger.error(f"Error listing available images: {e}")

# Global instance
pet_graphics = PetGraphics()

# For backward compatibility
get_pet_image = pet_graphics.get_pet_image
get_fallback_emoji = pet_graphics.get_fallback_emoji
create_pet_display_widget = pet_graphics.create_pet_display_widget