"""
Simple Playground Renderer - A minimal implementation to display and move a pet
"""

import os
import time
import tkinter as tk
from tkinter import Canvas
from PIL import Image, ImageTk, ImageDraw, ImageFont
import logging
from src.models.state_manager import state_manager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimplePlayground:
    """
    A simple playground that displays a movable pet.
    
    === Attributes ===
    canvas: Tkinter canvas for rendering
    pet_type: Current pet type (e.g., 'cat', 'dog')
    pet_stage: Current pet stage (1-5)
    pet_emotion: Current pet emotion (e.g., 'happy', 'sad')
    """
    
    # === Constants ===
    # Default facing directions for each pet type and emotion
    # 'right' means original image faces right, 'left' means it faces left
    PET_FACING_DIRECTIONS = {
        # Format: 'pettype_emotion': 'direction'
        # Default to right if not specified
        'raccoon': {
            'happy': 'right',
            'sad': 'right',
            'angry': 'right',
            'hungry': 'right',
            'worried': 'right'
        },
        'cat': {
            'happy': 'right',
            'sad': 'right',
            'angry': 'right',
            'hungry': 'right',
            'worried': 'right'
        },
        'dog': {
            'happy': 'right',
            'sad': 'right',
            'angry': 'right',
            'hungry': 'right',
            'worried': 'right'
        },
        'penguin': {
            'happy': 'right',
            'sad': 'right',
            'angry': 'right',
            'hungry': 'right',
            'worried': 'right'
        },
        'axolotl': {
            'happy': 'right',
            'sad': 'right',
            'angry': 'right',
            'hungry': 'right',
            'worried': 'right'
        }
    }
    
    # === Lifecycle Methods ===
    def __init__(self, canvas: Canvas, pet_type: str = None, pet_stage: int = None, pet_emotion: str = None, app_state=None):
        """Initialize the playground with a canvas and pet type."""
        self.canvas = canvas
        self.app_state = app_state
        self._bindings = []  # Track event bindings for cleanup

        # Clean up any existing instance on this canvas
        if hasattr(canvas, '_playground_instance'):
            canvas._playground_instance.cleanup()
        canvas._playground_instance = self

        # Initialize with default values that will be overridden by state manager
        # Use app_state for fallbacks if available
        pet_type_fallback = 'Raccoon'
        stage_fallback = 4
        emotion_fallback = 'happy'

        if self.app_state:
            pet_type_fallback = getattr(self.app_state, 'pet_type', 'Raccoon')
            stage_fallback = getattr(self.app_state, 'stage', 4)
            if hasattr(stage_fallback, 'value'):
                stage_fallback = stage_fallback.value
            emotion_fallback = getattr(self.app_state, 'emotion', 'happy')
            if hasattr(emotion_fallback, 'name'):
                emotion_fallback = emotion_fallback.name.lower()
            else:
                emotion_fallback = str(emotion_fallback).lower()

        # Set initial values, using provided values or falling back to app state
        self.pet_type = (pet_type or
                        pet_type_fallback).capitalize()
        self.pet_stage = (pet_stage if pet_stage is not None
                         else stage_fallback)
        # Convert stage from PetStage enum to int if needed
        if hasattr(self.pet_stage, 'value'):
            self.pet_stage = self.pet_stage.value

        # Handle pet_emotion initialization, converting PetEmotion to string if needed
        emotion = pet_emotion or emotion_fallback
        self.pet_emotion = str(emotion).lower() if emotion is not None else 'happy'
        
        # Set up canvas
        self.canvas.update_idletasks()
        self.width = max(self.canvas.winfo_width(), 800)
        self.height = max(self.canvas.winfo_height(), 600)
        
        # Set a nice gradient background
        self._setup_background()
        
        # Pet state
        # Size is now proportional to the canvas size to ensure consistent appearance across resolutions
        self.pet_size = min(self.width, self.height) // 4
        self.pet_x = self.width // 2
        # Lower the rest position (moved down by 100 pixels)
        self.pet_y = (self.height // 2) + 100
        self.target_x = self.pet_x
        self.target_y = self.pet_y
        self.speed = 4  # Slightly slower speed
        self.is_moving = False
        self._is_flipped = False  # Initialize flip state
        self._current_image_key = None  # Track currently displayed image
        
        # Animation
        self.animation_timer = None
        
        # Subscribe to state changes
        state_manager.subscribe(self._handle_state_change)
        self.update_interval = 50  # 20 FPS
        
        # Load pet image
        self.pet_image = None
        self.pet_photo = None
        self.pet_id = None
        self._load_pet_image()
        
        # Set up event bindings
        self._setup_bindings()
        
        # Start animation loop
        self._start_animation()
    
    def _handle_state_change(self, change_type):
        """Handle state changes from the state manager"""

        try:
            if not self.app_state:
                return

            # Get current state values
            current_emotion = getattr(self.app_state, 'emotion', None)
            current_stage = getattr(self.app_state, 'stage', None)

            # Only update if we have valid state values
            if current_emotion is not None and current_stage is not None:
                self.update_pet_state(
                    pet_stage=current_stage.value if hasattr(current_stage, 'value') else current_stage,
                    pet_emotion=current_emotion.name.lower() if hasattr(current_emotion, 'name') else str(current_emotion).lower()
                )
        except Exception as e:
            logger.error(f"Error handling state change: {e}")
            import traceback
            traceback.print_exc()
    
    def _return_to_rest_position(self):
        """Return the pet to its rest position"""
        self.target_x = self.width // 2
        self.target_y = (self.height // 2) + 100  # Rest position Y
        self.pet_x = self.target_x
        self.pet_y = self.target_y
        self.is_moving = False
        self._update_pet_position()
    
    def update_pet_state(self, pet_type=None, pet_stage=None, pet_emotion=None):
        """Update the pet's state and refresh the display"""
        was_egg = getattr(self, 'pet_stage', 4) == 1
        needs_update = False
        
        try:
            # Handle pet type update
            if pet_type and str(pet_type).lower() != getattr(self, 'pet_type', '').lower():
                self.pet_type = str(pet_type).capitalize()
                needs_update = True
                logger.debug(f"Pet type updated to: {self.pet_type}")
            
            # Handle stage update
            if pet_stage is not None:
                # Convert stage to int if it's an enum
                stage_value = pet_stage.value if hasattr(pet_stage, 'value') else pet_stage
                if stage_value != getattr(self, 'pet_stage', None):
                    self.pet_stage = stage_value
                    needs_update = True
                    logger.debug(f"Pet stage updated to: {self.pet_stage}")
            
            # Handle emotion update
            if pet_emotion is not None:
                emotion_str = str(pet_emotion).lower()
                if emotion_str != getattr(self, 'pet_emotion', '').lower():
                    self.pet_emotion = emotion_str
                    needs_update = True
                    logger.debug(f"Pet emotion updated to: {self.pet_emotion}")
            
            # Only reload if something actually changed
            if needs_update:
                logger.info(f"Updating pet display - Type: {self.pet_type}, Stage: {self.pet_stage}, Emotion: {self.pet_emotion}")
                self._load_pet_image()
                
                # If changing to/from egg stage, update position
                is_egg = getattr(self, 'pet_stage', 4) == 1
                if is_egg or was_egg:
                    self._return_to_rest_position()
                
        except Exception as e:
            logger.error(f"Error in update_pet_state: {e}")
            import traceback
            traceback.print_exc()
    
    def _canvas_exists(self):
        """Check if the canvas widget still exists and is valid"""
        try:
            return (hasattr(self, 'canvas') and 
                   self.canvas is not None and 
                   self.canvas.winfo_exists() == 1)
        except Exception:
            return False
            
    def _load_pet_image(self):
        """Load the appropriate pet image based on type, stage, and emotion"""
        try:
            # Clean up previous image if it exists
            if hasattr(self, 'pet_image') and self.pet_image:
                try:
                    self.pet_image.close()
                except Exception as e:
                    logger.debug(f"Error closing previous image: {e}")
                self.pet_image = None
            
            # Map stage numbers to names
            stage_map = {
                1: 'Egg',
                2: 'Baby',
                3: 'Child',
                4: 'Grown',
                5: 'Grown'  # Fallback to Grown for any higher stages
            }
            
            # Get stage name, default to 'Grown' if not found
            stage_name = stage_map.get(self.pet_stage, 'Grown')
            
            # Get current emotion, default to 'Happy' if not set
            emotion = getattr(self, 'pet_emotion', 'happy').capitalize()
            
            # Special case for Egg stage - it doesn't have emotions
            if stage_name == 'Egg':
                img_name = f"{self.pet_type.title()}_{stage_name}.png"
            else:
                img_name = f"{self.pet_type.title()}_{stage_name}_{emotion}.png"

            # Try to find the image in the img directory
            img_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'assets', 'img', self.pet_type.title()
            )
            
            img_path = os.path.join(img_dir, img_name)
            
            # If the exact image isn't found, try to find any image for this pet
            if not os.path.exists(img_path):
                logger.warning(f"Pet image not found at {img_path}, searching for alternatives...")
                
                # Try to find any image for this pet
                if os.path.exists(img_dir):
                    for file in os.listdir(img_dir):
                        if file.lower().startswith(self.pet_type.lower()) and file.lower().endswith(('.png', '.jpg', '.jpeg')):
                            img_path = os.path.join(img_dir, file)
                            logger.info(f"Using alternative image: {img_path}")
                            break
            
            # Load the image if found, otherwise create a fallback
            if os.path.exists(img_path):
                try:
                    self.pet_image = Image.open(img_path).convert('RGBA')
                    # Resize while maintaining aspect ratio
                    width, height = self.pet_image.size
                    scale = min(self.pet_size / width, self.pet_size / height) * 0.8  # 80% of the cell
                    new_width = int(width * scale)
                    new_height = int(height * scale)
                    self.pet_image = self.pet_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    logger.info(f"Loaded pet image: {img_path} (resized to {new_width}x{new_height})")
                    
                    # Store the original image for flipping
                    self.original_image = self.pet_image.copy()
                    
                    # Initialize image cache if it doesn't exist
                    if not hasattr(self, '_image_cache'):
                        self._image_cache = {}
                    
                    # Create a cache key for the current state
                    direction = 'left' if getattr(self, '_is_flipped', False) else 'right'
                    current_type = getattr(self, 'pet_type', 'Raccoon').lower()
                    current_emotion = getattr(self, 'pet_emotion', 'happy').lower()
                    
                    # Cache the clean image with the appropriate key
                    cache_key = f"{current_type}_{current_emotion}_{direction}"
                    self._image_cache[cache_key] = self.original_image
                    
                    # Convert to PhotoImage - must keep a reference!
                    self.pet_photo = ImageTk.PhotoImage(self.pet_image)
                    
                    # Update the display
                    self._update_pet_display()
                    
                except Exception as e:
                    logger.error(f"Error loading image {img_path}: {e}")
                    self._create_fallback_image()
            else:
                logger.warning("No pet image found, using fallback")
                self._create_fallback_image()
                
        except Exception as e:
            logger.error(f"Error in _load_pet_image: {e}", exc_info=True)
            self._create_fallback_image()
    
    def _update_pet_display(self):
        """Update the pet's image on the canvas"""
        if not hasattr(self, 'pet_photo') or not self.pet_photo:
            return
            
        try:
            if not self._canvas_exists():
                return
                
            if hasattr(self, 'pet_id') and self.pet_id:
                try:
                    self.canvas.itemconfig(self.pet_id, image=self.pet_photo)
                except tk.TclError as e:
                    if "invalid command name" in str(e):
                        logger.warning("Canvas command failed, widget may be destroyed")
                    else:
                        logger.error(f"Error updating pet display: {e}", exc_info=True)
            else:
                self.pet_id = self.canvas.create_image(
                    self.pet_x, self.pet_y,
                    image=self.pet_photo,
                    anchor=tk.CENTER,
                    tags=("pet",)
                )
                
            # Make sure the pet is visible
            self.canvas.tag_raise("pet")
            
        except Exception as e:
            logger.error(f"Error updating pet display: {e}", exc_info=True)
    
    def _setup_background(self):
        """Set up the background with a pet-specific image or fallback to gradient"""
        try:
            # Get the project root directory
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            
            # First try to find a background image in the Background directory
            bg_dir = os.path.join(project_root, 'assets', 'img', 'Background')
            
            # Look for pet-specific background images
            pet_name = getattr(self, 'pet_type', '').lower()
            if not pet_name:
                logger.warning("No pet type set, using default background")
                self._create_gradient_background()
                return
                
            # Try to find a background image in the Background directory
            if os.path.exists(bg_dir):
                # Try different case variations and extensions
                base_name = pet_name.lower()
                extensions = ['.png', '.jpg', '.jpeg']
                
                for ext in extensions:
                    # Try exact case first
                    filename = f"{base_name}{ext}"
                    bg_path = os.path.join(bg_dir, filename)
                    
                    if os.path.exists(bg_path):
                        try:
                            # Load and resize the background image
                            bg_image = Image.open(bg_path).convert('RGB')
                            bg_image = bg_image.resize((self.width, self.height), Image.Resampling.LANCZOS)
                            self.bg_photo = ImageTk.PhotoImage(bg_image)
                            
                            # Clear any existing background
                            self.canvas.delete("bg")
                            self.canvas.create_image(0, 0, image=self.bg_photo, anchor='nw', tags=("bg",))
                            logger.info(f"Loaded background image: {bg_path}")
                            return
                            
                        except Exception as e:
                            logger.warning(f"Error loading background image {filename}: {e}")
                
                # If no pet-specific background found, try title case
                title_name = pet_name.title()
                if title_name != base_name:
                    for ext in extensions:
                        filename = f"{title_name}{ext}"
                        bg_path = os.path.join(bg_dir, filename)
                        
                        if os.path.exists(bg_path):
                            try:
                                bg_image = Image.open(bg_path).convert('RGB')
                                bg_image = bg_image.resize((self.width, self.height), Image.Resampling.LANCZOS)
                                self.bg_photo = ImageTk.PhotoImage(bg_image)
                                
                                # Clear any existing background
                                self.canvas.delete("bg")
                                self.canvas.create_image(0, 0, image=self.bg_photo, anchor='nw', tags=("bg",))
                                logger.info(f"Loaded background image: {bg_path}")
                                return
                                
                            except Exception as e:
                                logger.warning(f"Error loading background image {filename}: {e}")
            
            # If no background image found, try to use the pet's happy image as background
            pet_dir = os.path.join(project_root, 'assets', 'img', pet_name.title())
            if os.path.exists(pet_dir):
                # Look for any happy image of the pet
                for file in os.listdir(pet_dir):
                    if file.lower().endswith(('.png', '.jpg', '.jpeg')) and 'happy' in file.lower():
                        try:
                            bg_image = Image.open(os.path.join(pet_dir, file))
                            logger.info(f"Using pet image as background: {file}")

                            # Resize to fit canvas while maintaining aspect ratio
                            img_ratio = bg_image.width / bg_image.height
                            canvas_ratio = self.width / self.height

                            if img_ratio > canvas_ratio:
                                new_width = int(self.height * img_ratio)
                                new_height = self.height
                            else:
                                new_width = self.width
                                new_height = int(self.width / img_ratio)

                            bg_image = bg_image.resize((new_width, new_height), Image.Resampling.LANCZOS)

                            # Composite onto a solid background
                            result = Image.new('RGB', (self.width, self.height), '#f0f8ff')
                            x = (self.width - new_width) // 2
                            y = (self.height - new_height) // 2

                            if bg_image.mode == 'RGBA':
                                result.paste(bg_image, (x, y), bg_image)
                            else:
                                result.paste(bg_image, (x, y))

                            self.bg_photo = ImageTk.PhotoImage(result)
                            self.canvas.delete("bg")
                            self.canvas.create_image(0, 0, image=self.bg_photo, anchor='nw', tags=("bg",))
                            logger.info(f"Using {file} as background for {pet_name}")
                            return
                            
                        except Exception as e:
                            logger.warning(f"Error creating background from {file}: {e}")
            
            # If we get here, no suitable background was found
            logger.info(f"No background image found for {pet_name}, using gradient")
            self._create_gradient_background()
            
        except Exception as e:
            logger.error(f"Error setting up background: {e}")
            # Fall back to a solid color
            self.canvas.config(bg='#e0f7fa')  # Light blue
    
    def _create_gradient_background(self):
        """Create a gradient background"""
        try:
            
            # Create a new image with a gradient
            bg = Image.new('RGB', (self.width, self.height), '#e0f7fa')
            draw = ImageDraw.Draw(bg)
            
            # Draw a simple gradient
            for y in range(self.height):
                # Calculate color (lighter at the top, slightly darker at the bottom)
                r = int(224 + (y / self.height) * 16)  # 224-240
                g = int(247 - (y / self.height) * 16)  # 247-231
                b = int(250 - (y / self.height) * 16)  # 250-234
                color = f'#{r:02x}{g:02x}{b:02x}'
                draw.line([(0, y), (self.width, y)], fill=color)
            
            # Add some decorative elements
            # Draw a sun in the top right
            sun_radius = min(self.width, self.height) // 6
            draw.ellipse(
                [self.width - sun_radius - 20, 20, 
                 self.width - 20, sun_radius + 20],
                fill='#fff9c4', outline='#fff59d', width=2
            )
            
            # Draw some cloud-like shapes
            for i, (x, y, size) in enumerate([
                (self.width//4, self.height//4, 60),
                (self.width//3, self.height//3, 40),
                (self.width*3//4, self.height//5, 50)
            ]):
                draw.ellipse([x, y, x+size, y+size//2], fill=(255, 255, 255, 204), outline='#e3f2fd')
            
            # Convert to PhotoImage and display
            self.bg_photo = ImageTk.PhotoImage(bg)
            self.canvas.create_image(0, 0, image=self.bg_photo, anchor='nw', tags=("bg",))
            
        except Exception as e:
            logger.error(f"Error creating gradient background: {e}")
            # Fall back to a solid color
            self.canvas.config(bg='#e0f7fa')
    
    def _create_fallback_image(self):
        """Create a simple colored circle as a fallback"""
        
        try:
            # Colors for different pet types with a pastel theme
            colors = {
                'cat': '#a5d6a7', 'dog': '#bcaaa4', 'axolotl': '#f8bbd0',
                'raccoon': '#b0bec5', 'penguin': '#90a4ae',
                'default': '#bbdefb'  # Light blue
            }
            
            color = colors.get(self.pet_type.lower(), colors['default'])
            
            # Create a simple image with a shadow
            size = self.pet_size
            img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Draw shadow
            shadow_offset = size // 30
            shadow_color = (0, 0, 0, 80)
            draw.ellipse(
                (shadow_offset, shadow_offset, 
                 size - shadow_offset, size - shadow_offset),
                fill=shadow_color
            )
            
            # Draw main circle
            padding = size // 10
            draw.ellipse(
                (padding, padding, 
                 size - padding, size - padding),
                fill=color,
                outline='#ffffff',
                width=2
            )
            
            # Add eyes
            eye_size = size // 5
            eye_offset = size // 4
            draw.ellipse(
                (size//2 - eye_offset - eye_size//2, size//2 - eye_size//2,
                 size//2 - eye_offset + eye_size//2, size//2 + eye_size//2),
                fill='white'
            )
            draw.ellipse(
                (size//2 + eye_offset - eye_size//2, size//2 - eye_size//2,
                 size//2 + eye_offset + eye_size//2, size//2 + eye_size//2),
                fill='white'
            )
            
            # Add pupils
            pupil_size = eye_size // 2
            draw.ellipse(
                (size//2 - eye_offset - pupil_size//2, size//2 - pupil_size//2,
                 size//2 - eye_offset + pupil_size//2, size//2 + pupil_size//2),
                fill='black'
            )
            draw.ellipse(
                (size//2 + eye_offset - pupil_size//2, size//2 - pupil_size//2,
                 size//2 + eye_offset + pupil_size//2, size//2 + pupil_size//2),
                fill='black'
            )
            
            # Add a smile
            smile_radius = size // 4
            draw.arc(
                (size//2 - smile_radius, size//2 - smile_radius//2,
                 size//2 + smile_radius, size//2 + smile_radius//2),
                start=0,
                end=180,
                fill='black',
                width=2
            )
            
            # Add text with pet type initial
            try:
                # Try to use a nice font if available
                font_size = size // 3
                try:
                    font = ImageFont.truetype("arial.ttf", font_size)
                except Exception:
                    font = ImageFont.load_default()
                
                # Draw text shadow
                text = self.pet_type[0].upper()
                text_bbox = draw.textbbox((0, 0), text, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]
                
                # Position text in the center of the circle
                text_x = (size - text_width) // 2
                text_y = (size - text_height) // 2 - size // 10  # Slightly above center
                
                # Draw text shadow
                draw.text((text_x+1, text_y+1), text, fill=(0, 0, 0, 76), font=font)
                # Draw main text
                draw.text((text_x, text_y), text, fill='white', font=font)
                
            except Exception as e:
                logger.warning(f"Could not add text to fallback image: {e}")
            
            self.pet_image = img
            self.pet_photo = ImageTk.PhotoImage(img)
            
            # Update the canvas if the pet ID already exists
            if self.pet_id is not None:
                self.canvas.itemconfig(self.pet_id, image=self.pet_photo)
            
        except Exception as e:
            logger.error(f"Error creating fallback image: {e}")
            # If all else fails, just set a colored background
            self.canvas.config(bg='#e0f7fa')
    
    def _setup_bindings(self):
        """Set up mouse and keyboard bindings"""
        # Clear any existing bindings first
        if hasattr(self, '_bindings'):
            for binding in self._bindings:
                try:
                    self.canvas.unbind(binding)
                except Exception:
                    pass

        # Click to move
        self.canvas.bind('<Button-1>', self._on_click)

        # Resize — keep pet centred proportionally when window changes size
        self.canvas.bind('<Configure>', self._on_canvas_resize)

        # Arrow key movement
        bindings = [
            ('<Left>', lambda e: self._move_pet(-self.speed, 0)),
            ('<Right>', lambda e: self._move_pet(self.speed, 0)),
            ('<Up>', lambda e: self._move_pet(0, -self.speed)),
            ('<Down>', lambda e: self._move_pet(0, self.speed))
        ]

        # Store binding tags for cleanup
        self._bindings = [b[0] for b in bindings]

        # Apply bindings
        for event, handler in bindings:
            self.canvas.bind_all(event, handler)

        # Focus the canvas to receive keyboard events
        self.canvas.focus_set()

    def _on_canvas_resize(self, event):
        """Reposition the pet proportionally when the canvas is resized."""
        new_w = event.width
        new_h = event.height
        if new_w < 10 or new_h < 10:
            return  # ignore spurious early events

        old_w = self.width or new_w
        old_h = self.height or new_h

        # Scale current position proportionally
        if old_w > 0 and old_h > 0:
            self.pet_x = int(self.pet_x * new_w / old_w)
            self.pet_y = int(self.pet_y * new_h / old_h)
            self.target_x = int(self.target_x * new_w / old_w)
            self.target_y = int(self.target_y * new_h / old_h)

        self.width = new_w
        self.height = new_h

        # Refresh background and pet at new size
        self._setup_background()
        self._update_pet_position()
    
    def _on_click(self, event):
        """Handle mouse click to move pet"""
        # Don't move if in egg stage
        if getattr(self, 'pet_stage', 4) == 1:  # Stage 1 is egg
            self._return_to_rest_position()
            return
            
        # Update target position
        self.target_x = event.x
        self.target_y = event.y
        self.is_moving = True
        
        # Update pet direction based on click position
        dx = self.target_x - self.pet_x
        if abs(dx) > 1:  # Only update direction if moving significantly horizontally
            self._flip_pet_image(dx < 0)
    
    def _move_pet(self, dx, dy):
        """Move the pet by the specified delta"""
        # Don't move if in egg stage
        if getattr(self, 'pet_stage', 4) == 1:  # Stage 1 is egg
            return
            
        self.pet_x = max(0, min(self.width, self.pet_x + dx))
        self.pet_y = max(0, min(self.height, self.pet_y + dy))
        self._update_pet_position()
    
    def _flip_pet_image(self, flip):
        """Flip the pet image horizontally"""
        if flip == self._is_flipped:
            return  # Already in the correct state
            
        try:
            # Get the pet's current state
            pet_type = getattr(self, 'pet_type', 'Raccoon').lower()
            emotion = getattr(self, 'pet_emotion', 'happy').lower()
            
            # Map stage number to stage name
            stage_map = {
                1: 'egg',
                2: 'baby',
                3: 'child',
                4: 'grown',
                5: 'grown'  # Fallback to grown for any higher stages
            }
            stage_name = stage_map.get(getattr(self, 'pet_stage', 4), 'grown')
            
            # Get the default facing direction for this pet, stage, and emotion
            default_direction = 'right'  # Default fallback
            try:
                default_direction = self.PET_FACING_DIRECTIONS\
                    .get(pet_type, {})\
                    .get(stage_name, {})\
                    .get(emotion, 'right')
            except (AttributeError, KeyError):
                logger.warning(f"Could not find facing direction for {pet_type}/{stage_name}/{emotion}, using 'right'")
            
            # Determine if we need to flip the image based on desired direction and default facing
            should_flip = (default_direction == 'right' and flip) or (default_direction == 'left' and not flip)
            logger.debug(f"Pet: {pet_type}, Stage: {stage_name}, Emotion: {emotion}, "
                       f"Default: {default_direction}, Should flip: {should_flip}")
            
            # Create a cache key for this pet/emotion/direction
            cache_key = f"{pet_type}_{stage_name}_{emotion}_{'left' if flip else 'right'}"
            
            # If this is the same image we're already showing, no need to change
            if cache_key == self._current_image_key:
                return
                
            self._current_image_key = cache_key
            
            # Check if we have a cached version
            if not hasattr(self, '_image_cache'):
                self._image_cache = {}
                
            if cache_key in self._image_cache:
                # Use cached image if available
                self.pet_image = self._image_cache[cache_key]
            else:
                # Otherwise, create a new flipped version
                if not hasattr(self, 'original_image'):
                    # If we don't have an original, use the current image
                    self.original_image = self.pet_image.copy()
                
                # Create a fresh copy of the original image
                img = self.original_image.copy()
                
                # Flip if needed based on the pet's default facing direction
                if should_flip:
                    img = img.transpose(Image.FLIP_LEFT_RIGHT)
                
                # Make sure to remove any existing direction indicators by creating a clean copy
                if img.mode == 'RGBA':
                    # Create a clean copy without any drawings
                    clean_img = Image.new('RGBA', img.size, (0, 0, 0, 0))
                    clean_img.paste(img, (0, 0), img)
                    img = clean_img
                
                # Cache the result
                self._image_cache[cache_key] = img
                self.pet_image = img
            
            # Update the display
            self.pet_photo = ImageTk.PhotoImage(self.pet_image)
            self.canvas.itemconfig(self.pet_id, image=self.pet_photo)
            self._is_flipped = flip
            
            # Force a redraw
            self.canvas.update_idletasks()
            
        except Exception as e:
            logger.warning(f"Could not flip image: {e}")
            import traceback
            traceback.print_exc()
    
    def _update_pet_position(self):
        """Update the pet's position on the canvas"""
        try:
            if not self._canvas_exists() or self.pet_id is None:
                return
                
            # Add a subtle bounce effect when moving
            bounce = 0
            if getattr(self, 'is_moving', False):
                # Simulate a gentle bounce using a sine wave
                bounce = 3 * abs((time.time() * 6) % 2 - 1)  # Bounces between 0 and 3
            
            # Update position with bounce
            try:
                self.canvas.coords(self.pet_id, self.pet_x, self.pet_y - bounce)
                # Ensure pet stays above background
                self.canvas.tag_raise(self.pet_id, 'bg')
            except tk.TclError as e:
                # Canvas might have been destroyed
                if 'invalid command name' not in str(e):
                    logger.warning(f"Error updating pet position: {e}")
        except Exception as e:
            logger.error(f"Error in _update_pet_position: {e}")
            import traceback
            traceback.print_exc()
    
    def _start_animation(self):
        """Start the animation loop"""
        self._animate()
    
    def _animate(self):
        """Update animation frame"""
        try:
            # Check if canvas still exists
            if not self._canvas_exists():
                self.animation_id = None
                return
                
            # Handle movement towards target
            if self.is_moving:
                dx = self.target_x - self.pet_x
                dy = self.target_y - self.pet_y
                distance = (dx**2 + dy**2) ** 0.5
                
                if distance > 2:  # If not at target
                    # Calculate movement with easing and slower speed
                    move_speed = 0.12  # Slightly slower for more natural movement
                    self.pet_x += dx * move_speed
                    self.pet_y += dy * move_speed
                    
                    # Keep pet within bounds with padding
                    padding = self.pet_size // 2
                    self.pet_x = max(padding, min(self.width - padding, self.pet_x))
                    self.pet_y = max(padding, min(self.height - padding, self.pet_y))
                    
                    # Update pet position with bounce effect
                    self._update_pet_position()
                else:
                    self.is_moving = False
            
            # Schedule next frame
            if self.canvas.winfo_exists():
                self.animation_timer = self.canvas.after(self.update_interval, self._animate)
                
        except Exception as e:
            logger.error(f"Error in animation loop: {e}")
            # Try to restart animation after a delay
            if self.canvas.winfo_exists():
                self.animation_timer = self.canvas.after(1000, self._start_animation)
    
    def stop_animation(self):
        """Stop the animation loop"""
        if self.animation_timer:
            self.canvas.after_cancel(self.animation_timer)
            self.animation_timer = None
    
    def cleanup(self):
        """
        Clean up resources safely, handling cases where canvas might be destroyed.
        """
        try:
            # Stop any running animations
            self.stop_animation()
            
            # Unsubscribe from state changes
            if hasattr(self, '_handle_state_change'):
                try:
                    state_manager.unsubscribe(self._handle_state_change)
                except Exception as e:
                    print(f"Error unsubscribing from state manager: {e}")
            
            # Safely delete canvas items if canvas still exists
            if hasattr(self, 'canvas') and self.canvas and self.canvas.winfo_exists():
                try:
                    if hasattr(self, 'pet_id') and self.pet_id:
                        self.canvas.delete(self.pet_id)
                    if hasattr(self, 'bg_photo'):
                        self.canvas.delete("bg")
                except tk.TclError as e:
                    if "can't invoke" not in str(e):
                        print(f"Error cleaning up canvas items: {e}")
            
            # Clean up image references
            for attr in ['pet_image', 'background_image', 'pet_photo', 'bg_photo']:
                if hasattr(self, attr):
                    try:
                        delattr(self, attr)
                    except Exception as e:
                        print(f"Error cleaning up {attr}: {e}")
            
            # Clear any remaining references
            self.pet_id = None
            
        except Exception as e:
            print(f"Error during playground cleanup: {e}")
            import traceback
            traceback.print_exc()
