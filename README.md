# motion-blinds
Python library for interfacing with Motion Blinds

This library allows you to control Motion Blinds from Coulisse B.V.
This library is primarly writen to be used with HomeAssistant but can also be used stand alone.

For products see https://motion-blinds.com or https://coulisse.com/products/motion.

Shops that sell these blinds:
- [Hornbach](https://www.hornbach.nl/)

## Installation

Use pip:

```$ pip install motionblinds```

or 

```$ pip install --use-wheel motionblinds```
  
## Retrieving Key
The Motion Blinds API uses a 16 character key that can be retrieved from the official "Motion Blinds" app for [Ios](https://apps.apple.com/us/app/motion-blinds/id1437234324) or [Android](https://play.google.com/store/apps/details?id=com.coulisse.motion).
Open the app, click the 3 dots in the top right corner, go to "settings", go to "Motion APP About", Please quickly tap this ‘Motion APP About’ page 5 times, a popup will apear that gives you the key.

![alt text](https://raw.githubusercontent.com/starkillerOG/motion-blinds/main/pictures/Motion_App__get_key_1.jpg)
![alt text](https://raw.githubusercontent.com/starkillerOG/motion-blinds/main/pictures/Motion_App__get_key_2.jpg)

Please note that "-" characters need to be included in the key when providing it to this library.
The key needs to be simular to "12ab345c-d67e-8f"

## Usage

For creation of a device you could use the following lines of codes (using a correct IP of the gateway and Key retrieved from the App)
```
from motionblinds import MotionGateway
m = MotionGateway(ip = "192.168.1.100", key = "12ab345c-d67e-8f")
```
This library is not polling. Thus you need to populate the connected blinds using the GetDeviceList method and update device information using the Update method.
```
m.GetDeviceList()
m.Update()
```
Note that GetDeviceList needs to be run before using Update since the device_type, mac and token are retrieved using the GetDeviceList method.
Once the connected blinds are discoverd using the GetDeviceList method, they can be listed by the device_list property:
```
m.device_list
```
This will return a dict with as key the mac_adress of the blind and as value a MotionBlind device that can be used to retreive information of that blind and control that blind.

Some example code that will print the information of the gateway and all conected blinds:
```
>>> from motionblinds import MotionGateway
>>> m = MotionGateway(ip = "192.168.1.100", key = "12ab345c-d67e-8f")
>>> m.GetDeviceList()
{'abcdefghujkl0001': <MotionBlind mac: abcdefghujkl0001, type: None, status: None, position: None %, angle: None, limit: None, battery: None, RSSI: None dBm>}
>>> m.Update()
>>> print(m)
<MotionGateway ip: 192.168.1.100, mac: abcdefghujkl, protecol: 0.9, N_devices: 1, status: Working, RSSI: -71 dBm>
>>> for blind in m.device_list.values():
>>>     blind.Update()
>>>     print(blind)
<MotionBlind mac: abcdefghujkl0001, type: RollerBlind, status: Stopped, position: 0 %, angle: 0, limit: Limits, battery: 1195, RSSI: -82 dBm>
```

To open a blind the following example code can be used:
```
>>> from motionblinds import MotionGateway
>>> m = MotionGateway(ip = "192.168.1.100", key = "12ab345c-d67e-8f")
>>> m.GetDeviceList()
>>> m.Update()
>>> blind_1 = list(m.device_list.values())[0]
>>> blind_1.Update()
>>> blind_1.Open()
```
Instead of blind_1.Open() you can also use blind_1.Close(), blind_1.Stop(), blind_1.Set_position(50) or blind_1.Set_angle(90)

## Gateway device
A gateway device (that was asigned to variable 'm') has the following methods and properties:

| method              | arguments | argument type | explanation                                                                        |
| ------------------- | --------- | ------------- | ---------------------------------------------------------------------------------- |
| "m.GetDeviceList()" | -         | -             | Get the device list from the Motion Gateway and update the properties listed below |
| "m.Update()"        | -         | -             | Get the status of the Motion Gateway and update the properties listed below        |

| property         | value type | explanation                                         |
| ---------------- | ---------- | --------------------------------------------------- |
| "m.status"       | string     | Return gateway status: from GatewayStatus enum      |
| "m.N_devices"    | int        | Return the number of connected child devices        |
| "m.RSSI"         | int        | Return the Wi-Fi connection strength of the gateway in dBm |
| "m.token"        | string     | Return the Token |
| "m.access_token" | string     | Return the AccessToken |
| "m.mac"          | string     | Return the mac address of the gateway |
| "m.device_type"  | string     | Return the device type of the gateway |
| "m.protecol"     | string     | Return the protecol version of the gateway |
| "m.device_list"  | dict       | Return a dict containing all blinds connected to the gateway, The keys in the dict are the mac adresses of the blinds. |

## Blind device
A blind device (that was asigned to variable 'blind_1') has the following methods and properties:

| method                     | arguments | argument type | explanation                                         |
| -------------------------- | --------- | ------------- | --------------------------------------------------- |
| "blind_1.Update()"         | -         | -             | Get the status of the blind from the Motion Gateway |
| "blind_1.Stop()"           | -         | -             | Stop the motion of the blind                        |
| "blind_1.Open()"           | -         | -             | Open the blind/move the blind up                    |
| "blind_1.Close()"          | -         | -             | Close the blind/move the blind down                 |
| "blind_1.Set_position(50)" | postion   | int (0-100)   | Set the position of the blind                       |
| "blind_1.Set_angle(90)"    | angle     | int (0-180)   | Set the angle/rotation of the blind                 |

| property                | value type | explanation                                                                         |
| ----------------------- | ---------- | ----------------------------------------------------------------------------------- |
| "blind_1.blind_type"    | string     | Return the type of the blind from BlindType enum                                    |
| "blind_1.mac"           | string     | Return the mac address of the blind                                                 |
| "blind_1.status"        | string     | Return the current status of the blind from BlindStatus enum                        |
| "blind_1.limit_status"  | string     | Return the current status of the limit detection of the blind from LimitStatus enum |
| "blind_1.position"      | int        | Return the current position of the blind in % (0-100)                               |
| "blind_1.angle"         | int        | Return the current angle of the blind 0-180                                         |
| "blind_1.battery_level" | int        | Return the current battery level of the blind                                       |
| "blind_1.RSSI"          | int        | Return the radio connection strength of the blind to the gateway in dBm             |
