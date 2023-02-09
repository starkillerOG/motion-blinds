"""
This module implements the interface to Motion Blinds.

:copyright: (c) 2020 starkillerOG.
:license: MIT, see LICENSE for more details.
"""


import logging
import socket
import json
import re
import struct
import datetime
from enum import IntEnum
from threading import Thread
from Cryptodome.Cipher import AES

_LOGGER = logging.getLogger(__name__)

MULTICAST_ADDRESS = "238.0.0.18"
UDP_PORT_SEND = 32100
UDP_PORT_RECEIVE = 32101
SOCKET_BUFSIZE = 4096
MAX_RESPONSE_LENGTH = 1024

DEVICE_TYPES_GATEWAY = ["02000001", "02000002"]  # Gateway
DEVICE_TYPE_BLIND = "10000000"  # Standard Blind
DEVICE_TYPE_TDBU = "10000001"  # Top Down Bottom Up
DEVICE_TYPE_DR = "10000002"  # Double Roller

DEVICE_TYPE_WIFI_CURTAIN = "22000000"  # Curtain direct WiFi
DEVICE_TYPE_WIFI_BLIND = "22000002"  # Standard Blind direct WiFi
DEVICE_TYPES_WIFI = [
    DEVICE_TYPE_WIFI_BLIND,
    DEVICE_TYPE_WIFI_CURTAIN,
]  # Direct WiFi devices

DEVICE_TYPES_CONTROLLER = DEVICE_TYPES_GATEWAY + DEVICE_TYPES_WIFI


class ParseException(Exception):
    """Exception wrapping any parse errors of a response send by a cover."""


class GatewayStatus(IntEnum):
    """Status of the gateway."""

    Unknown = -1
    Working = 1
    Pairing = 2
    Updating = 3


class BlindType(IntEnum):
    """Blind type matching of the blind using the values provided by the motion-gateway."""

    Unknown = -1
    RollerBlind = 1
    VenetianBlind = 2
    RomanBlind = 3
    HoneycombBlind = 4
    ShangriLaBlind = 5
    RollerShutter = 6
    RollerGate = 7
    Awning = 8
    TopDownBottomUp = 9
    DayNightBlind = 10
    DimmingBlind = 11
    Curtain = 12
    CurtainLeft = 13
    CurtainRight = 14
    DoubleRoller = 17
    VerticalBlindLeft = 21
    WoodShutter = 22
    SkylightBlind = 26
    DualShade = 27
    VerticalBlind = 28
    VerticalBlindRight = 29
    Switch = 43


class BlindStatus(IntEnum):
    """Status of the blind."""

    Unknown = -1
    Closing = 0
    Opening = 1
    Stopped = 2
    StatusQuery = 5
    FirmwareBug = 6
    JogUp = 7
    JogDown = 8


class LimitStatus(IntEnum):
    """Limit status of the blind."""

    Unknown = -1
    NoLimitDetected = 0
    TopLimitDetected = 1
    BottomLimitDetected = 2
    BothLimitsDetected = 3
    Limit3Detected = 4


class VoltageMode(IntEnum):
    """Voltage mode of the blind."""

    Unknown = -1
    AC = 0
    DC = 1


class WirelessMode(IntEnum):
    """Wireless mode of the blind."""

    Unknown = -1
    UniDirection = 0
    BiDirection = 1
    BiDirectionLimits = 2
    WiFi = 3
    VirtualPercentageLimits = 4
    Others = 5


def log_hide(message):
    """Hide security sensitive information from log messages"""
    mess_copy = message.copy()

    if not isinstance(mess_copy, dict):
        return mess_copy

    hide_pattern = re.compile("[a-zA-Z0-9]")
    if "token" in mess_copy:
        mess_copy["token"] = re.sub(hide_pattern, "x", mess_copy["token"])
    if "AccessToken" in mess_copy:
        mess_copy["AccessToken"] = re.sub(hide_pattern, "x", mess_copy["AccessToken"])

    return mess_copy


class MotionCommunication:
    """Communication class for Motion Gateways."""

    def _get_timestamp(self):
        """Get the current time and format according to required Message-ID (Timestamp)."""
        time = datetime.datetime.utcnow()
        time_str = time.strftime("%Y%m%d%H%M%S%f")[:-3]

        return time_str

    def _create_mcast_socket(self, interface, bind_interface, blocking=True):
        """Create and bind a socket for communication."""
        # Host IP adress is recommended as interface.
        if interface == "any":
            ip32bit = socket.INADDR_ANY
            bind_interface = False
            mreq = struct.pack("=4sl", socket.inet_aton(MULTICAST_ADDRESS), ip32bit)
        else:
            ip32bit = socket.inet_aton(interface)
            mreq = socket.inet_aton(MULTICAST_ADDRESS) + ip32bit

        udp_socket = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP
        )
        udp_socket.setblocking(blocking)

        # Required for receiving multicast
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            udp_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, ip32bit)
        except:
            _LOGGER.error(
                "Error creating multicast socket using IPPROTO_IP, trying SOL_IP"
            )
            udp_socket.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_IF, ip32bit)

        try:
            udp_socket.setsockopt(
                socket.IPPROTO_IP,
                socket.IP_ADD_MEMBERSHIP,
                mreq,
            )
        except:
            _LOGGER.error(
                "Error adding multicast socket membership using IPPROTO_IP, trying SOL_IP"
            )
            udp_socket.setsockopt(
                socket.SOL_IP,
                socket.IP_ADD_MEMBERSHIP,
                mreq,
            )

        udp_socket.bind((interface if bind_interface else "", UDP_PORT_RECEIVE))

        return udp_socket


class MotionDiscovery(MotionCommunication):
    """Multicast UDP discovery of Motion Gateways."""

    def __init__(self, interface="any", bind_interface=True, discovery_time=10.0):
        self._mcastsocket = None
        self._interface = interface
        self._bind_interface = bind_interface
        self._discovery_time = discovery_time

        self._discovered_devices = {}

    def discover(self):
        """Discover motion gateways."""
        self._mcastsocket = self._create_mcast_socket(
            self._interface, self._bind_interface
        )
        self._mcastsocket.settimeout(self._discovery_time)

        msg = {"msgType": "GetDeviceList", "msgID": self._get_timestamp()}

        self._mcastsocket.sendto(
            bytes(json.dumps(msg), "utf-8"), (MULTICAST_ADDRESS, UDP_PORT_SEND)
        )

        start_time = datetime.datetime.utcnow()
        while True:
            time_delta = datetime.datetime.utcnow() - start_time

            if time_delta.total_seconds() > self._discovery_time:
                break

            try:
                data, (ip, _) = self._mcastsocket.recvfrom(SOCKET_BUFSIZE)
                response = json.loads(data)

                # check msgType
                msgType = response.get("msgType")
                if msgType != "GetDeviceListAck":
                    if msgType != "Heartbeat":
                        _LOGGER.error(
                            "Response from discovery is not a GetDeviceListAck but '%s'.",
                            msgType,
                        )
                    continue

                # check device_type
                device_type = response.get("deviceType")
                if device_type not in DEVICE_TYPES_CONTROLLER:
                    _LOGGER.error(
                        "DeviceType %s does not correspond to a gateway or WiFi blind from a discovery response.",
                        device_type,
                    )
                    continue

                # add to discovered devices
                self._discovered_devices[ip] = response
            except socket.timeout:
                break

        self._mcastsocket.close()

        if not self._discovered_devices:
            _LOGGER.warning(
                "No Motion gateways discovered after %.1f seconds.",
                self._discovery_time,
            )

        return self._discovered_devices

    @property
    def discovered_devices(self):
        """Return the discovered devices."""
        return self._discovered_devices


class MotionMulticast(MotionCommunication):
    """Multicast UDP communication class for a MotionGateway."""

    def __init__(self, interface="any", bind_interface=True):
        self._listening = False
        self._mcastsocket = None
        self._thread = None
        self._interface = interface
        self._bind_interface = bind_interface

        self._registered_callbacks = {}

    def _listen_to_msg(self):
        """Listen loop for UDP multicast messages for the Motion Gateway."""
        while self._listening:
            if self._mcastsocket is None:
                continue
            try:
                data, (ip_add, _) = self._mcastsocket.recvfrom(SOCKET_BUFSIZE)
            except socket.timeout:
                continue
            try:
                message = json.loads(data)

                if ip_add not in self._registered_callbacks:
                    _LOGGER.info("Unknown motion gateway ip %s", ip_add)
                    continue

                callback = self._registered_callbacks[ip_add]
                callback(message)

            except Exception:
                _LOGGER.exception(
                    "Cannot process multicast message: '%s'", log_hide(data)
                )
                continue

        _LOGGER.info("Listener stopped")

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
        if ip in self._registered_callbacks:
            _LOGGER.error(
                "A callback for ip '%s' was already registed, overwriting previous callback",
                ip,
            )
        self._registered_callbacks[ip] = callback

    def Unregister_motion_gateway(self, ip):
        """Unregister a Motion Gateway from this Multicast listener."""
        if ip in self._registered_callbacks:
            self._registered_callbacks.pop(ip)

    def Start_listen(self):
        """Start listening."""
        if self._listening:
            _LOGGER.error(
                "Multicast listener already started, not starting another one."
            )
            return

        self._listening = True

        if self._mcastsocket is None:
            _LOGGER.info("Creating multicast socket")
            self._mcastsocket = self._create_mcast_socket(
                self._interface, self._bind_interface
            )
            # ensure you can exit the _listen_to_msg loop
            self._mcastsocket.settimeout(2.0)
        else:
            _LOGGER.error("Multicast socket was already created.")

        if self._thread is None:
            self._thread = Thread(target=self._listen_to_msg, args=())
            self._thread.daemon = True
            self._thread.start()
        else:
            _LOGGER.error("Multicast thread was already created.")
            self._thread.daemon = True
            self._thread.start()

    def Stop_listen(self):
        """Stop listening."""
        self._listening = False

        if self._thread is not None:
            self._thread.join()

        self._thread = None
        _LOGGER.info("Multicast thread stopped")

        if self._mcastsocket is not None:
            self._mcastsocket.close()
            self._mcastsocket = None


class MotionGateway(MotionCommunication):
    """Main class representing the Motion Gateway."""

    def __init__(
        self,
        ip: str = None,
        key: str = None,
        timeout: float = 3.0,
        mcast_timeout: float = 5.0,
        multi_resp_timeout: float = 0.2,
        multicast: MotionMulticast = None,
    ):
        self._ip = ip
        self._key = key
        self._token = None

        self._access_token = None
        self._gateway_mac = None
        self._timeout = timeout
        self._mcast_timeout = mcast_timeout
        self._multi_resp_timeout = multi_resp_timeout

        self._multicast = multicast
        self._registered_callbacks = {}

        self._device_list = {}
        self._device_type = None
        self._status = None
        self._available = False
        self._N_devices = None
        self._RSSI = None
        self._protocol_version = None
        self._firmware_version = None

        self._received_multicast_msg = False

        if self._multicast is not None:
            self._multicast.Register_motion_gateway(ip, self.multicast_callback)

    def __repr__(self):
        return (
            f"<MotionGateway ip: {self._ip}, mac: {self.mac}, protocol: {self.protocol}, firmware: {self.firmware}, N_devices: {self.N_devices}, status: {self.status}, RSSI: {self.RSSI} dBm>"
        )

    def _get_access_token(self):
        """Calculate the AccessToken from the Key and Token."""
        if self._token is None:
            _LOGGER.error(
                "Token not yet retrieved, use GetDeviceList to obtain it before using _get_access_token."
            )
            return None
        if self._key is None:
            _LOGGER.error(
                "Key not specified, specify a key when creating the gateway class like MotionGateway(ip = '192.168.1.100', key = 'abcd1234-56ef-78') when using _get_access_token."
            )
            return None

        token_bytes = bytes(self._token, "utf-8")
        key_bytes = bytes(self._key, "utf-8")

        cipher = AES.new(key_bytes, AES.MODE_ECB)
        encrypted_bytes = cipher.encrypt(token_bytes)
        self._access_token = encrypted_bytes.hex().upper()

        return self._access_token

    def _send(self, message, single_response=True):
        """Send a command to the Motion Gateway."""
        attempt = 1
        data = []
        while True:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(self._timeout)

                s.sendto(bytes(json.dumps(message), "utf-8"), (self._ip, UDP_PORT_SEND))

                while True:
                    single_data, _addr = s.recvfrom(SOCKET_BUFSIZE)
                    data.append(single_data)

                    if len(single_data) < int(0.9 * MAX_RESPONSE_LENGTH):
                        break

                    s.settimeout(self._multi_resp_timeout)

                    if single_response:
                        _LOGGER.error(
                            "Response of length %i>%i received, while only expecting single response,"
                            " while sending message '%s', got response: '%s'",
                            len(single_data),
                            int(0.9 * MAX_RESPONSE_LENGTH),
                            log_hide(message),
                            log_hide(json.loads(single_data)),
                        )
                        break

                s.close()
                break
            except socket.timeout:
                if len(data) > 0:
                    s.close()
                    break

                if attempt >= 3:
                    _LOGGER.error(
                        "Timeout of %.1f sec occurred on %i attempts while sending message '%s'",
                        self._timeout,
                        attempt,
                        log_hide(message),
                    )
                    s.close()
                    self._available = False
                    raise
                _LOGGER.debug(
                    "Timeout of %.1f sec occurred at %i attempts while sending message '%s', trying again...",
                    self._timeout,
                    attempt,
                    log_hide(message),
                )
                s.close()
                attempt += 1

        responses = []
        for d in data:
            responses.append(json.loads(d))

        for response in responses:
            if response.get("actionResult") is not None:
                _LOGGER.error(
                    "Received actionResult: '%s', when sending message: '%s', got response: '%s'",
                    response.get("actionResult"),
                    log_hide(message),
                    log_hide(response),
                )
                if response.get("token") is not None:
                    # check for token change
                    if self._token != response["token"]:
                        _LOGGER.warning("Gateway token has changed from actionResult.")
                        self._token = response["token"]
                        self._access_token = None

        if single_response:
            return responses[0]

        return responses

    def _read_subdevice(self, mac, device_type):
        """Read the status of a subdevice."""
        msg = {
            "msgType": "ReadDevice",
            "mac": mac,
            "deviceType": device_type,
            "AccessToken": self.access_token,
            "msgID": self._get_timestamp(),
        }

        return self._send(msg)

    def _write_subdevice(self, mac, device_type, data):
        """Write a command to a subdevice."""
        msg = {
            "msgType": "WriteDevice",
            "mac": mac,
            "deviceType": device_type,
            "AccessToken": self.access_token,
            "msgID": self._get_timestamp(),
            "data": data,
        }

        return self._send(msg)

    def _parse_update_response(self, response):
        """Parse the response to a update of the gateway"""

        # check device_type
        device_type = response.get("deviceType", self._device_type)
        if device_type not in DEVICE_TYPES_CONTROLLER:
            _LOGGER.warning(
                "DeviceType %s does not correspond to a gateway or WiFi blind in parse update function.",
                device_type,
            )

        # update variables
        self._gateway_mac = response["mac"]
        self._device_type = device_type
        self._available = True
        data = response.get("data")
        if data:
            self._status = GatewayStatus(
                data.get("currentState", GatewayStatus.Unknown)
            )
            self._N_devices = data.get("numberOfDevices", 0)
            self._RSSI = data.get("RSSI")

    def _parse_device_list_response(self, response):
        """Parse the response to a device list update of the gateway"""

        # check device_type of the gateway
        gw_device_type = response.get("deviceType", self._device_type)
        if gw_device_type not in DEVICE_TYPES_CONTROLLER:
            _LOGGER.warning(
                "DeviceType %s does not correspond to a gateway or WiFi blind in GetDeviceList function.",
                gw_device_type,
            )

        # check for token change
        if self._token is not None and self._token != response["token"]:
            _LOGGER.warning("Gateway token has changed.")
            self._access_token = None

        # update variables
        self._gateway_mac = response["mac"]
        self._device_type = gw_device_type
        self._protocol_version = response["ProtocolVersion"]
        self._firmware_version = response.get("fwVersion")
        self._token = response["token"]
        self._available = True

        # calculate the acces token
        self._get_access_token()

        # add the discovered blinds to the device list.
        for blind in response["data"]:
            device_type = blind["deviceType"]
            if device_type not in DEVICE_TYPES_GATEWAY:
                blind_mac = blind["mac"]
                if device_type in [DEVICE_TYPE_BLIND]:
                    self._device_list[blind_mac] = MotionBlind(
                        gateway=self, mac=blind_mac, device_type=device_type
                    )
                elif device_type in [DEVICE_TYPE_DR]:
                    self._device_list[blind_mac] = MotionBlind(
                        gateway=self,
                        mac=blind_mac,
                        device_type=device_type,
                        max_angle=90,
                    )
                elif device_type in [DEVICE_TYPE_TDBU]:
                    self._device_list[blind_mac] = MotionTopDownBottomUp(
                        gateway=self, mac=blind_mac, device_type=device_type
                    )
                elif device_type in [DEVICE_TYPE_WIFI_BLIND, DEVICE_TYPE_WIFI_CURTAIN]:
                    self._device_list[blind_mac] = MotionBlind(
                        gateway=self, mac=blind_mac, device_type=device_type
                    )
                else:
                    _LOGGER.warning(
                        "Device with mac '%s' has DeviceType '%s' that does not correspond to a gateway or known blind.",
                        blind_mac,
                        device_type,
                    )

    def multicast_callback(self, message):
        """Process a multicast push message to update data."""
        if message.get("actionResult") is not None:
            _LOGGER.error(
                "Received actionResult: '%s', on multicast listener from ip '%s', got response: '%s'",
                message["actionResult"],
                self._ip,
                log_hide(message),
            )
            return

        msgType = message.get("msgType")
        mac = message.get("mac")
        if msgType == "Report":
            if mac == self._gateway_mac:
                self._parse_update_response(message)
                for callback in self._registered_callbacks.values():
                    callback()
                return
            if mac not in self.device_list:
                if self.device_list:
                    _LOGGER.warning(
                        "Multicast push with mac '%s' not in device_list, message: '%s'",
                        mac,
                        log_hide(message),
                    )
                return
            self.device_list[mac].multicast_callback(message)
        elif msgType == "Heartbeat":
            if mac != self._gateway_mac and self._gateway_mac is not None:
                _LOGGER.warning(
                    "Multicast Heartbeat with mac '%s' does not agree with gateway mac '%s', message: '%s'",
                    mac,
                    self._gateway_mac,
                    log_hide(message),
                )
                return
            self._parse_update_response(message)
            for callback in self._registered_callbacks.values():
                callback()
        elif msgType == "GetDeviceListAck":
            if mac != self._gateway_mac and self._gateway_mac is not None:
                _LOGGER.warning(
                    "Multicast GetDeviceListAck with mac '%s' does not agree with gateway mac '%s', message: '%s'",
                    mac,
                    self._gateway_mac,
                    log_hide(message),
                )
                return
            self._parse_device_list_response(message)
            for callback in self._registered_callbacks.values():
                callback()
        else:
            _LOGGER.warning(
                "Unknown msgType '%s' received from multicast push with message: '%s'",
                msgType,
                log_hide(message),
            )
            return

    def GetDeviceList(self):
        """Get the device list from the Motion Gateway."""
        msg = {"msgType": "GetDeviceList", "msgID": self._get_timestamp()}

        try:
            responses = self._send(msg, single_response=False)
        except socket.timeout:
            for blind in self.device_list.values():
                blind._available = False
            raise

        for response in responses:
            # check msgType
            msgType = response.get("msgType")
            if msgType != "GetDeviceListAck":
                _LOGGER.error(
                    "Response to GetDeviceList is not a GetDeviceListAck but '%s'.",
                    msgType,
                )
                return self._device_list

            # parse response
            self._parse_device_list_response(response)

        return self._device_list

    def Update(self):
        """Get the status of the Motion Gateway."""
        if (
            self._gateway_mac is None
            or self._device_type is None
            or self._access_token is None
        ):
            _LOGGER.debug(
                "gateway mac or device_type not yet retrieved, first executing GetDeviceList to obtain it before continuing with Update."
            )
            self.GetDeviceList()

        msg = {
            "msgType": "ReadDevice",
            "mac": self.mac,
            "deviceType": self.device_type,
            "AccessToken": self.access_token,
            "msgID": self._get_timestamp(),
        }

        try:
            response = self._send(msg)
        except socket.timeout:
            for blind in self.device_list.values():
                blind._available = False
            raise

        # check msgType
        msgType = response.get("msgType")
        if msgType != "ReadDeviceAck":
            _LOGGER.error(
                "Response to Update is not a ReadDeviceAck but '%s'.",
                msgType,
            )
            return

        # parse response
        self._parse_update_response(response)

    def Check_gateway_multicast(self):
        """Trigger a multicast message from the gateway by issuing a GetDeviceList over multicast and check if the response is received."""
        if self._multicast is None:
            _LOGGER.error(
                "Trigger_gateway_multicast requires a MotionMulticast to be supplied during initialization"
            )
            return False

        self._received_multicast_msg = False

        def check_multicast_callback():
            self._received_multicast_msg = True

        self.Register_callback("Check_gateway_multicast", check_multicast_callback)

        # Check if device_list is not empty
        if not self.device_list:
            _LOGGER.debug(
                "Device list not yet retrieved, first executing GetDeviceList to obtain it before continuing with Check_gateway_multicast."
            )
            self.GetDeviceList()

        for blind in self.device_list.values():
            blind.Register_callback("Check_blind_multicast", check_multicast_callback)

        # Trigger multicast messages
        for blind in self.device_list.values():
            blind.Update_trigger()

        # Wait untill callback received
        start = datetime.datetime.utcnow()
        while True:
            if self._received_multicast_msg:
                break
            time_past = datetime.datetime.utcnow() - start
            if time_past.total_seconds() > self._mcast_timeout:
                break

        self.Remove_callback("Check_gateway_multicast")
        for blind in self.device_list.values():
            blind.Remove_callback("Check_blind_multicast")
        return self._received_multicast_msg

    def Register_callback(self, cb_id, callback):
        """Register a external callback function for updates of the gateway."""
        if cb_id in self._registered_callbacks:
            _LOGGER.error(
                "A callback with id '%s' was already registed, overwriting previous callback",
                cb_id,
            )
        self._registered_callbacks[cb_id] = callback

    def Remove_callback(self, cb_id):
        """Remove a external callback using its id."""
        self._registered_callbacks.pop(cb_id)

    def Clear_callbacks(self):
        """Remove all external registered callbacks for updates of the gateway."""
        self._registered_callbacks.clear()

    @property
    def available(self):
        """Return if the blind is available."""
        return self._available

    @property
    def status(self):
        """Return gateway status: from GatewayStatus enum."""
        if self._status is not None:
            return self._status.name

        return self._status

    @property
    def N_devices(self):
        """Return the number of connected child devices."""
        return self._N_devices

    @property
    def RSSI(self):
        """Return the Wi-Fi connection strength of the gateway in dBm."""
        return self._RSSI

    @property
    def token(self):
        """Return the Token."""
        return self._token

    @property
    def access_token(self):
        """Return the AccessToken."""
        if self._access_token is None:
            if self._token is None:
                _LOGGER.error(
                    "Token not yet retrieved, use GetDeviceList to obtain it before using the access_token."
                )
                return None
            if self._key is None:
                _LOGGER.error(
                    "Key not specified, specify a key when creating the gateway class like MotionGateway(ip = '192.168.1.100', key = 'abcd1234-56ef-78') when using the access_token."
                )
                return None
            # calculate the acces token
            self._get_access_token()

        return self._access_token

    @property
    def mac(self):
        """Return the mac address of the gateway."""
        if self._gateway_mac is None:
            _LOGGER.error(
                "gateway mac not yet retrieved, use GetDeviceList to obtain it before using the mac."
            )
            return None

        return self._gateway_mac

    @property
    def device_type(self):
        """Return the device type of the gateway."""
        if self._device_type is None:
            _LOGGER.error(
                "gateway device_type not yet retrieved, use GetDeviceList to obtain it before using the device_type."
            )
            return None

        return self._device_type

    @property
    def protocol(self):
        """Return the protocol version of the gateway."""
        return self._protocol_version

    @property
    def firmware(self):
        """Return the firmware version of the gateway."""
        return self._firmware_version

    @property
    def device_list(self):
        """
        Return a dict containing all blinds connected to the gateway.

        The keys in the dict are the mac adresses of the blinds.
        """
        return self._device_list


class MotionBlind:
    """Sub class representing a blind connected to the Motion Gateway."""

    QUERY_DATA = {"operation": 5}

    def __init__(
        self,
        gateway: MotionGateway = None,
        mac: str = None,
        device_type: str = None,
        max_angle: int = 180,
    ):
        self._gateway = gateway
        self._mac = mac
        self._device_type = device_type
        self._blind_type = None
        self._wireless_mode = None
        self._voltage_mode = None
        self._max_angle = max_angle

        self._registered_callbacks = {}
        self._last_status_report = datetime.datetime.utcnow()

        self._status = None
        self._available = False
        self._limit_status = None
        self._position = None
        self._angle = None
        self._restore_angle = None
        self._battery_voltage = None
        self._battery_level = None
        self._is_charging = None
        self._RSSI = None

    def __repr__(self):
        if self._wireless_mode == WirelessMode.UniDirection:
            return f"<MotionBlind mac: {self.mac}, type: {self.blind_type}, status: {self.status}, com: {self.wireless_name}>"

        if self._wireless_mode == WirelessMode.BiDirectionLimits:
            return (
                f"<MotionBlind mac: {self.mac}, type: {self.blind_type}, status: {self.status}, limit: {self.limit_status}, "
                f"battery: {self.voltage_name}, {self.battery_level} %, {self.battery_voltage} V, charging: {self.is_charging}, RSSI: {self.RSSI} dBm, com: {self.wireless_name}>"
            )

        return (
            f"<MotionBlind mac: {self.mac}, type: {self.blind_type}, status: {self.status}, position: {self.position} %, angle: {self.angle}, "
            f"limit: {self.limit_status}, battery: {self.voltage_name}, {self.battery_level} %, {self.battery_voltage} V, charging: {self.is_charging}, RSSI: {self.RSSI} dBm, com: {self.wireless_name}>"
        )

    def _write(self, data):
        """Write a command to control the blind."""

        response = self._gateway._write_subdevice(self.mac, self._device_type, data)

        # check msgType
        msgType = response.get("msgType")
        if msgType != "WriteDeviceAck":
            _LOGGER.error(
                "Response to Write is not a WriteDeviceAck but '%s'.",
                msgType,
            )

        return response

    def _wait_on_mcast_report(self, mcast_socket):
        """Wait untill a status report is received from the multicast socket"""
        while True:
            try:
                mcast_data, (ip, _) = mcast_socket.recvfrom(SOCKET_BUFSIZE)
                mcast_response = json.loads(mcast_data)

                # check ip
                if ip != self._gateway._ip:
                    _LOGGER.debug(
                        "Received multicast push from a diffrent gateway with ip '%s', in Update function",
                        ip,
                    )
                    continue

                # check mac
                if mcast_response.get("mac") != self.mac:
                    _LOGGER.debug(
                        "Received multicast push regarding a diffrent blind with mac '%s', in Update function",
                        mcast_response.get("mac"),
                    )
                    continue

                # check actionResult
                if mcast_response.get("actionResult") is not None:
                    _LOGGER.error(
                        "Received actionResult: '%s' from multicast push within Update function",
                        mcast_response.get("actionResult"),
                    )
                    continue

                # check msgType
                msgType = mcast_response.get("msgType")
                if msgType != "Report":
                    _LOGGER.debug(
                        "Response to update on multicast is not a Report but '%s'.",
                        msgType,
                    )
                    continue

                # done
                mcast_socket.close()
                return mcast_response
            except socket.timeout:
                mcast_socket.close()
                raise

    def _calculate_battery_level(self, voltage):
        if 0.0 < voltage <= 9.4:
            # 2 cel battery pack (8.4V)
            return round((voltage - 6.2) * 100 / (8.4 - 6.2), 0)

        if 9.4 < voltage <= 13.6:
            # 3 cel battery pack (12.6V)
            return round((voltage - 10.4) * 100 / (12.6 - 10.4), 0)

        if 13.6 < voltage <= 19.0:
            # 4 cel battery pack (16.8V)
            return round((voltage - 14.6) * 100 / (16.8 - 14.6), 0)

        if voltage == 220.0:
            # AC motor
            return None

        if voltage <= 0.0:
            return 0.0

        return 200.0

    def _parse_response_common(self, response):
        """Parse the common part of a response form the blind."""

        # Check for actionResult (errors)
        if response.get("actionResult") is not None:
            # Error already logged in _send function
            return False

        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug("Parsing response: '%s'", log_hide(response))

        # check device_type
        device_type = response.get("deviceType", self._device_type)
        if device_type not in [
            DEVICE_TYPE_BLIND,
            DEVICE_TYPE_TDBU,
            DEVICE_TYPE_DR,
            DEVICE_TYPE_WIFI_BLIND,
            DEVICE_TYPE_WIFI_CURTAIN,
        ]:
            _LOGGER.warning(
                "Device with mac '%s' has DeviceType '%s' that does not correspond to a known blind in Update function.",
                self.mac,
                device_type,
            )

        # update variables
        self._mac = response.get("mac", self._mac)
        self._device_type = device_type
        try:
            self._blind_type = BlindType(response["data"]["type"])
        except KeyError:
            if self._blind_type is None:
                _LOGGER.info(
                    "Device with mac '%s' has no blind_type in the status response, using the default 'RollerBlind' type.",
                    self.mac,
                )
                self._blind_type = BlindType.RollerBlind
        except ValueError:
            if self._blind_type != BlindType.Unknown:
                _LOGGER.error(
                    "Device with mac '%s' has blind_type '%s' that is not yet known, please submit an issue at https://github.com/starkillerOG/motion-blinds/issues.",
                    self.mac,
                    response["data"]["type"],
                )
            self._blind_type = BlindType.Unknown

        try:
            self._wireless_mode = WirelessMode(response["data"]["wirelessMode"])
        except KeyError:
            pass
        except ValueError:
            if self._wireless_mode != WirelessMode.Unknown:
                _LOGGER.error(
                    "Device with mac '%s' has wireless_mode '%s' that is not yet known, please submit an issue at https://github.com/starkillerOG/motion-blinds/issues.",
                    self.mac,
                    response["data"].get("wirelessMode"),
                )
            self._wireless_mode = WirelessMode.Unknown

        try:
            self._voltage_mode = VoltageMode(response["data"]["voltageMode"])
        except KeyError:
            pass
        except ValueError:
            if self._voltage_mode != VoltageMode.Unknown:
                _LOGGER.error(
                    "Device with mac '%s' has voltage_mode '%s' that is not yet known, please submit an issue at https://github.com/starkillerOG/motion-blinds/issues.",
                    self.mac,
                    response["data"].get("voltageMode"),
                )
            self._voltage_mode = VoltageMode.Unknown

        # Check max angle
        if self._blind_type in [BlindType.ShangriLaBlind]:
            self._max_angle = 90

        self._available = True

        if self._wireless_mode == WirelessMode.UniDirection:
            return True

        try:
            self._RSSI = response["data"]["RSSI"]
        except KeyError:
            pass

        try:
            self._is_charging = response["data"]["chargingState"]
        except KeyError:
            pass

        return True

    def _parse_response(self, response):
        """Parse a response form the blind."""
        try:
            # handle the part that is common among all blinds
            if not self._parse_response_common(response):
                return

            # handle specific properties
            try:
                self._status = BlindStatus(response["data"]["operation"])
            except KeyError:
                self._status = BlindStatus.Unknown
            except ValueError:
                if self._status != BlindStatus.Unknown:
                    _LOGGER.error(
                        "Device with mac '%s' has status '%s' that is not yet known, please submit an issue at https://github.com/starkillerOG/motion-blinds/issues.",
                        self.mac,
                        response["data"]["operation"],
                    )
                self._status = BlindStatus.Unknown

            if self._wireless_mode == WirelessMode.UniDirection:
                return

            try:
                self._limit_status = LimitStatus(response["data"]["currentState"])
            except KeyError:
                self._limit_status = LimitStatus.Unknown
            except ValueError:
                if self._limit_status != LimitStatus.Unknown:
                    _LOGGER.error(
                        "Device with mac '%s' has limit_status '%s' that is not yet known, please submit an issue at https://github.com/starkillerOG/motion-blinds/issues.",
                        self.mac,
                        response["data"]["currentState"],
                    )
                self._status = LimitStatus.Unknown

            try:
                self._battery_voltage = response["data"]["batteryLevel"] / 100.0
            except KeyError:
                self._battery_voltage = None
            else:
                self._battery_level = self._calculate_battery_level(
                    self._battery_voltage
                )
                if self._voltage_mode != VoltageMode.AC and (self._battery_voltage <= 0.0 or self._battery_level >= 200.0):
                    _LOGGER.debug(
                        "Device with mac '%s' reported voltage '%s' outside of expected limits, got raw voltage: '%s'",
                        self.mac,
                        self._battery_voltage,
                        response["data"]["batteryLevel"],
                    )

            if self._wireless_mode == WirelessMode.BiDirectionLimits:
                return

            if self._wireless_mode == WirelessMode.VirtualPercentageLimits and self._limit_status < LimitStatus.BothLimitsDetected:
                _LOGGER.warning("Virtual percentage motor with mac '%s' has mechanical limit status '%s'"
                    ", both mechanical limits need to be detected before percentage control can be used",
                    self.mac,
                    self.limit_status,
                )
                return

            self._position = response["data"].get("currentPosition", 1)
            self._angle = response["data"].get("currentAngle", 0) * (180.0 / self._max_angle)
            if self._angle != 0:
                self._restore_angle = self._angle
        except (KeyError, ValueError) as ex:
            _LOGGER.exception(
                "Device with mac '%s' send an response with unexpected data, please submit an issue at https://github.com/starkillerOG/motion-blinds/issues. Response: '%s'",
                self.mac,
                log_hide(response),
            )
            raise ParseException(
                f"Got an exception while parsing response: {log_hide(response)}"
            ) from ex

    def multicast_callback(self, message):
        """Process a multicast push message to update data."""
        self._parse_response(message)

        if message.get("msgType") == "Report":
            self._last_status_report = datetime.datetime.utcnow()

        for callback in self._registered_callbacks.values():
            callback()

    def Update_from_cache(self):
        """
        Get the status of the blind from the cache of the Motion Gateway

        No 433MHz radio communication with the blind takes place.
        """
        response = self._gateway._read_subdevice(self.mac, self._device_type)

        # check msgType
        msgType = response.get("msgType")
        if msgType != "ReadDeviceAck":
            _LOGGER.error(
                "Response to Update is not a ReadDeviceAck but '%s'.",
                msgType,
            )
            return

        self._parse_response(response)

    def Update_trigger(self):
        """
        Get the status of the blind from the cache of the Motion Gateway and request a new status from the blind

        This will send a query to the blind to retrieve its status, but does not wait for that new status.
        The Gateway will imediatly respond with the status of the blind from cache (old status), this status is processed.
        The multicast push response of the blind over 433MHz radio is not awaited.
        """
        response = self._write(self.QUERY_DATA)

        # parse status from cache
        self._parse_response(response)

    def Update(self):
        """
        Get the status of the blind from the blind through the Motion Gateway

        This will send a query to the blind to retrieve its status.
        The Gateway will imediatly respond with the status of the blind from cache (old status).
        As soon as the blind responds over 433MHz radio, a multicast push will be sent out by the gateway with the new status.
        """
        if self._wireless_mode == WirelessMode.UniDirection:
            # UniDirection blinds cannot send their state, so do not wait on multicast
            self.Update_trigger()
            return

        attempt = 1
        while True:
            if self._gateway._multicast is None:
                mcast = self._gateway._create_mcast_socket("any", False)
                mcast.settimeout(self._gateway._mcast_timeout)
            else:
                start = datetime.datetime.utcnow()

            # send update request
            self.Update_trigger()

            # wait on multicast push for new status
            try:
                if self._gateway._multicast is None:
                    mcast_response = self._wait_on_mcast_report(mcast)

                    self._parse_response(mcast_response)
                    break

                while True:
                    time_diff = self._last_status_report - start
                    if time_diff.total_seconds() > 0:
                        break
                    time_past = datetime.datetime.utcnow() - start
                    if time_past.total_seconds() > self._gateway._mcast_timeout:
                        raise socket.timeout
                break
            except socket.timeout:
                if attempt >= 5:
                    _LOGGER.error(
                        "Timeout of %.1f sec occurred on %i attempts while waiting on multicast push from update request, communication between gateway and blind might be bad.",
                        self._gateway._mcast_timeout,
                        attempt,
                    )
                    self._available = False
                    raise
                _LOGGER.debug(
                    "Timeout of %.1f sec occurred at %i attempts while waiting on multicast push from update request, trying again...",
                    self._gateway._mcast_timeout,
                    attempt,
                )
                attempt += 1

    def Stop(self):
        """Stop the motion of the blind."""
        data = {"operation": 2}

        response = self._write(data)

        self._parse_response(response)

    def Open(self):
        """Open the blind/move the blind up."""
        data = {"operation": 1}

        response = self._write(data)

        self._parse_response(response)

    def Close(self):
        """Close the blind/move the blind down."""
        data = {"operation": 0}

        response = self._write(data)

        self._parse_response(response)

    def Set_position(self, position, angle=None, restore_angle=False):
        """
        Set the position of the blind.
        Optionally also set angle or restore current angle.

        position is in %, so 0-100
        0 = open
        100 = closed
        angle is in degrees, so 0-180
        """
        data = {"targetPosition": position}
        if restore_angle and self._restore_angle is not None and position != 0:
            target_angle = round(self._restore_angle * self._max_angle / 180.0, 0)
            data["targetAngle"] = target_angle
        if angle is not None:
            target_angle = round(angle * self._max_angle / 180.0, 0)
            data["targetAngle"] = target_angle

        response = self._write(data)

        self._parse_response(response)

    def Set_angle(self, angle):
        """
        Set the angle/rotation of the blind.

        angle is in degrees, so 0-180
        """
        target_angle = round(angle * self._max_angle / 180.0, 0)

        data = {"targetAngle": target_angle}

        response = self._write(data)

        self._parse_response(response)

    def Jog_up(self):
        """Open the blind/move the blind one step up."""
        data = {"operation": 7}

        response = self._write(data)

        self._parse_response(response)

    def Jog_down(self):
        """Close the blind/move the blind one step down."""
        data = {"operation": 8}

        response = self._write(data)

        self._parse_response(response)

    def Register_callback(self, cb_id, callback):
        """Register a external callback function for updates of this blind."""
        if cb_id in self._registered_callbacks:
            _LOGGER.error(
                "A callback with id '%s' was already registed, overwriting previous callback",
                cb_id,
            )
        self._registered_callbacks[cb_id] = callback

    def Remove_callback(self, cb_id):
        """Remove a external callback using its id."""
        self._registered_callbacks.pop(cb_id)

    def Clear_callbacks(self):
        """Remove all external registered callbacks for updates of this blind."""
        self._registered_callbacks.clear()

    @property
    def device_type(self):
        """Return the device type of the blind."""
        if self._device_type is None:
            _LOGGER.error(
                "blind device_type not yet retrieved, use Update to obtain it before using the device_type."
            )
            return None

        return self._device_type

    @property
    def blind_type(self):
        """Return the type of the blind from BlindType enum."""
        if self._blind_type is not None:
            return self._blind_type.name

        return self._blind_type

    @property
    def type(self):
        """Return the type of the blind as a BlindType enum."""
        return self._blind_type

    @property
    def wireless_mode(self):
        """Return the wireless mode of the blind as a WirelessMode enum."""
        return self._wireless_mode

    @property
    def wireless_name(self):
        """Return the wireless mode of the blind from WirelessMode enum as a string."""
        if self._wireless_mode is not None:
            return self._wireless_mode.name

        return self._wireless_mode

    @property
    def voltage_mode(self):
        """Return the voltage mode of the blind as a VoltageMode enum."""
        return self._voltage_mode

    @property
    def voltage_name(self):
        """Return the voltage mode of the blind from VoltageMode enum as a string."""
        if self._voltage_mode is not None:
            return self._voltage_mode.name

        return self._voltage_mode

    @property
    def mac(self):
        """Return the mac address of the blind."""
        return self._mac

    @property
    def available(self):
        """Return if the blind is available."""
        return self._available

    @property
    def status(self):
        """Return the current status of the blind from BlindStatus enum."""
        if self._status is not None:
            return self._status.name

        return self._status

    @property
    def limit_status(self):
        """Return the current status of the limit detection of the blind from LimitStatus enum."""
        if self._limit_status is not None:
            return self._limit_status.name

        return self._limit_status

    @property
    def position(self):
        """Return the current position of the blind in % (0-100)."""
        return self._position

    @property
    def angle(self):
        """Return the current angle of the blind 0-180."""
        return self._angle

    @property
    def battery_voltage(self):
        """Return the current battery voltage of the blind in V."""
        return self._battery_voltage

    @property
    def battery_level(self):
        """Return the current battery level of the blind in %."""
        return self._battery_level

    @property
    def is_charging(self):
        """Return if the blind is currently charging its battery."""
        if self._is_charging is None:
            return None
        return self._is_charging == 1

    @property
    def RSSI(self):
        """Return the radio connection strength of the blind to the gateway in dBm."""
        return self._RSSI


class MotionTopDownBottomUp(MotionBlind):
    """Sub class representing a Top Down Bottom Up blind connected to the Motion Gateway."""

    QUERY_DATA = {"operation_T": 5, "operation_B": 5}

    def __init__(
        self,
        gateway: MotionGateway = None,
        mac: str = None,
        device_type: str = None,
        max_angle: int = 180,
    ):
        super().__init__(gateway, mac, device_type, max_angle)
        self._position = {"T": 0, "B": 0, "C": 0}
        self._battery_voltage = {"T": None, "B": None}
        self._battery_level = {"T": None, "B": None}

    def __repr__(self):
        return (
            f"<MotionBlind mac: {self.mac}, type: {self.blind_type}, status: {self.status}, "
            f"position: {self.position} %, scaled_position: {self.scaled_position} %, width: {self.width} %, "
            f"limit: {self.limit_status}, battery: {self.voltage_name}, {self.battery_level} %, {self.battery_voltage} V, charging: {self.is_charging}, RSSI: {self.RSSI} dBm, com: {self.wireless_name}>"
        )

    def _parse_response(self, response):
        """Parse a response form the blind."""
        try:
            # handle the part that is common among all blinds
            if not self._parse_response_common(response):
                return

            # handle specific properties
            try:
                self._status = {
                    "T": BlindStatus(response["data"]["operation_T"]),
                    "B": BlindStatus(response["data"]["operation_B"]),
                }
            except KeyError:
                self._status = {"T": BlindStatus.Unknown, "B": BlindStatus.Unknown}
            except ValueError:
                if self._status != {"T": BlindStatus.Unknown, "B": BlindStatus.Unknown}:
                    _LOGGER.error(
                        "Device with mac '%s' has status T: '%s', B: '%s' that is not yet known, please submit an issue at https://github.com/starkillerOG/motion-blinds/issues.",
                        self.mac,
                        response["data"].get("operation_T"),
                        response["data"].get("operation_B"),
                    )
                self._status = {"T": BlindStatus.Unknown, "B": BlindStatus.Unknown}

            try:
                self._limit_status = {
                    "T": LimitStatus(response["data"]["currentState_T"]),
                    "B": LimitStatus(response["data"]["currentState_B"]),
                }
            except KeyError:
                self._limit_status = {
                    "T": LimitStatus.Unknown,
                    "B": LimitStatus.Unknown,
                }
            except ValueError:
                if self._limit_status != {
                    "T": LimitStatus.Unknown,
                    "B": LimitStatus.Unknown,
                }:
                    _LOGGER.error(
                        "Device with mac '%s' has limit status T: '%s', B: '%s' that is not yet known, please submit an issue at https://github.com/starkillerOG/motion-blinds/issues.",
                        self.mac,
                        response["data"].get("currentState_T"),
                        response["data"].get("currentState_B"),
                    )
                self._limit_status = {
                    "T": LimitStatus.Unknown,
                    "B": LimitStatus.Unknown,
                }

            try:
                pos_T = response["data"]["currentPosition_T"]
                pos_B = response["data"]["currentPosition_B"]
            except KeyError:
                _LOGGER.error(
                    "Device with mac '%s' send status that did not include the position of the TDBU.",
                    self.mac,
                )
                pos_T = self._position["T"]
                pos_B = self._position["B"]

            pos_C = (pos_T + pos_B) / 2.0
            self._position = {"T": pos_T, "B": pos_B, "C": pos_C}
            self._angle = None

            try:
                self._battery_voltage = {
                    "T": response["data"]["batteryLevel_T"] / 100.0,
                    "B": response["data"]["batteryLevel_B"] / 100.0,
                }
            except KeyError:
                self._battery_voltage = {"T": None, "B": None}
            else:
                self._battery_level = {
                    "T": self._calculate_battery_level(self._battery_voltage["T"]),
                    "B": self._calculate_battery_level(self._battery_voltage["B"]),
                }
                if (
                    self._voltage_mode != VoltageMode.AC
                    and (self._battery_level["T"] >= 200.0
                    or self._battery_level["B"] >= 200.0
                    or self._battery_voltage["T"] <= 0.0
                    or self._battery_voltage["B"] <= 0.0)
                ):
                    _LOGGER.debug(
                        "Device with mac '%s' reported voltage '%s' outside of expected limits, got raw voltages: '%s', '%s'",
                        self.mac,
                        self._battery_voltage,
                        response["data"]["batteryLevel_T"],
                        response["data"]["batteryLevel_B"],
                    )

        except (KeyError, ValueError) as ex:
            _LOGGER.exception(
                "Device with mac '%s' send an response with unexpected data, please submit an issue at https://github.com/starkillerOG/motion-blinds/issues. Response: '%s'",
                self.mac,
                log_hide(response),
            )
            raise ParseException(
                f"Got an exception while parsing response: {log_hide(response)}"
            ) from ex

    def Stop(self, motor: str = "B"):
        """Stop the motion of the blind."""
        if motor == "B":
            data = {"operation_B": 2}
        elif motor == "T":
            data = {"operation_T": 2}
        elif motor == "C":
            data = {"operation_B": 2, "operation_T": 2}
        else:
            _LOGGER.error(
                'Please specify which motor to control "T" (top), "B" (bottom) or "C" (combined)'
            )
            return

        response = self._write(data)

        self._parse_response(response)

    def Open(self, motor: str = "B"):
        """Open the blind/move the blind up."""
        if motor == "B":
            data = {"targetPosition_B": 0}
        elif motor == "T":
            data = {"targetPosition_T": 0}
        elif motor == "C":
            data = {"targetPosition_B": 0, "targetPosition_T": 0}
        else:
            _LOGGER.error(
                'Please specify which motor to control "T" (top), "B" (bottom) or "C" (combined)'
            )
            return

        response = self._write(data)

        self._parse_response(response)

    def Close(self, motor: str = "B"):
        """Close the blind/move the blind down."""
        if motor == "B":
            data = {"targetPosition_B": 100}
        elif motor == "T":
            data = {"targetPosition_T": 100}
        elif motor == "C":
            data = {"targetPosition_B": 100, "targetPosition_T": 0}
        else:
            _LOGGER.error(
                'Please specify which motor to control "T" (top), "B" (bottom) or "C" (combined)'
            )
            return

        response = self._write(data)

        self._parse_response(response)

    def Set_position(self, position, motor: str = "B", width: int = None):  # pylint: disable=W0237
        """
        Set the position of the blind.

        position is in %, so 0-100
        0 = open
        100 = closed
        """
        if width is None:
            width = self.width

        if motor == "B":
            if position >= self._position["T"]:
                data = {"targetPosition_B": position}
            else:
                _LOGGER.error(
                    "Error setting position, the bottom of the TDBU blind can not go above the top of the TDBU blind"
                )
                return
        elif motor == "T":
            if position <= self._position["B"]:
                data = {"targetPosition_T": position}
            else:
                _LOGGER.error(
                    "Error setting position, the top of the TDBU blind can not go below the bottom of the TDBU blind"
                )
                return
        elif motor == "C":
            if width / 2.0 <= position <= (100 - width / 2.0):
                data = {
                    "targetPosition_T": position - width / 2.0,
                    "targetPosition_B": position + width / 2.0,
                }
            else:
                _LOGGER.error(
                    "Error setting position, the combined TDBU blind cannot reach position %.1f, because including the width of %.1f, it would exceed its limits",
                    position,
                    width,
                )
                return
        else:
            _LOGGER.error(
                'Please specify which motor to control "T" (top), "B" (bottom) or "C" (combined)'
            )
            return

        response = self._write(data)

        self._parse_response(response)

    def Set_scaled_position(self, scaled_position, motor: str = "B"):
        """
        Set the scaled position of the blind.

        scaled_position is in %, so 0-100
        for top blind:
            0 = open
            100 = at position of bottom blind
        for bottom blind:
            0 = at position of the top blind
            100 = closed
        """
        if motor == "B":
            pos_bottom = self._position["T"] + (100.0 - self._position["T"]) * scaled_position / 100.0
            self.Set_position(pos_bottom, motor)
            return
        if motor == "T":
            pos_top = scaled_position * self._position["B"] / 100.0
            self.Set_position(pos_top, motor)
            return
        if motor == "C":
            pos_combined = self.width / 2.0 + scaled_position * (100.0 - self.width) / 100.0
            self.Set_position(pos_combined, motor)
            return

        _LOGGER.error(
            'Please specify which motor to control "T" (top) or "B" (bottom)'
        )
        return

    def Set_angle(self, angle, motor: str = "B"):
        """
        Set the angle/rotation of the blind.

        angle is in degrees, so 0-180
        """
        target_angle = round(angle * self._max_angle / 180.0, 0)

        if motor == "B":
            data = {"targetAngle_B": target_angle}
        elif motor == "T":
            data = {"targetAngle_T": target_angle}
        elif motor == "C":
            data = {"targetAngle_B": target_angle, "targetAngle_T": target_angle}
        else:
            _LOGGER.error(
                'Please specify which motor to control "T" (top), "B" (bottom) or "C" (combined)'
            )
            return

        response = self._write(data)

        self._parse_response(response)

    def Jog_up(self, motor: str = "B"):
        """Open the blind/move the blind one step up."""
        if motor == "B":
            data = {"operation_B": 7}
        elif motor == "T":
            data = {"operation_T": 7}
        elif motor == "C":
            data = {"operation_B": 7, "operation_T": 7}
        else:
            _LOGGER.error(
                'Please specify which motor to control "T" (top), "B" (bottom) or "C" (combined)'
            )
            return

        response = self._write(data)

        self._parse_response(response)

    def Jog_down(self, motor: str = "B"):
        """Close the blind/move the blind one step down."""
        if motor == "B":
            data = {"operation_B": 8}
        elif motor == "T":
            data = {"operation_T": 8}
        elif motor == "C":
            data = {"operation_B": 8, "operation_T": 8}
        else:
            _LOGGER.error(
                'Please specify which motor to control "T" (top), "B" (bottom) or "C" (combined)'
            )
            return

        response = self._write(data)

        self._parse_response(response)

    @property
    def scaled_position(self):
        """
        Return the current scaled position of the blind in % (0-100).

        For the Top this is the position from the top to the bottom blind
        For the Bottom this is the postion from the top blind to the bottom
        """
        if self._position["B"] > 0:
            pos_top = round(self._position["T"] * 100.0 / self._position["B"], 1)
        else:
            pos_top = 0

        if self._position["T"] < 100:
            pos_bottom = round(
                (self._position["B"] - self._position["T"])* 100.0 / (100.0 - self._position["T"]),
                1,
            )
        else:
            pos_bottom = 100

        if self.width < 100:
            pos_combined = round(
                (self._position["C"] - self.width / 2.0) * 100.0 / (100.0 - self.width),
                1,
            )
        else:
            pos_combined = 100

        return {"T": pos_top, "B": pos_bottom, "C": pos_combined}

    @property
    def width(self):
        """Return the current width of the closed surface in % (0-100)."""
        return self._position["B"] - self._position["T"]

    @property
    def status(self):
        """Return the current status of the blind from BlindStatus enum."""
        if self._status is not None:
            return {"T": self._status["T"].name, "B": self._status["B"].name}

        return self._status

    @property
    def limit_status(self):
        """Return the current status of the limit detection of the blind from LimitStatus enum."""
        if self._limit_status is not None:
            return {
                "T": self._limit_status["T"].name,
                "B": self._limit_status["B"].name,
            }

        return self._limit_status
