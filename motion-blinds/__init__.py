"""
Python library for interfacing with Motion Blinds.

:copyright: (c) 2020 starkillerOG.
:license: MIT, see LICENSE for more details.
"""

# Set default logging handler to avoid "No handler found" warnings.
import logging

logging.getLogger(__name__).addHandler(logging.NullHandler())

__title__ = "motion-blinds"
__version__ = "0.0.0"

# Import motion_blinds module
from .motion_blinds import MotionGateway
