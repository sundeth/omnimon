"""
OmninetService - Python client for Omninet API
Handles device linking, auto-login, and API communication with Omninet server.
"""
import json
import os
import threading
import requests
from urllib.parse import urljoin
from typing import Optional, Tuple, Dict, Any

from core import runtime_globals, constants


class OmninetService:
    """API client for Omninet server communication."""
    
    # Singleton instance
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern to ensure only one instance exists."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the Omninet service."""
        if self._initialized:
            return
        
        self._initialized = True
        self._device_key: Optional[str] = None
        self._device_id: Optional[str] = None
        self._player_id: Optional[str] = None  # Cached player UUID from server
        self._user_info: Optional[Dict[str, Any]] = None
        self._timeout = 5  # seconds
        
        # Path for storing device credentials
        self._credentials_path = self._get_credentials_path()
        
        # Load saved credentials on init
        self._load_credentials()
    
    def _get_credentials_path(self) -> str:
        """Get the path to the credentials file."""
        # Try to get save directory from game globals
        save_dir = getattr(runtime_globals, 'save_directory', None)
        if save_dir:
            return os.path.join(save_dir, 'omninet_device.json')
        
        # Fallback to save/ directory
        return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                          'save', 'omninet_device.json')
    
    def _get_base_url(self) -> str:
        """Get the Omninet server base URL."""
        # Try local URL first (for development)
        local_url = getattr(constants, 'OMNINET_LOCAL_URL', 'http://localhost:8000')
        if local_url:
            try:
                response = requests.get(urljoin(local_url, '/health'), timeout=2)
                if response.status_code == 200:
                    return local_url
            except Exception:
                pass
        
        # Try main URL
        main_url = getattr(constants, 'OMNINET_MAIN_URL', None)
        if main_url:
            return main_url
        
        return local_url
    
    def _load_credentials(self) -> None:
        """Load saved device credentials from file."""
        try:
            if os.path.exists(self._credentials_path):
                with open(self._credentials_path, 'r') as f:
                    data = json.load(f)
                    self._device_key = data.get('device_key')
                    self._device_id = data.get('device_id')
                    self._player_id = data.get('player_id')
                    runtime_globals.game_console.log("[OmninetService] Loaded saved credentials")
        except Exception as e:
            runtime_globals.game_console.log(f"[OmninetService] Failed to load credentials: {e}")
    
    def _save_credentials(self) -> None:
        """Save device credentials to file."""
        try:
            os.makedirs(os.path.dirname(self._credentials_path), exist_ok=True)
            with open(self._credentials_path, 'w') as f:
                json.dump({
                    'device_key': self._device_key,
                    'device_id': self._device_id,
                    'player_id': self._player_id,
                }, f)
            runtime_globals.game_console.log("[OmninetService] Saved credentials")
        except Exception as e:
            runtime_globals.game_console.log(f"[OmninetService] Failed to save credentials: {e}")
    
    def _clear_credentials(self) -> None:
        """Clear saved device credentials."""
        self._device_key = None
        self._device_id = None
        self._player_id = None
        self._user_info = None
        try:
            if os.path.exists(self._credentials_path):
                os.remove(self._credentials_path)
                runtime_globals.game_console.log("[OmninetService] Cleared credentials")
        except Exception as e:
            runtime_globals.game_console.log(f"[OmninetService] Failed to clear credentials: {e}")
    
    def check_availability(self) -> bool:
        """Check if Omninet server is available."""
        try:
            base_url = self._get_base_url()
            response = requests.get(urljoin(base_url, '/health'), timeout=2)
            return response.status_code == 200
        except Exception:
            return False
    
    def validate_pairing_code(self, code: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Validate a pairing code and link this device.
        
        Args:
            code: The 4-character pairing code from Module Editor
            
        Returns:
            Tuple of (success, message, user_info)
        """
        try:
            base_url = self._get_base_url()
            url = urljoin(base_url, '/api/v1/auth/validate-pairing-code')
            
            runtime_globals.game_console.log(f"[OmninetService] Validating pairing code: {code}")
            
            response = requests.post(
                url,
                json={'code': code.upper()},
                timeout=self._timeout
            )
            
            runtime_globals.game_console.log(f"[OmninetService] Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                self._device_key = data.get('secret_key')
                self._device_id = data.get('device_id')
                
                # Save credentials
                self._save_credentials()
                
                # Validate the device to get user info
                success, msg, user_info = self.validate_device()
                if success and user_info:
                    return True, data.get('message', 'Device linked successfully!'), user_info
                
                return True, data.get('message', 'Device linked successfully!'), None
            else:
                error_data = response.json()
                error_msg = error_data.get('detail', 'Invalid or expired code')
                runtime_globals.game_console.log(f"[OmninetService] Pairing failed: {error_msg}")
                return False, error_msg, None
                
        except requests.exceptions.Timeout:
            runtime_globals.game_console.log("[OmninetService] Request timeout")
            return False, "Connection timeout", None
        except requests.exceptions.ConnectionError:
            runtime_globals.game_console.log("[OmninetService] Connection error")
            return False, "Cannot connect to server", None
        except Exception as e:
            runtime_globals.game_console.log(f"[OmninetService] Error: {e}")
            return False, str(e), None
    
    def validate_device(self) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Validate saved device credentials and get user info.
        Used for auto-login on startup.
        
        Returns:
            Tuple of (success, message, user_info)
        """
        if not self._device_key:
            return False, "No device credentials", None
        
        try:
            base_url = self._get_base_url()
            url = urljoin(base_url, '/api/v1/auth/validate-device')
            
            runtime_globals.game_console.log("[OmninetService] Validating device credentials")
            
            headers = {
                'X-Device-Key': self._device_key,
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                url,
                headers=headers,
                json={},
                timeout=self._timeout
            )
            
            runtime_globals.game_console.log(f"[OmninetService] Response status: {response.status_code}")
            
            if response.status_code == 200:
                self._user_info = response.json()
                # Cache player_id from server response
                server_player_id = self._user_info.get('id')
                if server_player_id:
                    self._player_id = str(server_player_id)
                    self._save_credentials()
                runtime_globals.game_console.log(f"[OmninetService] Logged in as: {self._user_info.get('nickname')}")
                return True, "Device validated", self._user_info
            else:
                # Invalid credentials, clear them
                error_data = response.json()
                error_msg = error_data.get('detail', 'Device validation failed')
                runtime_globals.game_console.log(f"[OmninetService] Validation failed: {error_msg}")
                self._clear_credentials()
                return False, error_msg, None
                
        except requests.exceptions.Timeout:
            return False, "Connection timeout", None
        except requests.exceptions.ConnectionError:
            return False, "Cannot connect to server", None
        except Exception as e:
            runtime_globals.game_console.log(f"[OmninetService] Error: {e}")
            return False, str(e), None
    
    def logout(self) -> bool:
        """
        Logout and clear device credentials.
        
        Returns:
            True if logout was successful
        """
        # Try to invalidate on server (if we have credentials and server is available)
        if self._device_key:
            try:
                base_url = self._get_base_url()
                url = urljoin(base_url, '/api/v1/auth/logout')
                
                headers = {
                    'X-Device-Key': self._device_key,
                    'Content-Type': 'application/json'
                }
                
                response = requests.post(
                    url,
                    headers=headers,
                    json={'secret_key': self._device_key},
                    timeout=self._timeout
                )
                
                runtime_globals.game_console.log(f"[OmninetService] Logout response: {response.status_code}")
            except Exception as e:
                runtime_globals.game_console.log(f"[OmninetService] Logout error: {e}")
        
        # Clear local credentials regardless of server response
        self._clear_credentials()
        return True
    
    # =========================================================================
    # Account Auth Methods (register, login, verify, resend)
    # =========================================================================

    def register(self, nickname: str, email: str, password: str) -> Tuple[bool, str]:
        """
        Register a new user account.
        On success the server sends a verification code to the email.

        Args:
            nickname: Desired display name (3-100 chars, alphanumeric/_ /-).
            email:    Valid email address.
            password: At least 6 characters.

        Returns:
            (success, message) — message is the server detail string.
        """
        try:
            base_url = self._get_base_url()
            url = urljoin(base_url, '/api/v1/auth/register')
            response = requests.post(
                url,
                json={'nickname': nickname, 'email': email, 'password': password},
                timeout=self._timeout,
            )
            data = response.json() if response.content else {}
            if response.status_code == 200:
                msg = data.get('message', 'Verification code sent')
                runtime_globals.game_console.log(f"[OmninetService] Register OK: {msg}")
                return True, msg
            detail = data.get('detail', 'Registration failed')
            runtime_globals.game_console.log(f"[OmninetService] Register fail: {detail}")
            return False, detail
        except requests.exceptions.Timeout:
            return False, "Connection timeout"
        except requests.exceptions.ConnectionError:
            return False, "Cannot connect to server"
        except Exception as e:
            runtime_globals.game_console.log(f"[OmninetService] Register error: {e}")
            return False, str(e)

    def verify_registration(self, email: str, code: str) -> Tuple[bool, str]:
        """
        Verify registration with the 6-char code sent to email.
        On success, a device key is created and stored automatically.

        Returns:
            (success, message)
        """
        try:
            base_url = self._get_base_url()
            url = urljoin(base_url, '/api/v1/auth/verify-registration')
            response = requests.post(
                url,
                json={'email': email, 'code': code},
                timeout=self._timeout,
            )
            data = response.json() if response.content else {}
            if response.status_code == 200:
                self._device_key = data.get('secret_key')
                self._device_id = data.get('device_id')
                self._save_credentials()
                # Validate device to get full user info + player_id
                self.validate_device()
                msg = data.get('message', 'Account verified')
                runtime_globals.game_console.log(f"[OmninetService] VerifyReg OK: {msg}")
                return True, msg
            detail = data.get('detail', 'Verification failed')
            runtime_globals.game_console.log(f"[OmninetService] VerifyReg fail: {detail}")
            return False, detail
        except requests.exceptions.Timeout:
            return False, "Connection timeout"
        except requests.exceptions.ConnectionError:
            return False, "Cannot connect to server"
        except Exception as e:
            runtime_globals.game_console.log(f"[OmninetService] VerifyReg error: {e}")
            return False, str(e)

    def login_request(self, email: str, password: str) -> Tuple[bool, str]:
        """
        Login with email and password.
        On success the server sends a verification code to the email.

        Returns:
            (success, message)
        """
        try:
            base_url = self._get_base_url()
            url = urljoin(base_url, '/api/v1/auth/login')
            response = requests.post(
                url,
                json={'email': email, 'password': password},
                timeout=self._timeout,
            )
            data = response.json() if response.content else {}
            if response.status_code == 200:
                msg = data.get('message', 'Verification code sent')
                runtime_globals.game_console.log(f"[OmninetService] Login OK: {msg}")
                return True, msg
            detail = data.get('detail', 'Login failed')
            runtime_globals.game_console.log(f"[OmninetService] Login fail: {detail}")
            return False, detail
        except requests.exceptions.Timeout:
            return False, "Connection timeout"
        except requests.exceptions.ConnectionError:
            return False, "Cannot connect to server"
        except Exception as e:
            runtime_globals.game_console.log(f"[OmninetService] Login error: {e}")
            return False, str(e)

    def verify_login(self, email: str, code: str,
                     clear_devices: bool = False) -> Tuple[bool, str]:
        """
        Verify login with the 6-char code.
        On success, a device key is created and stored automatically.

        Args:
            email:         The email used during login_request().
            code:          6-character verification code.
            clear_devices: If True, revoke all other device keys first.

        Returns:
            (success, message)
        """
        try:
            base_url = self._get_base_url()
            url = urljoin(base_url, '/api/v1/auth/verify-login')
            response = requests.post(
                url,
                json={'email': email, 'code': code,
                      'clear_devices': clear_devices},
                timeout=self._timeout,
            )
            data = response.json() if response.content else {}
            if response.status_code == 200:
                self._device_key = data.get('secret_key')
                self._device_id = data.get('device_id')
                self._save_credentials()
                # Validate device to get full user info + player_id
                self.validate_device()
                msg = data.get('message', 'Login verified')
                runtime_globals.game_console.log(f"[OmninetService] VerifyLogin OK: {msg}")
                return True, msg
            detail = data.get('detail', 'Verification failed')
            runtime_globals.game_console.log(f"[OmninetService] VerifyLogin fail: {detail}")
            return False, detail
        except requests.exceptions.Timeout:
            return False, "Connection timeout"
        except requests.exceptions.ConnectionError:
            return False, "Cannot connect to server"
        except Exception as e:
            runtime_globals.game_console.log(f"[OmninetService] VerifyLogin error: {e}")
            return False, str(e)

    def resend_code(self, email: str) -> Tuple[bool, str]:
        """
        Resend a verification code to the given email.

        Returns:
            (success, message)
        """
        try:
            base_url = self._get_base_url()
            url = urljoin(base_url, f'/api/v1/auth/resend-code?email={email}')
            response = requests.post(url, timeout=self._timeout)
            data = response.json() if response.content else {}
            if response.status_code == 200:
                msg = data.get('message', 'Code resent')
                runtime_globals.game_console.log(f"[OmninetService] Resend OK: {msg}")
                return True, msg
            detail = data.get('detail', 'Failed to resend code')
            runtime_globals.game_console.log(f"[OmninetService] Resend fail: {detail}")
            return False, detail
        except requests.exceptions.Timeout:
            return False, "Connection timeout"
        except requests.exceptions.ConnectionError:
            return False, "Cannot connect to server"
        except Exception as e:
            runtime_globals.game_console.log(f"[OmninetService] Resend error: {e}")
            return False, str(e)

    def is_logged_in(self) -> bool:
        """Check if device is linked and has valid credentials."""
        return self._device_key is not None and self._user_info is not None
    
    def get_username(self) -> Optional[str]:
        """Get the logged in user's nickname."""
        if self._user_info:
            return self._user_info.get('nickname')
        return None
    
    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """Get the full user info."""
        return self._user_info
    
    def get_device_key(self) -> Optional[str]:
        """Get the device key for authenticated requests."""
        return self._device_key
    
    def has_saved_credentials(self) -> bool:
        """Check if there are saved credentials (for auto-login attempt)."""
        return self._device_key is not None

    def get_player_id(self) -> Optional[str]:
        """Get the cached player ID (UUID) from credentials.

        The player ID is extracted from the server's UserResponse on
        validate_device() or validate_pairing_code() and cached locally
        in omninet_device.json.  It is used as the save-folder name
        for Progress Mode.

        Returns:
            Player UUID string if available, None otherwise.
        """
        return self._player_id
    
    # =========================================================================
    # Shop API Methods
    # =========================================================================
    
    def _make_request(self, method: str, endpoint: str, json_data: dict = None, 
                      require_auth: bool = True) -> Tuple[bool, Any]:
        """
        Make an API request with optional authentication.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            json_data: Optional JSON body data
            require_auth: Whether to include device key header
            
        Returns:
            Tuple of (success, data/error_message)
        """
        try:
            base_url = self._get_base_url()
            url = urljoin(base_url, endpoint)
            
            headers = {'Content-Type': 'application/json'}
            if require_auth and self._device_key:
                headers['X-Device-Key'] = self._device_key
            
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, timeout=self._timeout)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=json_data or {}, timeout=self._timeout)
            else:
                return False, f"Unsupported method: {method}"
            
            if response.status_code == 200:
                return True, response.json()
            else:
                # Handle error responses
                try:
                    error_data = response.json() if response.content else {}
                    # For 422 validation errors, extract field errors
                    if response.status_code == 422 and 'detail' in error_data:
                        detail = error_data['detail']
                        if isinstance(detail, list) and len(detail) > 0:
                            # Extract first validation error message
                            first_error = detail[0]
                            if isinstance(first_error, dict):
                                msg = first_error.get('msg', str(first_error))
                                field = '.'.join(str(x) for x in first_error.get('loc', []))
                                return False, f"{field}: {msg}" if field else msg
                        elif isinstance(detail, str):
                            return False, detail
                    # For other errors, get detail or fallback
                    return False, error_data.get('detail', f'Request failed: {response.status_code}')
                except:
                    return False, f'Request failed: {response.status_code}'
                
        except requests.exceptions.Timeout:
            return False, "Connection timeout"
        except requests.exceptions.ConnectionError:
            return False, "Cannot connect to server"
        except Exception as e:
            runtime_globals.game_console.log(f"[OmninetService] Request error: {e}")
            return False, str(e)
    
    def get_shop_modules(self, category: str = None) -> Tuple[bool, list]:
        """Get list of modules available in shop."""
        endpoint = '/api/v1/shop/modules'
        if category:
            endpoint += f'?category={category}'
        success, data = self._make_request('GET', endpoint, require_auth=False)
        if success and isinstance(data, dict):
            return True, data.get('modules', [])
        return success, data if isinstance(data, list) else []
    
    def get_shop_gameplay(self) -> Tuple[bool, list]:
        """Get list of gameplay items available in shop."""
        success, data = self._make_request('GET', '/api/v1/shop/gameplay', require_auth=False)
        if success and isinstance(data, dict):
            return True, data.get('gameplay', [])
        return success, data if isinstance(data, list) else []
    
    def get_shop_items(self) -> Tuple[bool, list]:
        """Get list of items available in shop."""
        success, data = self._make_request('GET', '/api/v1/shop/items', require_auth=False)
        if success and isinstance(data, dict):
            return True, data.get('items', [])
        return success, data if isinstance(data, list) else []
    
    def get_shop_cosmetics(self) -> Tuple[bool, list]:
        """Get list of cosmetics available in shop."""
        success, data = self._make_request('GET', '/api/v1/shop/cosmetics', require_auth=False)
        if success and isinstance(data, dict):
            return True, data.get('cosmetics', [])
        return success, data if isinstance(data, list) else []
    
    def get_shop_specials(self) -> Tuple[bool, list]:
        """Get list of special items available in shop."""
        success, data = self._make_request('GET', '/api/v1/shop/specials', require_auth=False)
        if success and isinstance(data, dict):
            return True, data.get('specials', [])
        return success, data if isinstance(data, list) else []
    
    def purchase_item(self, item_type: str, item_id: str) -> Tuple[bool, str]:
        """
        Purchase an item from the shop.
        
        Args:
            item_type: Type of item (module, cosmetic, gameplay, item, special)
            item_id: The item's GUID
            
        Returns:
            Tuple of (success, message)
        """
        if not self._device_key:
            return False, "Not logged in"
        
        success, data = self._make_request('POST', '/api/v1/shop/purchase', {
            'purchase_type': item_type,  # Server expects 'purchase_type', not 'item_type'
            'item_id': item_id
        })
        
        if success and isinstance(data, dict):
            return True, data.get('message', 'Purchase successful')
        return False, data if isinstance(data, str) else 'Purchase failed'
    
    def download_module(self, module_id: str) -> Tuple[bool, Any]:
        """Download a purchased module."""
        if not self._device_key:
            return False, "Not logged in"
        return self._make_request('GET', f'/api/v1/shop/download/module/{module_id}')

    def download_module_free(self, module_id: str) -> Tuple[bool, Any]:
        """Download a module for free (Free Mode). Uses public module download endpoint."""
        return self._make_request('GET', f'/api/v1/modules/{module_id}/download', require_auth=False)

    def download_gameplay(self, gameplay_id: str) -> Tuple[bool, Any]:
        """Download a purchased gameplay item."""
        if not self._device_key:
            return False, "Not logged in"
        return self._make_request('GET', f'/api/v1/shop/download/gameplay/{gameplay_id}')
    
    def download_cosmetic(self, cosmetic_id: str) -> Tuple[bool, Any]:
        """Download a purchased cosmetic."""
        if not self._device_key:
            return False, "Not logged in"
        return self._make_request('GET', f'/api/v1/shop/download/cosmetic/{cosmetic_id}')
    
    def download_item(self, item_id: str) -> Tuple[bool, Any]:
        """Download a purchased item."""
        if not self._device_key:
            return False, "Not logged in"
        return self._make_request('GET', f'/api/v1/shop/download/item/{item_id}')


# Global singleton instance
omninet_service = OmninetService()
