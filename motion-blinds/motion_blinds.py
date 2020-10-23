"""
This module implements the interface to Motion Blinds.

:copyright: (c) 2020 starkillerOG.
:license: MIT, see LICENSE for more details.
"""


import logging
import socket
import json
import datetime
from Cryptodome.Cipher import AES

_LOGGER = logging.getLogger(__name__)

UDP_PORT = 32100
DEVICE_TYPE_BLIND = "10000000"
DEVICE_TYPE_GATEWAY = "02000002"


class MotionGateway:
    """Main class representing the Motion Gateway."""

    def __init__(
        self,
        ip: str = None,
        key: str = None,
        token: str = None,
        debug: int = 0,
    ):
        self._ip = ip
        self._key = key
        self._token = token
        self._debug = debug
        
        self._access_token = None
        self._gateway_mac = None
        self._timeout = 5.0

        self._device_list = {}
        
        self._get_access_token()

    def _get_access_token(self):
        """Calculate the AccessToken from the Key and Token."""
        token_bytes = bytes(self._token, 'utf-8')
        key_bytes = bytes(self._key, 'utf-8')

        cipher = AES.new(key_bytes, AES.MODE_ECB)
        encrypted_bytes = cipher.encrypt(token_bytes)
        self._access_token = encrypted_bytes.hex()
        
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

        s.sendto(json.dump(message), (self._ip, UDP_PORT))
        #s.sendto(bytes(message, 'utf-8'), (self._ip, UDP_PORT))

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

        self._send(msg)
        
        # add the discovered blinds to the device list.

    def Update(self, mac):
        """Get the status of the Motion Gateway."""
        msg = {"msgType":"ReadDevice", "mac": self._gateway_mac, "deviceType": DEVICE_TYPE_GATEWAY, "msgID":self._get_timestamp}

        self._send(msg)

    @property
    def access_token(self):
        """Return the AccessToken."""
        return self._access_token
        
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
        debug: int = 0,
    ):
        self._gateway = gateway
        self._mac = mac
        self._debug = debug
        self._device_type = device_type

    def _write(self, data):
        """Write a command to control the blind."""
        return self._gateway._write_subdevice(self._mac, self._device_type, data)

    def Update(self):
        """Get the status of the blind from the Motion Gateway."""
        response = self._gateway._update_subdevice(self._mac, self._device_type)
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
