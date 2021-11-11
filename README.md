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

Additional home-made libraries should be placed in the HA "custom_components" directory. We will install a new type of (mcp23017) relay in that directory as follows.

```
cd /home/homeassistant/.homeassistant
mkdir custom_components
cd custom_components
mkdir mcp23017relay
cd mcp23017relay

```




```
```




```
```




```
```




```
```




```
```




```
```




```
```




```
```




```
```




```
```




```
```




```
```




```
```




```
```




```
```




```
```




```
```




```
```




```
```




```
```




