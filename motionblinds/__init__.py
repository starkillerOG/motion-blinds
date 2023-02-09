"""
Python library for interfacing with Motion Blinds.

:copyright: (c) 2020 starkillerOG.
:license: MIT, see LICENSE for more details.
"""

# Set default logging handler to avoid "No handler found" warnings.
import logging

# Import motion_blinds module
from .motion_blinds import MotionGateway
from .motion_blinds import MotionMulticast
from .motion_blinds import MotionDiscovery
from .motion_blinds import BlindType
from .motion_blinds import WirelessMode
from .motion_blinds import ParseException

# Import async_motion_blinds module
from .async_motion_blinds import AsyncMotionMulticast

# Import constants
from .motion_blinds import DEVICE_TYPES_GATEWAY
from .motion_blinds import DEVICE_TYPES_WIFI

logging.getLogger(__name__)

__title__ = "motion-blinds"
__version__ = "0.6.16"
