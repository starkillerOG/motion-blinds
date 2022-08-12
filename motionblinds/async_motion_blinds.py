"""
This module implements the async interface to Motion Blinds.

:copyright: (c) 2020 starkillerOG.
:license: MIT, see LICENSE for more details.
"""


import logging
import json
import asyncio

from .motion_blinds import MotionCommunication

_LOGGER = logging.getLogger(__name__)


class AsyncMotionMulticast(MotionCommunication):
    """Async Multicast UDP communication class for a MotionGateway."""

    def __init__(self, interface="any", bind_interface=True):
        self._listen_couroutine = None
        self._interface = interface
        self._bind_interface = bind_interface

        self.registered_callbacks = {}

    def _create_udp_listener(self):
        """Create the UDP multicast socket and protocol."""
        udp_socket = self._create_mcast_socket(
            self._interface, self._bind_interface, blocking=False
        )

        loop = asyncio.get_event_loop()

        return loop.create_datagram_endpoint(
            lambda: self.MulticastListenerProtocol(loop, udp_socket, self),
            sock=udp_socket,
        )

    @property
    def interface(self):
        """Return the used interface."""
        return self._interface

    @property
    def bind_interface(self):
        """Return if the interface is bound."""
        return self._bind_interface

    def Register_motion_gateway(self, ip, callback):
        """Register a Motion Gateway to this Multicast listener."""
        if ip in self.registered_callbacks:
            _LOGGER.error(
                "A callback for ip '%s' was already registed, overwriting previous callback",
                ip,
            )
        self.registered_callbacks[ip] = callback

    def Unregister_motion_gateway(self, ip):
        """Unregister a Motion Gateway from this Multicast listener."""
        if ip in self.registered_callbacks:
            self.registered_callbacks.pop(ip)

    async def Start_listen(self):
        """Start listening."""
        if self._listen_couroutine is not None:
            _LOGGER.error(
                "Multicast listener already started, not starting another one."
            )
            return

        listen_task = self._create_udp_listener()
        _, self._listen_couroutine = await listen_task

    def Stop_listen(self):
        """Stop listening."""
        if self._listen_couroutine is None:
            return

        self._listen_couroutine.close()
        self._listen_couroutine = None

    class MulticastListenerProtocol:
        """Handle responding to UPNP/SSDP discovery requests."""

        def __init__(self, loop, udp_socket, parent):
            """Initialize the class."""
            self.transport = None
            self._loop = loop
            self._sock = udp_socket
            self._parent = parent
            self._connected = False

        def connection_made(self, transport):
            """Set the transport."""
            self.transport = transport
            self._connected = True
            _LOGGER.info("MotionMulticast listener started")

        def connection_lost(self, exc):
            """Handle connection lost."""
            if self._connected:
                _LOGGER.error(
                    "Connection unexpectedly lost in MotionMulticast listener: %s", exc
                )

        def datagram_received(self, data, addr):
            """Handle received messages."""
            try:
                (ip_add, _) = addr
                message = json.loads(data)

                if ip_add not in self._parent.registered_callbacks:
                    _LOGGER.info("Unknown motion gateway ip %s", ip_add)
                    return

                callback = self._parent.registered_callbacks[ip_add]
                callback(message)

            except Exception:
                _LOGGER.exception("Cannot process multicast message: '%s'", data)

        def error_received(self, exc):
            """Log UDP errors."""
            _LOGGER.error("UDP error received in MotionMulticast listener: %s", exc)

        def close(self):
            """Stop the server."""
            _LOGGER.debug("MotionMulticast listener shutting down")
            self._connected = False
            if self.transport:
                self.transport.close()
            self._loop.remove_writer(self._sock.fileno())
            self._loop.remove_reader(self._sock.fileno())
            self._sock.close()
            _LOGGER.info("MotionMulticast listener stopped")
