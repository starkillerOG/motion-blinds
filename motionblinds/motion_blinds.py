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
UPD_PORT_RECEIVE = 32101
DEVICE_TYPE_BLIND = "10000000"
DEVICE_TYPE_GATEWAY = "02000002"


class BlindDeviceType(IntEnum):
    """Device type matching of the blind using the values provided by the motion-gateway."""

    RollerBlind = 1
    VenetianBlind = 2
    RomanBlind = 3
    HoneycombBlind = 4
    Shangri-LaBlind = 5
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
        token: str = None,
    ):
        self._ip = ip
        self._key = key
        self._token = token
        
        self._access_token = None
        self._gateway_mac = None
        self._timeout = 5.0

        self._device_list = {}
        self._device_type = None
        self._status = None
        self._N_devices = None
        self._RSSI = None
        self._protecol_version = None
        
        self._get_access_token()

    def __repr__(self):
        return "<MotionGateway ip: %s, mac: %s, protecol: %s, N_devices: %s, status: %s, RSSI: %s>" % (
            self._ip,
            self.mac,
            self.protecol,
            self.N_devices,
            self.status,
            self.RSSI,
        )

    def _get_access_token(self):
        """Calculate the AccessToken from the Key and Token."""
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

        print("sending command")

        s.sendto(json.dump(message), (self._ip, UDP_PORT_SEND))
        #s.sendto(bytes(message, 'utf-8'), (self._ip, UDP_PORT_SEND))

        print("trying to receive")

        data, addr = s.recvfrom(1024)

        print(data)
        print(addr)
        
        return data

    def _read_subdevice(self, mac, device_type):
        """Read the status of a subdevice."""
        msg = {"msgType": "ReadDevice", "mac": mac, "deviceType": device_type, "msgID": self._get_timestamp}

        return self._gateway._send(msg)

    def _write_subdevice(self, mac, device_type, data):
        """Write a command to a subdevice."""
        msg = {"msgType": "WriteDevice", "mac": mac, "deviceType": device_type, "AccessToken": self.access_token, "msgID": self._get_timestamp, "data": data}

        return self._gateway._send(msg)

    def GetDeviceList(self):
        """Get the device list from the Motion Gateway."""
        msg = {"msgType":"GetDeviceList", "msgID":self._get_timestamp}

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
                "DeviceType %s does not correspond to a gateway.",
                device_type,
            )
        
        # update variables
        self._gateway_mac = response["mac"]
        self._device_type = device_type
        self._protecol_version = response["ProtocolVersion"]
        self._token = response["token"]
        
        # add the discovered blinds to the device list.
        for blind in response["data"]:
            blind_type = blind["deviceType"]
            if blind_type != DEVICE_TYPE_GATEWAY:
                blind_mac = blind["mac"]
                self._device_list[blind_mac] = MotionBlind(gateway = self, mac = blind_mac, device_type = blind_type)
        
        return self._device_list

    def Update(self, mac):
        """Get the status of the Motion Gateway."""
        msg = {"msgType":"ReadDevice", "mac": self._gateway_mac, "deviceType": self._device_type, "msgID":self._get_timestamp}

        self._send(msg)

    @property
    def status(self):
        """Return gateway status: 'Working', 'Pairing' or 'Updating'."""
        return self._status

    @property
    def N_devices(self):
        """Return the number of connected child devices."""
        return self._N_devices

    @property
    def RSSI(self):
        """Return the Wi-Fi connection strength of the gateway."""
        return self._RSSI

    @property
    def token(self):
        """Return the Token."""
        return self._token

    @property
    def access_token(self):
        """Return the AccessToken."""
        return self._access_token

    @property
    def mac(self):
        """Return the mac address of the gateway."""
        return self._gateway_mac

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
        
        self._status = None
        self._limit_status = None
        self._position = None
        self._angle = None
        self._battery_level = None
        self._RSSI = None

    def __repr__(self):
        return "<MotionBlind mac: %s, type: %s, status: %s, position: %s, angle: %s, limit: %s, battery: %s, RSSI: %s>" % (
            self.mac,
            self.device_type,
            self.status,
            self.position,
            self.angle,
            self.limit_status,
            self.battery_level,
            self.RSSI,
        )

    def _write(self, data):
        """Write a command to control the blind."""
        return self._gateway._write_subdevice(self.mac, self._device_type, data)

    def Update(self):
        """Get the status of the blind from the Motion Gateway."""
        response = self._gateway._update_subdevice(self.mac, self._device_type)
        print(response)
        
        data = {"operation": 5}
        response2 = self._write(data)
        print(response2)

    def Stop(self):
        """Stop the motion of the blind."""
        data = {"operation": 2}

        response = self._write(data)
        print(response)

    def Open(self):
        """Open the blind/move the blind up."""
        data = {"operation": 1}

        response = self._write(data)
        print(response)

    def Close(self):
        """Close the blind/move the blind down."""
        data = {"operation": 0}

        response = self._write(data)
        print(response)

    def Set_position(self, position):
        """
        Set the position of the blind.
        
        position is in %, so 0-100
        0 = open
        100 = closed
        """
        data = {"targetPosition": position}

        response = self._write(data)
        print(response)

    def Set_angle(self, angle):
        """
        Set the angle/rotation of the blind.
        
        angle is in degrees, so 0-180
        """
        data = {"targetAngle": angle}

        response = self._write(data)
        print(response)

    @property
    def device_type(self):
        """Return the device type of the blind from BlindDeviceType enum."""
        return self._device_type.name

    @property
    def mac(self):
        """Return the mac address of the blind."""
        return self._mac

    @property
    def status(self):
        """Return the current status of the blind from BlindStatus enum."""
        return self._status.name

    @property
    def limit_status(self):
        """Return the current status of the limit detection of the blind from LimitStatus enum."""
        return self._limit_status.name

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
        """Return the current battery level of the blind in % (0-100)."""
        return self._battery_level

    @property
    def RSSI(self):
        """Return the radio connection strength of the blind to the gateway."""
        return self._RSSI

