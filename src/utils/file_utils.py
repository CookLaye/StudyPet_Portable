"""
File utility functions with atomic operations and error handling.
"""
import os
import json
import shutil
import tempfile
import time
from typing import Any, TypeVar
T = TypeVar('T')

def atomic_write(file_path: str, data: Any, **kwargs) -> bool:
    """
    Atomically write data to a file.
    
    Args:
        file_path: Path to the file to write
        data: Data to write (will be JSON serialized)
        **kwargs: Additional arguments to pass to json.dump()
        
    Returns:
        bool: True if successful, False otherwise
    """
    if 'default' not in kwargs:
        kwargs['default'] = str  # Handle non-serializable types
        
    temp_file = None
    try:
        # Create parent directories if they don't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Create a temporary file in the same directory
        with tempfile.NamedTemporaryFile(
            mode='w', 
            dir=os.path.dirname(file_path),
            delete=False,
            suffix='.tmp',
            encoding='utf-8'
        ) as temp_file:
            json.dump(data, temp_file, indent=2, **kwargs)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        
        # On Windows, we need to remove the destination file first
        if os.name == 'nt' and os.path.exists(file_path):
            os.unlink(file_path)
            
        # Atomic rename
        os.rename(temp_file.name, file_path)
        return True
        
    except (IOError, OSError, TypeError, ValueError) as e:
        print(f"Error writing to {file_path}: {e}")
        if temp_file and os.path.exists(temp_file.name):
            try:
                os.unlink(temp_file.name)
            except OSError:
                pass
        return False


def write_runtime_backup(save_file_path: str, data: Any) -> bool:
    backup_path = f"{save_file_path}.runtime"
    return atomic_write(backup_path, data)


def read_runtime_backup(save_file_path: str, default: Any = None) -> Any:
    backup_path = f"{save_file_path}.runtime"
    return atomic_read(backup_path, default=default)


def delete_runtime_backup(save_file_path: str) -> bool:
    backup_path = f"{save_file_path}.runtime"
    if not os.path.exists(backup_path):
        return True
    try:
        os.unlink(backup_path)
        return True
    except OSError:
        return False

def atomic_read(file_path: str, default: Any = None, **kwargs) -> Any:
    """
    Safely read data from a JSON file with error handling.
    
    Args:
        file_path: Path to the file to read
        default: Default value to return if file doesn't exist or is invalid
        **kwargs: Additional arguments to pass to json.load()
        
    Returns:
        The parsed JSON data or default value
    """
    if not os.path.exists(file_path):
        return default
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f, **kwargs)
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error reading {file_path}: {e}")
        return default

def backup_file(file_path: str, max_backups: int = 3) -> bool:
    """
    Create a timestamped backup of a file.
    
    Args:
        file_path: Path to the file to back up
        max_backups: Maximum number of backups to keep
        
    Returns:
        bool: True if backup was successful, False otherwise
    """
    if not os.path.exists(file_path):
        return False
        
    try:
        # Create backup directory if it doesn't exist
        backup_dir = os.path.join(os.path.dirname(file_path), 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        # Create timestamped backup
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        filename = os.path.basename(file_path)
        backup_path = os.path.join(backup_dir, f"{timestamp}_{filename}")
        
        shutil.copy2(file_path, backup_path)
        
        # Clean up old backups
        if max_backups > 0:
            backups = sorted(
                [f for f in os.listdir(backup_dir) if f.endswith(f'_{filename}')],
                reverse=True
            )
            for old_backup in backups[max_backups:]:
                try:
                    os.unlink(os.path.join(backup_dir, old_backup))
                except OSError:
                    pass
                    
        return True
        
    except (IOError, OSError) as e:
        print(f"Error creating backup of {file_path}: {e}")
        return False
