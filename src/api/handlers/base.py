"""Base handler for API requests.

This module provides the base class for all API request handlers.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from src.api.session import Session
from src.utils.logging import get_logger

logger = get_logger(__name__)


class BaseHandler(ABC):
    """Base class for API handlers."""
    
    def __init__(self, gateway=None):
        """Initialize handler.
        
        Args:
            gateway: Gateway instance for I3 network communication
        """
        self.gateway = gateway
    
    @abstractmethod
    async def handle(self, session: Session, params: Dict[str, Any]) -> Any:
        """Handle API request.
        
        Args:
            session: Client session
            params: Request parameters
            
        Returns:
            Response data
            
        Raises:
            ValueError: If parameters are invalid
            PermissionError: If session lacks permission
        """
        pass
    
    @abstractmethod
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate request parameters.
        
        Args:
            params: Parameters to validate
            
        Returns:
            True if valid, False otherwise
        """
        pass
    
    def check_permission(self, session: Session, permission: str) -> bool:
        """Check if session has required permission.
        
        Args:
            session: Client session
            permission: Permission to check
            
        Returns:
            True if has permission, False otherwise
        """
        return session.has_permission(permission)
    
    def get_required_params(self) -> list[str]:
        """Get list of required parameters.
        
        Returns:
            List of required parameter names
        """
        return []
    
    def get_optional_params(self) -> list[str]:
        """Get list of optional parameters.
        
        Returns:
            List of optional parameter names
        """
        return []
    
    def validate_base_params(self, params: Dict[str, Any]) -> bool:
        """Validate that required parameters are present.
        
        Args:
            params: Parameters to validate
            
        Returns:
            True if all required params present, False otherwise
        """
        if params is None:
            params = {}
        
        for param in self.get_required_params():
            if param not in params:
                logger.warning(f"Missing required parameter: {param}")
                return False
        
        return True
    
    async def log_request(
        self,
        session: Session,
        method: str,
        params: Dict[str, Any],
        success: bool,
        error: Optional[str] = None
    ):
        """Log API request for auditing.
        
        Args:
            session: Client session
            method: Method name
            params: Request parameters
            success: Whether request succeeded
            error: Error message if failed
        """
        log_data = {
            "session_id": session.session_id,
            "mud_name": session.mud_name,
            "method": method,
            "success": success
        }
        
        if error:
            log_data["error"] = error
        
        if success:
            logger.info("API request completed", extra=log_data)
        else:
            logger.warning("API request failed", extra=log_data)