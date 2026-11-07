# -*- coding: utf-8 -*-
"""Supporto opzionale alla porta seriale (pyserial)."""


try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
