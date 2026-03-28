"""
Battle system for Omnipet.
Contains battle encounters, simulation, DCom communication, and protocol handling.
"""

from .protocol_handler import ProtocolHandler, ProtocolDefinition

__all__ = ['ProtocolHandler', 'ProtocolDefinition']
