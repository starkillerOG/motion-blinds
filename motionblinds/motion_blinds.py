"""
This module implements the interface to Motion Blinds.

:copyright: (c) 2020 starkillerOG.
:license: MIT, see LICENSE for more details.
"""


import logging
import socket
import json
import datetime
from enum import IntEnum
from Cryptodome.Cipher import AES

_LOGGER = logging.getLogger(__name__)

UDP_PORT_SEND = 32100
DEVICE_TYPE_BLIND = "10000000"
DEVICE_TYPE_GATEWAY = "02000002"


class GatewayStatus(IntEnum):
    """Status of the gateway."""

    Working = 1
    Pairing = 2
    Updating = 3


class BlindType(IntEnum):
    """Blind type matching of the blind using the values provided by the motion-gateway."""

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


class BlindStatus(IntEnum):
    """Status of the blind."""

    Closing = 0
    Opening = 1
    Stopped = 2
    StatusQuery = 5


class LimitStatus(IntEnum):
    """Limit status of the blind."""

    NoLimit = 0
    TopLimit = 1
    BottomLimit = 2
    Limits = 3
    Limit3 = 4


class MotionGateway:
    """Main class representing the Motion Gateway."""

    def __init__(
        self,
        ip: str = None,
        key: str = None,
    ):
        self._ip = ip
        self._key = key
        self._token = None
        
        self._access_token = None
        self._gateway_mac = None
        self._timeout = 5.0

        self._device_list = {}
        self._device_type = None
        self._status = None
        self._N_devices = None
        self._RSSI = None
        self._protecol_version = None
        
        
    def __repr__(self):
        return "<MotionGateway ip: %s, mac: %s, protecol: %s, N_devices: %s, status: %s, RSSI: %s dBm>" % (
            self._ip,
            self.mac,
            self.protecol,
            self.N_devices,
            self.status,
            self.RSSI,
        )

    def _get_access_token(self):
        """Calculate the AccessToken from the Key and Token."""
        if self._token is None:
            _LOGGER.error("Token not yet retrieved, use GetDeviceList to obtain it before using _get_access_token.")
            return None
        if self._key is None:
            _LOGGER.error("Key not specified, specify a key when creating the gateway class like MotionGateway(ip = '192.168.1.100', key = 'abcd1234-56ef-78') when using _get_access_token.")
            return None
        
        token_bytes = bytes(self._token, 'utf-8')
        key_bytes = bytes(self._key, 'utf-8')

        cipher = AES.new(key_bytes, AES.MODE_ECB)
        encrypted_bytes = cipher.encrypt(token_bytes)
        self._access_token = encrypted_bytes.hex().upper()
        
        return self._access_token

    def _get_timestamp(self):
        """Get the current time and format according to required Message-ID (Timestamp)."""
        time = datetime.datetime.utcnow()
        time_str = time.strftime("%Y%d%m%H%M%S%f")[:-3]
        
        return time_str

    def _send(self, message):
        """Send a command to the Motion Gateway."""

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(self._timeout)

        s.sendto(bytes(json.dumps(message), 'utf-8'), (self._ip, UDP_PORT_SEND))

        data, addr = s.recvfrom(1024)
        
        response = json.loads(data)
        
        if response.get("actionResult") is not None:
            _LOGGER.error("Received actionResult: '%s', when sending message: '%s'",
                response.get("actionResult"),
                message
            )
        
        return response

    def _read_subdevice(self, mac, device_type):
        """Read the status of a subdevice."""
        msg = {"msgType": "ReadDevice", "mac": mac, "deviceType": device_type, "msgID": self._get_timestamp()}

        return self._send(msg)

    def _write_subdevice(self, mac, device_type, data):
        """Write a command to a subdevice."""
        msg = {"msgType": "WriteDevice", "mac": mac, "deviceType": device_type, "AccessToken": self.access_token, "msgID": self._get_timestamp(), "data": data}

        return self._send(msg)

    def GetDeviceList(self):
        """Get the device list from the Motion Gateway."""
        msg = {"msgType":"GetDeviceList", "msgID":self._get_timestamp()}

        response = self._send(msg)
        
        # check msgType
        msgType = response.get("msgType")
        if msgType != "GetDeviceListAck":
            _LOGGER.error(
                "Response to GetDeviceList is not a GetDeviceListAck but '%s'.",
                msgType,
            )
            return
        
        # check device_type
        device_type = response.get("deviceType")
        if device_type != DEVICE_TYPE_GATEWAY:
            _LOGGER.warning(
                "DeviceType %s does not correspond to a gateway in GetDeviceList function.",
                device_type,
            )
        
        # update variables
        self._gateway_mac = response["mac"]
        self._device_type = device_type
        self._protecol_version = response["ProtocolVersion"]
        self._token = response["token"]
        
        # calculate the acces token
        self._get_access_token()
        
        # add the discovered blinds to the device list.
        for blind in response["data"]:
            blind_type = blind["deviceType"]
            if blind_type != DEVICE_TYPE_GATEWAY:
                if blind_type != DEVICE_TYPE_BLIND:
                    _LOGGER.warning(
                        "DeviceType %s does not correspond to a gateway or a blind.",
                        blind_type,
                    )
                blind_mac = blind["mac"]
                self._device_list[blind_mac] = MotionBlind(gateway = self, mac = blind_mac, device_type = blind_type)
        
        return self._device_list

    def Update(self):
        """Get the status of the Motion Gateway."""
        msg = {"msgType":"ReadDevice", "mac": self.mac, "deviceType": self.device_type, "msgID":self._get_timestamp()}

        response = self._send(msg)
        
        # check msgType
        msgType = response.get("msgType")
        if msgType != "ReadDeviceAck":
            _LOGGER.error(
                "Response to Update is not a ReadDeviceAck but '%s'.",
                msgType,
            )
            return
        
        # check device_type
        device_type = response.get("deviceType")
        if device_type != DEVICE_TYPE_GATEWAY:
            _LOGGER.warning(
                "DeviceType %s does not correspond to a gateway in Update function.",
                device_type,
            )
        
        # update variables
        self._gateway_mac = response["mac"]
        self._device_type = device_type
        self._status = GatewayStatus(response["data"]["currentState"])
        self._N_devices = response["data"]["numberOfDevices"]
        self._RSSI = response["data"]["RSSI"]

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
                _LOGGER.error("Token not yet retrieved, use GetDeviceList to obtain it before using the access_token.")
                return None
            if self._key is None:
                _LOGGER.error("Key not specified, specify a key when creating the gateway class like MotionGateway(ip = '192.168.1.100', key = 'abcd1234-56ef-78') when using the access_token.")
                return None
            # calculate the acces token
            self._get_access_token()
        
        return self._access_token

    @property
    def mac(self):
        """Return the mac address of the gateway."""
        if self._gateway_mac is None:
            _LOGGER.error("gateway mac not yet retrieved, use GetDeviceList to obtain it before using the mac.")
            return None
        
        return self._gateway_mac

    @property
    def device_type(self):
        """Return the device type of the gateway."""
        if self._device_type is None:
            _LOGGER.error("gateway device_type not yet retrieved, use GetDeviceList to obtain it before using the device_type.")
            return None

        return self._device_type

    @property
    def protecol(self):
        """Return the protecol version of the gateway."""
        return self._protecol_version

    @property
    def device_list(self):
        """
        Return a dict containing all blinds connected to the gateway.
        
        The keys in the dict are the mac adresses of the blinds.
        """
        return self._device_list

class MotionBlind:
    """Sub class representing a blind connected to the Motion Gateway."""
    def __init__(
        self,
        gateway: MotionGateway = None,
        mac: str = None,
        device_type: str = None,
    ):
        self._gateway = gateway
        self._mac = mac
        self._device_type = device_type
        self._blind_type = None
        
        self._status = None
        self._limit_status = None
        self._position = None
        self._angle = None
        self._battery_level = None
        self._RSSI = None

    def __repr__(self):
        return "<MotionBlind mac: %s, type: %s, status: %s, position: %s %%, angle: %s, limit: %s, battery: %s, RSSI: %s dBm>" % (
            self.mac,
            self.blind_type,
            self.status,
            self.position,
            self.angle,
            self.limit_status,
            self.battery_level,
            self.RSSI,
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

    def _parse_response(self, response):
        """Parse a response form the blind."""

        # check device_type
        device_type = response.get("deviceType")
        if device_type != DEVICE_TYPE_BLIND:
            _LOGGER.warning(
                "DeviceType %s does not correspond to a blind in Update function.",
                device_type,
            )
        
        # update variables
        self._mac = response["mac"]
        self._device_type = response["deviceType"]
        self._blind_type = BlindType(response["data"]["type"])
        self._status = BlindStatus(response["data"]["operation"])
        self._limit_status = LimitStatus(response["data"]["currentState"])
        self._position = response["data"]["currentPosition"]
        self._angle = response["data"]["currentAngle"]
        self._battery_level = response["data"]["batteryLevel"]
        self._RSSI = response["data"]["RSSI"]

    def Update(self):
        """Get the status of the blind from the Motion Gateway."""
        response = self._gateway._read_subdevice(self.mac, self._device_type)
        # alternative: response = self._write({"operation": 5})
        
        # check msgType
        msgType = response.get("msgType")
        if msgType != "ReadDeviceAck":
            _LOGGER.error(
                "Response to Update is not a ReadDeviceAck but '%s'.",
                msgType,
            )
            return
        
        self._parse_response(response)

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

    def Set_position(self, position):
        """
        Set the position of the blind.
        
        position is in %, so 0-100
        0 = open
        100 = closed
        """
        data = {"targetPosition": position}

        response = self._write(data)
        
        self._parse_response(response)

    def Set_angle(self, angle):
        """
        Set the angle/rotation of the blind.
        
        angle is in degrees, so 0-180
        """
        data = {"targetAngle": angle}

        response = self._write(data)
        
        self._parse_response(response)

    @property
    def blind_type(self):
        """Return the type of the blind from BlindType enum."""
        if self._blind_type is not None:
            return self._blind_type.name

        return self._blind_type

    @property
    def mac(self):
        """Return the mac address of the blind."""
        return self._mac

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
    def battery_level(self):
        """Return the current battery level of the blind."""
        return self._battery_level

    @property
    def RSSI(self):
        """Return the radio connection strength of the blind to the gateway in dBm."""
        return self._RSSI

