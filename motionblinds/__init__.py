"""
Python library for interfacing with Motion Blinds.

:copyright: (c) 2020 starkillerOG.
:license: MIT, see LICENSE for more details.
"""

# Set default logging handler to avoid "No handler found" warnings.
import logging

logging.getLogger(__name__)

__title__ = "motion-blinds"
__version__ = "0.4.5"

# Import motion_blinds module
from .motion_blinds import MotionGateway
from .motion_blinds import MotionMulticast
from .motion_blinds import MotionDiscovery
from .motion_blinds import BlindType
