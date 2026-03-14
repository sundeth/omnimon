"""
Protocol system for handling different Digimon communication protocols.

This module provides a data-driven system for defining and handling
various Digimon device protocols (DM20, DMX, PEN20, etc.).
"""

from .protocol_handler import ProtocolHandler, ProtocolDefinition

__all__ = ['ProtocolHandler', 'ProtocolDefinition']
