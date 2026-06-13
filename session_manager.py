import streamlit as st
from typing import Optional, Dict, Any
from logger_config import logger


class SessionManager:
    """Manager for Streamlit session state with type safety and validation."""
    
    # Session state keys
    USER_KEY = "user"
    ORIGINAL_USER_KEY = "original_user"
    PAGE_KEY = "page"
    CLIENT_LOGGED_IN_KEY = "client_logged_in"
    
    @staticmethod
    def get_user() -> Optional[Dict[str, Any]]:
        """
        Get current user from session state.
        
        Returns:
            User dictionary or None if not logged in
        """
        return st.session_state.get(SessionManager.USER_KEY)
    
    @staticmethod
    def set_user(user: Dict[str, Any]) -> None:
        """
        Set current user in session state.
        
        Args:
            user: User dictionary containing user information
        """
        st.session_state[SessionManager.USER_KEY] = user
        logger.info(f"User session set: {user.get('username', 'unknown')}")
    
    @staticmethod
    def clear_user() -> None:
        """Clear user from session state (logout)."""
        user = SessionManager.get_user()
        if user:
            logger.info(f"User session cleared: {user.get('username', 'unknown')}")
        
        st.session_state[SessionManager.USER_KEY] = None
        st.session_state[SessionManager.ORIGINAL_USER_KEY] = None
    
    @staticmethod
    def get_original_user() -> Optional[Dict[str, Any]]:
        """
        Get original user (for impersonation feature).
        
        Returns:
            Original user dictionary or None if not impersonating
        """
        return st.session_state.get(SessionManager.ORIGINAL_USER_KEY)
    
    @staticmethod
    def set_original_user(user: Dict[str, Any]) -> None:
        """
        Set original user (for impersonation feature).
        
        Args:
            user: Original user dictionary
        """
        st.session_state[SessionManager.ORIGINAL_USER_KEY] = user
        logger.info(f"Original user set for impersonation: {user.get('username', 'unknown')}")
    
    @staticmethod
    def clear_original_user() -> None:
        """Clear original user (end impersonation)."""
        st.session_state[SessionManager.ORIGINAL_USER_KEY] = None
        logger.info("Original user cleared (impersonation ended)")
    
    @staticmethod
    def get_effective_user() -> Optional[Dict[str, Any]]:
        """
        Get effective user (original user if impersonating, otherwise current user).
        
        Returns:
            Effective user dictionary or None
        """
        original = SessionManager.get_original_user()
        if original:
            return original
        return SessionManager.get_user()
    
    @staticmethod
    def is_impersonating() -> bool:
        """
        Check if currently impersonating another user.
        
        Returns:
            True if impersonating, False otherwise
        """
        return SessionManager.get_original_user() is not None
    
    @staticmethod
    def get_page() -> str:
        """
        Get current page from session state.
        
        Returns:
            Current page name
        """
        return st.session_state.get(SessionManager.PAGE_KEY, "login")
    
    @staticmethod
    def set_page(page: str) -> None:
        """
        Set current page in session state.
        
        Args:
            page: Page name
        """
        st.session_state[SessionManager.PAGE_KEY] = page
        logger.debug(f"Page changed to: {page}")
    
    @staticmethod
    def is_authenticated() -> bool:
        """
        Check if user is authenticated.
        
        Returns:
            True if authenticated, False otherwise
        """
        return SessionManager.get_user() is not None
    
    @staticmethod
    def is_client_logged_in() -> bool:
        """
        Check if client is logged in.
        
        Returns:
            True if client logged in, False otherwise
        """
        return st.session_state.get(SessionManager.CLIENT_LOGGED_IN_KEY, False)
    
    @staticmethod
    def set_client_logged_in(logged_in: bool) -> None:
        """
        Set client login status.
        
        Args:
            logged_in: Client login status
        """
        st.session_state[SessionManager.CLIENT_LOGGED_IN_KEY] = logged_in
        logger.info(f"Client login status set to: {logged_in}")
    
    @staticmethod
    def get_user_id() -> Optional[int]:
        """
        Get current user ID.
        
        Returns:
            User ID or None if not logged in
        """
        user = SessionManager.get_user()
        return user.get('user_id') if user else None
    
    @staticmethod
    def get_user_role() -> Optional[str]:
        """
        Get current user role.
        
        Returns:
            User role or None if not logged in
        """
        user = SessionManager.get_user()
        return user.get('role') if user else None
    
    @staticmethod
    def get_company_id() -> Optional[int]:
        """
        Get current user's company ID.
        
        Returns:
            Company ID or None if not logged in
        """
        user = SessionManager.get_user()
        return user.get('company_id') if user else None
    
    @staticmethod
    def require_auth() -> bool:
        """
        Check if authentication is required and redirect to login if not authenticated.
        
        Returns:
            True if authenticated, False otherwise (and redirects to login)
        """
        if not SessionManager.is_authenticated():
            logger.warning("Authentication required but user not logged in")
            st.warning("🔒 Please log in")
            SessionManager.set_page("login")
            st.rerun()
            return False
        return True
    
    @staticmethod
    def require_role(allowed_roles: list) -> bool:
        """
        Check if user has required role.
        
        Args:
            allowed_roles: List of allowed role strings
            
        Returns:
            True if user has allowed role, False otherwise
        """
        if not SessionManager.is_authenticated():
            return False
        
        user_role = SessionManager.get_user_role()
        effective_role = SessionManager.get_effective_user().get('role') if SessionManager.is_impersonating() else user_role
        
        if effective_role not in allowed_roles:
            logger.warning(f"Access denied. User role: {effective_role}, Required: {allowed_roles}")
            st.error(f"Access denied. Required role: {allowed_roles}")
            return False
        
        return True
    
    @staticmethod
    def initialize_session() -> None:
        """Initialize session state with default values."""
        if SessionManager.PAGE_KEY not in st.session_state:
            SessionManager.set_page("login")
        
        if SessionManager.USER_KEY not in st.session_state:
            st.session_state[SessionManager.USER_KEY] = None
        
        if SessionManager.ORIGINAL_USER_KEY not in st.session_state:
            st.session_state[SessionManager.ORIGINAL_USER_KEY] = None
        
        if SessionManager.CLIENT_LOGGED_IN_KEY not in st.session_state:
            SessionManager.set_client_logged_in(False)
        
        logger.debug("Session state initialized")


# Create a singleton instance
session = SessionManager()
