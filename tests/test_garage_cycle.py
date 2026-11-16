"""Tests for the direct-WiFi garage gate impulse command."""

import socket

import pytest

from motionblinds import motion_blinds
from motionblinds.motion_blinds import (
    DEVICE_TYPE_WIFI_BLIND,
    DEVICE_TYPE_WIFI_GATE,
    MotionBlind,
    MotionGateway,
)


class FakeGateway:
    """Capture a local write and return an ACK without position data."""

    def __init__(self):
        self.writes = []

    def _write_subdevice(self, mac, device_type, data, max_attempts=3):
        self.writes.append((mac, device_type, data, max_attempts))
        return {
            "msgType": "WriteDeviceAck",
            "mac": mac,
            "deviceType": device_type,
        }

    def _read_subdevice(self, mac, device_type):
        raise socket.timeout


def test_cycle_sends_single_impulse_to_direct_wifi_garage_gate():
    """A missing status read must not make an acknowledged impulse look failed."""
    gateway = FakeGateway()
    gate = MotionBlind(gateway, "001122334455", DEVICE_TYPE_WIFI_GATE)

    gate.Cycle()

    assert gateway.writes == [
        ("001122334455", DEVICE_TYPE_WIFI_GATE, {"operation": 3}, 1)
    ]
    assert gate.status is None
    assert gate.position is None


def test_cycle_rejects_other_blind_types_without_sending_a_command():
    """An impulse intended for a garage gate must not move another blind."""
    gateway = FakeGateway()
    blind = MotionBlind(gateway, "001122334455", DEVICE_TYPE_WIFI_BLIND)

    with pytest.raises(ValueError, match="garage gate"):
        blind.Cycle()

    assert gateway.writes == []


def test_single_attempt_does_not_repeat_a_timed_out_impulse(monkeypatch):
    """A lost ACK must not lead to a second gate movement command."""
    sends = []

    class TimedOutSocket:
        def __init__(self, *args, **kwargs):
            pass

        def settimeout(self, timeout):
            pass

        def sendto(self, message, address):
            sends.append((message, address))

        def recvfrom(self, size):
            raise socket.timeout

        def close(self):
            pass

    monkeypatch.setattr(motion_blinds.socket, "socket", TimedOutSocket)
    gateway = MotionGateway(ip="192.0.2.1")

    with pytest.raises(socket.timeout):
        gateway._send({"msgType": "WriteDevice"}, max_attempts=1)

    assert len(sends) == 1
