import re
from typing import Optional, Tuple
from logger_config import logger


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


def validate_email(email: str) -> Tuple[bool, Optional[str]]:
    """
    Validate email address format.
    
    Args:
        email: Email address to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not email:
        return False, "Email is required"
    
    email = email.strip().lower()
    
    # Basic email regex pattern
    pattern = r'^[a-z0-9]+[\._]?[a-z0-9]+[@]\w+[.]\w{2,3}(\.\w{2})?$'
    if not re.match(pattern, email):
        return False, "Invalid email format"
    
    if len(email) > 255:
        return False, "Email is too long (max 255 characters)"
    
    return True, None


def validate_phone(phone: str) -> Tuple[bool, Optional[str]]:
    """
    Validate phone number format.
    
    Args:
        phone: Phone number to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not phone:
        return True, None  # Phone is optional
    
    phone = phone.strip()
    
    # Remove common formatting characters
    cleaned = re.sub(r'[\s\-\(\)\.]', '', phone)
    
    # Check if it's numeric (allow + at start for country code)
    if not re.match(r'^\+?\d{10,15}$', cleaned):
        return False, "Invalid phone number format (must be 10-15 digits)"
    
    return True, None


def validate_username(username: str) -> Tuple[bool, Optional[str]]:
    """
    Validate username format.
    
    Args:
        username: Username to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not username:
        return False, "Username is required"
    
    username = username.strip()
    
    if len(username) < 3:
        return False, "Username must be at least 3 characters"
    
    if len(username) > 50:
        return False, "Username is too long (max 50 characters)"
    
    # Allow alphanumeric, underscores, and hyphens
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        return False, "Username can only contain letters, numbers, underscores, and hyphens"
    
    return True, None


def validate_password(password: str) -> Tuple[bool, Optional[str]]:
    """
    Validate password strength.
    
    Args:
        password: Password to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not password:
        return False, "Password is required"
    
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    
    if len(password) > 128:
        return False, "Password is too long (max 128 characters)"
    
    # Check for at least one uppercase letter
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    # Check for at least one lowercase letter
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    # Check for at least one digit
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    
    return True, None


def validate_zip_code(zip_code: str) -> Tuple[bool, Optional[str]]:
    """
    Validate ZIP code format (US format).
    
    Args:
        zip_code: ZIP code to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not zip_code:
        return True, None  # ZIP is optional
    
    zip_code = zip_code.strip()
    
    # US ZIP code format: 12345 or 12345-6789
    if not re.match(r'^\d{5}(-\d{4})?$', zip_code):
        return False, "Invalid ZIP code format (use 12345 or 12345-6789)"
    
    return True, None


def validate_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Validate URL format.
    
    Args:
        url: URL to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not url:
        return True, None  # URL is optional
    
    url = url.strip()
    
    # Basic URL pattern
    pattern = r'^https?://[^\s/$.?#].[^\s]*$'
    if not re.match(pattern, url):
        return False, "Invalid URL format (must start with http:// or https://)"
    
    return True, None


def validate_business_name(name: str) -> Tuple[bool, Optional[str]]:
    """
    Validate business name.
    
    Args:
        name: Business name to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not name:
        return False, "Business name is required"
    
    name = name.strip()
    
    if len(name) < 2:
        return False, "Business name must be at least 2 characters"
    
    if len(name) > 200:
        return False, "Business name is too long (max 200 characters)"
    
    return True, None


def sanitize_string(input_string: str, max_length: int = 255) -> str:
    """
    Sanitize a string by trimming and limiting length.
    
    Args:
        input_string: String to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized string
    """
    if not input_string:
        return ""
    
    return input_string.strip()[:max_length]


def validate_numeric(value: str, field_name: str = "value") -> Tuple[bool, Optional[str], Optional[float]]:
    """
    Validate and convert a numeric string.
    
    Args:
        value: String to validate as numeric
        field_name: Name of the field for error messages
        
    Returns:
        Tuple of (is_valid, error_message, numeric_value)
    """
    if not value:
        return False, f"{field_name} is required", None
    
    try:
        numeric_value = float(value)
        if numeric_value < 0:
            return False, f"{field_name} must be positive", None
        return True, None, numeric_value
    except ValueError:
        return False, f"{field_name} must be a valid number", None
