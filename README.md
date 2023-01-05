# motion-blinds
Python library for interfacing with Motion Blinds

This library allows you to control Motion Blinds from Coulisse B.V.
This library is primarly writen to be used with HomeAssistant but can also be used stand alone.

[![](https://img.shields.io/static/v1?label=Sponsor&message=%E2%9D%A4&logo=GitHub&color=%23fe8e86)](https://github.com/sponsors/starkillerOG)

For products see https://motion-blinds.com or https://coulisse.com/products/motion.

Shops that sell these blinds:
- [Hornbach](https://www.hornbach.nl/)
- [Smart Blinds](https://www.smartblinds.nl/)

## Other brands of blinds
This python library is primarly written for the Motion Blinds, but some other manufacturers use the same API and therefore this library also works with those brands.
The following brands have been reported to also work with this python library:
- [Motion Blinds](https://motionblinds.com/)
- [Smart Blinds](https://www.smartblinds.nl/)
- [Dooya](http://www.dooya.com/)
- [Brel Home](https://www.brel-home.nl/)
- [Bloc Blinds](https://www.blocblinds.com/)
- [AMP Motorization](https://www.ampmotorization.com/)
- [Bliss Automation - Alta Window Fashions](https://www.altawindowfashions.com/product/automation/bliss-automation/)
- [3 Day Blinds](https://www.3dayblinds.com/)
- [Diaz](https://www.diaz.be/en/)
- [Gaviota](https://www.gaviotagroup.com/en/)
- [Havana Shade](https://havanashade.com/)
- [Hurrican Shutters Wholesale](https://www.hurricaneshutterswholesale.com/)
- [Inspired Shades](https://www.inspired-shades.com/)
- [iSmartWindow](https://www.ismartwindow.co.nz/)
- [Martec](https://www.martec.co.nz/)
- [Raven Rock MFG](https://www.ravenrockmfg.com/)
- [ScreenAway](https://www.screenaway.com.au/)
- [Smart Home](https://www.smart-home.hu)
- [Uprise Smart Shades](http://uprisesmartshades.com)

## Installation

Use pip:

```$ pip install motionblinds```

or 

```$ pip install --use-wheel motionblinds```
  
## Retrieving Key
The Motion Blinds API uses a 16 character key that can be retrieved from the official "Motion Blinds" app for [Ios](https://apps.apple.com/us/app/motion-blinds/id1437234324) or [Android](https://play.google.com/store/apps/details?id=com.coulisse.motion).
Open the app, click the 3 dots in the top right corner, go to "settings", go to "Motion APP About", Please quickly tap this "Motion APP About" page 5 times, a popup will apear that gives you the key.

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
Note that multicast pushes from the gateway can be processed to retrieve instant status updates (see Multicast pushes section)
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
<MotionGateway ip: 192.168.1.100, mac: abcdefghujkl, protocol: 0.9, N_devices: 1, status: Working, RSSI: -71 dBm>
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

## Multicast pushes
This library allows to listen for multicast pushes from the gateway (in a parallel thread or using asyncio) and process these pushes to get instant updates of the gateway and connected blinds status.
To use this parallel pushes processing a MotionMulticast/AsyncMotionMulticast class object needs to be initilized.
The MotionMulticast.Start_listen()/AsyncMotionMulticast.Start_listen() and MotionMulticast.Stop_listen()/AsyncMotionMulticast.Stop_listen() can then be used to start and stop the parallel thread that is listening for incoming pushes.
The MotionMulticast/AsyncMotionMulticast class object can be supplied to the MotionGateway class to let it update that gateway and its connected blinds.
Externall callbacks can be registered for both gateway devices and blind devices (see tables below)
If UDP multicast messages are not coming through, try using the IP adress of the host running the code as the interface instead of "any".
### Parallel thread
An example code to listen for pushes for 30 seconds and print out gateway or blind information when a push comes in (when a blind finishes moving) using a parallel thread:
```
import time
from motionblinds import MotionMulticast, MotionGateway

def callback_func_gateway():
    print(m)

def callback_func_blind():
    for blind in m.device_list.values():
        print(blind)

motion_multicast = MotionMulticast(interface = "any")
motion_multicast.Start_listen()

m = MotionGateway(ip="192.168.1.100", key="12ab345c-d67e-8f", multicast = motion_multicast)
m.GetDeviceList()
m.Update()

m.Register_callback("1", callback_func_gateway)
for blind in m.device_list.values():
    blind.Register_callback("1", callback_func_blind)

time.sleep(30)

motion_multicast.Stop_listen()
```
### Asyncio
An example code to listen for pushes for 30 seconds and print out gateway or blind information when a push comes in (when a blind finishes moving) using asyncio:
```
import asyncio
from motionblinds import AsyncMotionMulticast, MotionGateway

async def asyncio_demo(loop):
    def callback_func_gateway():
        print(m)

    def callback_func_blind():
        for blind in m.device_list.values():
            print(blind)

    motion_multicast = AsyncMotionMulticast(interface = "any")
    await motion_multicast.Start_listen()

    m = MotionGateway(ip="192.168.1.100", key="12ab345c-d67e-8f", multicast = motion_multicast)
    await loop.run_in_executor(None, m.GetDeviceList)
    await loop.run_in_executor(None, m.Update)

    m.Register_callback("1", callback_func_gateway)
    for blind in m.device_list.values():
        blind.Register_callback("1", callback_func_blind)

    await asyncio.sleep(30)

    motion_multicast.Stop_listen()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio_demo(loop))
```

## Discovery
Motion Gateways can be discovered on your network using the MotionDiscovery class.
The following example will try to discover gateways for 10 seconds and then print a dict containg the gateways and their connected blinds that were discovered.

```
>>> from motionblinds import MotionDiscovery
>>> d = MotionDiscovery()
>>> motion_gateways = d.discover()
>>> print(motion_gateways)

{'192.168.1.100': {
    'msgType': 'GetDeviceListAck',
    'mac': 'abcdefghujkl',
    'deviceType': '02000002',
    'ProtocolVersion': '0.9',
    'token': '12345A678B9CDEFG',
    'data': [
        {'mac': 'abcdefghujkl',     'deviceType': '02000002'},
        {'mac': 'abcdefghujkl0001', 'deviceType': '10000000'},
        {'mac': 'abcdefghujkl0002', 'deviceType': '10000000'}
    ]
}}
```

## Gateway device
A gateway device (that was asigned to variable 'm') has the following methods and properties:

| method                          | arguments    | argument type    | explanation                                                                        |
| ------------------------------- | ------------ | ---------------- | ---------------------------------------------------------------------------------- |
| "m.GetDeviceList()"             | -            | -                | Get the device list from the Motion Gateway and update the properties listed below |
| "m.Update()"                    | -            | -                | Get the status of the Motion Gateway and update the properties listed below        |
| "m.Check_gateway_multicast()"   | -            | -                | Check if multicast messages can be received with the configured multicast listener |
| "m.Register_callback("1", func) | id, callback | string, function | Register a external callback function for updates of the gateway                   |
| "m.Remove_callback("1")         | id           | string           | Remove a external callback using its id                                            |
| "m.Clear_callbacks()            | -            | -                | Remove all external registered callbacks for updates of the gateway                |

| property         | value type | explanation                                                                                                            |
| ---------------- | ---------- | ---------------------------------------------------------------------------------------------------------------------- |
| "m.available"    | boolean    | Return if the gateway is available                                                                                     |
| "m.status"       | string     | Return gateway status: from GatewayStatus enum                                                                         |
| "m.N_devices"    | int        | Return the number of connected child devices                                                                           |
| "m.RSSI"         | int        | Return the Wi-Fi connection strength of the gateway in dBm                                                             |
| "m.token"        | string     | Return the Token                                                                                                       |
| "m.access_token" | string     | Return the AccessToken                                                                                                 |
| "m.mac"          | string     | Return the mac address of the gateway                                                                                  |
| "m.device_type"  | string     | Return the device type of the gateway                                                                                  |
| "m.protocol"     | string     | Return the protocol version of the gateway                                                                             |
| "m.firmware"     | string     | Return the firmware version of the gateway                                                                             |
| "m.device_list"  | dict       | Return a dict containing all blinds connected to the gateway, The keys in the dict are the mac adresses of the blinds. |

## Blind device
A blind device (that was asigned to variable 'blind_1') has the following methods and properties, arguments between () are optional:

| method                                | arguments                         | argument type                     | explanation                                                                                                                                              |
| ------------------------------------- | --------------------------------- | --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| "blind_1.Update_from_cache()"         | -                                 | -                                 | Get the status of the blind from the cache of the Motion Gateway, No 433MHz radio communication with the blind takes place                               |
| "blind_1.Update_trigger()"            | -                                 | -                                 | Get the status of the blind from the cache of the Motion Gateway and request a 433MHz radio communication with the blind for a new status (not awaited)  |
| "blind_1.Update()"                    | -                                 | -                                 | Get the status of the blind from the blind through the Motion Gateway (WiFi) using 433MHz radio communication between the gateway and the blind          |
| "blind_1.Stop()"                      | -                                 | -                                 | Stop the motion of the blind                                                                                                                             |
| "blind_1.Open()"                      | -                                 | -                                 | Open the blind/move the blind up                                                                                                                         |
| "blind_1.Close()"                     | -                                 | -                                 | Close the blind/move the blind down                                                                                                                      |
| "blind_1.Set_position(50)"            | postion, (angle), (restore_angle) | int (0-100), int (0-180), boolean | Set the position of the blind, optionaly set angle or restore current angle                                                                              |
| "blind_1.Set_angle(90)"               | angle                             | int (0-180)                       | Set the angle/rotation of the blind                                                                                                                      |
| "blind_1.Jog_up()"                    | -                                 | -                                 | Open the blind/move the blind one step up                                                                                                                |
| "blind_1.Jog_down()"                  | -                                 | -                                 | Close the blind/move the blind one step down                                                                                                             |  
| "blind_1.Register_callback("1", func) | id, callback                      | string, function                  | Register a external callback function for updates of the blind                                                                                           |
| "blind_1.Remove_callback("1")         | id                                | string                            | Remove a external callback using its id                                                                                                                  |
| "blind_1.Clear_callbacks()            | -                                 | -                                 | Remove all external registered callbacks for updates of the blind                                                                                        |

| property                  | value type | explanation                                                                         |
| ------------------------- | ---------- | ----------------------------------------------------------------------------------- |
| "blind_1.device_type"     | string     | Return the device type which is a 8 character number                                |
| "blind_1.blind_type"      | string     | Return the type of the blind from BlindType enum                                    |
| "blind_1.type"            | enum       | Return the type of the blind as a BlindType enum                                    |
| "blind_1.mac"             | string     | Return the mac address of the blind                                                 |
| "blind_1.available"       | boolean    | Return if the blind is available                                                    |
| "blind_1.status"          | string     | Return the current status of the blind from BlindStatus enum                        |
| "blind_1.limit_status"    | string     | Return the current status of the limit detection of the blind from LimitStatus enum |
| "blind_1.position"        | int        | Return the current position of the blind in % (0-100)                               |
| "blind_1.angle"           | int        | Return the current angle of the blind 0-180                                         |
| "blind_1.battery_voltage" | double     | Return the current battery voltage of the blind in V                                |
| "blind_1.battery_level"   | double     | Return the current battery level of the blind in %                                  |
| "blind_1.is_charging"     | boolean    | Return if the blind is currently charging its battery                               |
| "blind_1.RSSI"            | int        | Return the radio connection strength of the blind to the gateway in dBm             |
| "blind_1.wireless_mode"   | enum       | Return the wireless mode of the blind as a WirelessMode enum                        |
| "blind_1.wireless_name"   | string     | Return the wireless mode of the blind from WirelessMode enum                        |
| "blind_1.voltage_mode"    | enum       | Return the voltage mode of the blind as a VoltageMode enum                          |
| "blind_1.voltage_name"    | string     | Return the voltage mode of the blind from VoltageMode enum                          |

## Top Down Bottom Up (TDBU) device
A TDBU blind device has two motors designated by "T" = Top and "B" = Bottom to control the two parts of the blind.
Both parts can be controlled together using "C" = Combined as the motor.
The TDBU device (that was asigned to variable 'blind_1') has the following methods and properties:

| method                                              | arguments              | argument type                             | explanation                                                                             |
| --------------------------------------------------- | ---------------------- | ----------------------------------------- | --------------------------------------------------------------------------------------- |
| "blind_1.Update()"                                  | -                      | -                                         | Get the status of the blind from the Motion Gateway                                     |
| "blind_1.Stop(motor = 'B')"                         | motor                  | 'B', 'T' or 'C'                           | Stop the motion of Bottom or Top motor of the blind                                     |
| "blind_1.Open(motor = 'B')"                         | motor                  | 'B', 'T' or 'C'                           | Move the Bottom or Top motor of the blind up                                            |
| "blind_1.Close(motor = 'B')"                        | motor                  | 'B', 'T' or 'C'                           | Move the Bottom or Top motor of the blind down                                          |
| "blind_1.Set_position(50, motor = 'B', width = 20)" | position, motor, width | int (0-100), 'B', 'T' or 'C', int (0-100) | Set the position of the Bottom or Top motor of the blind, optionaly specify width       |
| "blind_1.Set_scaled_position(50, motor = 'B')"      | position, motor        | int (0-100), 'B', 'T' or 'C'              | Set the position of the motor of the blind within the alowed space in which it can move |
| "blind_1.Set_angle(90, motor = 'B')"                | angle, motor           | int (0-180), 'B', 'T' or 'C'              | Set the angle/rotation of the Bottom or Top motor of the blind                          |
| "blind_1.Jog_up(motor = 'B')"                       | motor                  | 'B', 'T' or 'C'                           | Move the Bottom or Top motor of the blind one step up                                   |
| "blind_1.Jog_down(motor = 'B')"                     | motor                  | 'B', 'T' or 'C'                           | Move the Bottom or Top motor of the blind one step down                                 | 
| "blind_1.Register_callback("1", func)               | id, callback           | string, function                          | Register a external callback function for updates of the blind                          |
| "blind_1.Remove_callback("1")                       | id                     | string                                    | Remove a external callback using its id                                                 |
| "blind_1.Clear_callbacks()                          | -                      | -                                         | Remove all external registered callbacks for updates of the blind                       |

| property                  | value type                              | explanation                                                                                             |
| ------------------------- | --------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| "blind_1.device_type"     | string                                  | Return the device type which is a 8 character number                                                    |
| "blind_1.blind_type"      | string                                  | Return the type of the blind from BlindType enum                                                        |
| "blind_1.type"            | enum                                    | Return the type of the blind as a BlindType enum                                                        |
| "blind_1.mac"             | string                                  | Return the mac address of the blind                                                                     |
| "blind_1.available"       | boolean                                 | Return if the blind is available                                                                        |
| "blind_1.status"          | {"T": string, "B": string}              | Return the current status of the blind from BlindStatus enum                                            |
| "blind_1.limit_status"    | {"T": string, "B": string}              | Return the current status of the limit detection of the blind from LimitStatus enum                     |
| "blind_1.position"        | {"T": int, "B": int, "C": double}       | Return the current position of the blind in % (0-100)                                                   |
| "blind_1.scaled_position" | {"T": double, "B": double, "C": double} | Return the current position of the blind, scaled to the alowed space in which it can move, in % (0-100) |
| "blind_1.width"           | int                                     | Return the area that is covered by the blind in % (0-100)                                               |
| "blind_1.angle"           | {"T": int, "B": int}                    | Return the current angle of the blind 0-180                                                             |
| "blind_1.battery_voltage" | {"T": double, "B": double}              | Return the current battery voltage of the blind in V                                                    |
| "blind_1.battery_level"   | {"T": double, "B": double}              | Return the current battery level of the blind in %                                                      |
| "blind_1.is_charging"     | boolean                                 | Return if the blind is currently charging its battery                                                   |
| "blind_1.RSSI"            | int                                     | Return the radio connection strength of the blind to the gateway in dBm                                 |
| "blind_1.wireless_mode"   | enum                                    | Return the wireless mode of the blind as a WirelessMode enum                                            |
| "blind_1.wireless_name"   | string                                  | Return the wireless mode of the blind from WirelessMode enum                                            |
| "blind_1.voltage_mode"    | enum                                    | Return the voltage mode of the blind as a VoltageMode enum                                              |
| "blind_1.voltage_name"    | string                                  | Return the voltage mode of the blind from VoltageMode enum                                              |
