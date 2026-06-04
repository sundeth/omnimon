"""
DCom communication module for Omnipet.
Handles serial communication with DCom devices for real hardware battles.
"""

from .dcom_controller import DComController
from .dcom_protocol import DComProtocol, ProtocolType

__all__ = ['DComController', 'DComProtocol', 'ProtocolType']
