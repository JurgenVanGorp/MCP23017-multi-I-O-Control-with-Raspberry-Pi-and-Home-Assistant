Guide creation date: 11-Nov-2021

# STEP 4: MCP23017 multi-I/O Control with Home-Assistant on a Raspberry Pi
This section will explain how to read and control the MCP23017 from within Home Assistant that is installed (native) on a Raspberry Pi.

Previous topic: [Step 3: Doing Multi I/O Control with the Raspberry Pi and an MCP23017.](https://github.com/JurgenVanGorp/Step4-MCP23017-multi-IO-control-on-a-Raspberry-Pi-with-I2C)

## INTRODUCTION

This guide will explain how to control an MCP23017 I/O chip from within a native installed Home Assistant (further also called HA).

Now, to be clear: Home Assistant already has a pretty fine working MCP23017 library built-in. You will find sufficient documentation on the internet on how to install Home Assistant with a docker image, and how to enable I2C on the Raspberry Pi (further also called RPi). With some effort, you will also find examples on how to use the built-in mcp23017 library.

So, why doing the programming overnew? There were several reasons.

### Reason 1: safety

I am using the MCP23017 with toggle relays (aka teleruptors), so where the teleruptor only needs to be activated briefly for switching between lights-on and lights-off states. 

My experience was that the built-in library, with docker, often 'hung' or missed an High/Low command. The result was that sometimes one, or many, telerupters were randomly powered continuously. I could then only release the power by rebooting the RPi.

Needless to say this was a potential fire hazard, so I wanted control outside HA for the critical MCP23017 ICs that drove the 240V relays.

### Reason 2: functionality

My Home Assistant controls my house independently. I.e. I can switch the lights and control the house independent of HA being online or not.

Home Assistant adds a much apreciated comfort layer (e.g. "All lights out") but at least I'm not dependent on HA for proper operation. A HA outage as a result of an upgrade or me messing around with the HA installation (again) does not bring the whole house down.

It also means that I can switch the lights without HA knowing about it. The built-in MCP23017 library could drive an MCP23017 pin, but then considered that state to be the "on" or "off" state of the light. I need two pins: one to measure the current state of the light (independent of who switched it on or off), and another MCP23017 pin to toggle the teleruptor. So, additional coding was needed to provide that functionality.

## ASSUMPTIONS

* You are using a Raspberry Pi with Home Assistant and controlling an MCP23017 Multi I/O chip. This guide was written with an RPi 3B+, but I trust it will also work with e.g. an RPi4.
* You have Home Assistant installed NATIVE (i.e. not with a Docker Image)
  * You can [follow e.g. this guide](https://github.com/JurgenVanGorp/Setting-up-a-Raspberry-Pi) to set up your RPi.
  * You [can follow this guide](https://github.com/JurgenVanGorp/Home-Assistant-on-Raspberry-Pi-Native) to set up Home-Assistant native (i.e. without a docker instance) on the RPi.
  * You [can follow this guide](https://github.com/JurgenVanGorp/MCP23017-multi-IO-control-on-a-Raspberry-Pi-with-I2C) to install _and test (!)_ the MCP23017 controller libraries that I will be using in this guide.
* Your Home Assistant is up and running on your Raspberry Pi, and you have completed the base configuration.
* You can connect to your Raspberry Pi with SSH. The below commands will guide will use both the command interface and the HA interface.

## Installing the client software within Home-Assistant

### Installing the software

Let's start with locating the home directory of your Home-Assistant installation. If you followed the guide in the previous steps, it should be in the /home/homeassistant/.homeassistant. Verify (with ls) if this is the case:

```
pi@HA:~ $ ls /home/homeassistant/.homeassistant
automations.yaml    deps                home-assistant_v2.db  secrets.yaml
blueprints          groups.yaml         scenes.yaml           tts
configuration.yaml  home-assistant.log  scripts.yaml
```

If you used a different location (or you are not sure), try locating the configuration.yaml file with:

```
sudo find / | grep configuration.yaml
```

which would e.g. result in the following output.

```
pi@HA:~ $ sudo find / | grep configuration.yaml
/home/homeassistant/.homeassistant/configuration.yaml
```

Additional home-made libraries should be placed in the HA "custom_components" directory. We will install a new type of (mcp23017) relay in that directory as follows. As stated earlier, this guide assumes [you installed HA with this guide](https://github.com/JurgenVanGorp/Home-Assistant-on-Raspberry-Pi-Native), so we will need to install under the Home-Assistant credentials.

```
sudo -u homeassistant -H -s

cd /home/homeassistant/.homeassistant
mkdir custom_components
cd custom_components
mkdir mcp23017relay
cd mcp23017relay
wget -L https://raw.githubusercontent.com/JurgenVanGorp/MCP23017-multi-I-O-Control-with-Raspberry-Pi-and-Home-Assistant/main/custom_components/mcp23017relay/__init__.py
wget -L https://raw.githubusercontent.com/JurgenVanGorp/MCP23017-multi-I-O-Control-with-Raspberry-Pi-and-Home-Assistant/main/custom_components/mcp23017relay/manifest.json
wget -L https://raw.githubusercontent.com/JurgenVanGorp/MCP23017-multi-I-O-Control-with-Raspberry-Pi-and-Home-Assistant/main/custom_components/mcp23017relay/switch.py

exit
sudo reboot
```

### A simple switch

At this stage the relay should be available in Home Assistant. 

Let's assume that you have [that looks like this simple example](https://www.raspberrypi-spy.co.uk/2013/07/how-to-use-a-mcp23017-i2c-port-expander-with-the-raspberry-pi-part-1/), i.e. the board is connected with address pins [000] (0x20 on the I2C bus). Pins GPA0, GPA1 and GPA2 are driving three LEDs, and GPA7 is connected to a small push button.

The following configuration will use pin GPA2 as a regular light, so let's edit the configuration.yaml file.

```
sudo nano /home/homeassistant/.homeassistant/configuration.yaml
```

Find the _switch:_ section and add the relay in that section. If the section doesn't exist, just add the line.

```python
switch:
  - platform: mcp23017relay
    friendly_name: LED Light
    name: LED_Light
    scan_interval: 1
    output_i2c_address: 0x20
    output_pin: 2
```

Type Ctrl-S to save the file and Ctrl-X to exit.

Log into the Home Assistant GUI. Click [Configuration] and then [Server Controls].

https://github.com/JurgenVanGorp/MCP23017-multi-I-O-Control-with-Raspberry-Pi-and-Home-Assistant/blob/main/HA_config_01.png

Click the [Restart] button. Click [OK] when HA asks you if you're sure. Restarting will take a minute.

https://github.com/JurgenVanGorp/MCP23017-multi-I-O-Control-with-Raspberry-Pi-and-Home-Assistant/blob/main/HA_config_02.png

When HA has restarted, click [Configuration] again, and then select [Entities] from the list.

https://github.com/JurgenVanGorp/MCP23017-multi-I-O-Control-with-Raspberry-Pi-and-Home-Assistant/blob/main/HA_config_03.png

The new LED Light should be visible in the list of Entities. 

https://github.com/JurgenVanGorp/MCP23017-multi-I-O-Control-with-Raspberry-Pi-and-Home-Assistant/blob/main/HA_config_04.png

If you installed Home-Assistant native, the "Overview" dashboard should already have picked up the new Switch. If you configured HA yourself, you will need to add the new switch in the lovelace dashboard as 'switch.led_light'.

https://github.com/JurgenVanGorp/MCP23017-multi-I-O-Control-with-Raspberry-Pi-and-Home-Assistant/blob/main/HA_config_05.png


### A Toggle Relay

In the previous example the input and output of the relay are the same. In this example the "sense" input is different from the "driver" output. I.e. GPA7 is used to sense the 'state' of the light, and GPA0 is used to toggle a teleruptor.

The configuration in configuration.yaml then needs to be set as follows. Remark that the input and output boards can also have different board_id addresses. You could e.g. have an MCP23017 board dedicated to inputs, and another board dedicated to toggle outputs. In this example both boards are the same.

```python
switch:
  - platform: mcp23017relay
    friendly_name: Toggle Relay 1
    name: Toggle_Relay_1
    scan_interval: 1
    input_i2c_address: 0x20
    input_pin: 7
    output_i2c_address: 0x20
    output_pin: 0
```

## Trouble-shooting with email notifications

If the 


```python
switch:
  - platform: mcp23017relay
    friendly_name: LED Light
    name: LED_Light
    scan_interval: 1
    #verbose_level: 3
    output_i2c_address: 0x20
    output_pin: 15
```


```
```




