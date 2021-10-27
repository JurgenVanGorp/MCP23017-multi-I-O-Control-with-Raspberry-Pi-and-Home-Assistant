# DRAFT - DO NOT USE YET

# MCP23017-multi-I-O-Control-with-Raspberry-Pi-and-Home-Assistant

# Home-assistant - I2C communication with an MCP23017

ASSUMPTIONS
* You are using a Raspberry Pi
* You have Home Assistant installed NATIVE (i.e. not with a Docker Image)
  * Why? because the software shown here communicates directly with the I2C bus
  * Home Assistant has an MCP23017 library built in, but it misses communication every now and then, which has resulted in a _really_ instable house in my case.
* You are using an MCP23017 I/O IC connected to the Raspberry Pi I2C bus.
  * See my other entries for hardware examples of the I2C
* You know where to find the Home Assistant directory on your Raspberry Pi (e.g. /home/home-assistant/.home-assistant) 


Home Assistant setup


