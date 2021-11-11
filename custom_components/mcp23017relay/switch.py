"""
Switch based on e.g. a MCP23017 IC, connected to a Raspberry Pi board.
It is expected that a server part is running, through a Redis in-memory database. Commands are
sent to the Redis database, and responses captured. The server would then process the actions
in background.
Author: find me on codeproject.com --> JurgenVanGorp
"""
import smtplib
import time
import sys
import redis
from datetime import datetime
import logging
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

###
### USER EDITABLE CONSTANTS #####################################################################
###

# Email parameters are ONLY needed in case logging is configured in the switch, through the 
# CONF_VERBOSE_LEVEL parameter. I.e. this can be done on a per-device level. If no logging is
# set, the following parameters can be left empty. If logging is configured for debugging
# purposes (e.g. verbose_level = 3), emails will be sent on critical actions, allowing proper
# debugging. Do mind that the emails will significantly slow down the operation, so handle with care.
CONST_EMAIL_SENDER = "my_email_address@mydomain.com"
CONST_EMAIL_RECEIVER = "your_email_address@yourdomain.com"
CONST_EMAIL_SMTPSERVER = "uit.telenet.be"

# Communications between Clients and the server happen through a Redis in-memory database
# so to limit the number of writes on the (SSD or microSD) storage. For larger implementations
# dozens to hundreds of requests can happen per second. Writing to disk would slow down the 
# process, and may damage the storage.
# Make sure to have Redis installed in the proper locations, e.g. also in the virtual python
# environments. The default is that Redis is installed on localhost (127.0.0.1).
REDIS_HOST = 'localhost'
REDIS_PORT = 6379

# The COMMAND_TIMEOUT value is the maximum time (in seconds) that is allowed between pushing a  
# button and the action that must follow. This is done to protect you from delayed actions 
# whenever the I2C bus is heavily used, or the CPU is overloaded. If you e.g. push a button, 
# and the I2C is too busy with other commands, the push-button command is ignored when  
# COMMAND_TIMEOUT seconds have passed. Typically you would push the button again if nothing 
# happens after one or two seconds. If both commands are stored, the light is switched on and
# immediately switched off again.
# Recommended minimum value one or two seconds
# COMMAND_TIMEOUT = 2
# Recommended maximum value is 10 seconds. Feel free to set higher values, but be prepared that 
# you can can experience strange behaviour if there is a lot of latency on the bus.
COMMAND_TIMEOUT = 1

###
### PROGRAM INTERNAL CONSTANTS ####################################################################
###

DEFAULT_I2C_ADDRESS = 0x20

CONF_INPUT_I2C_ADDRESS = "input_i2c_address"
CONF_INPUT_PIN = "input_pin"
CONF_OUTPUT_I2C_ADDRESS = "output_i2c_address"
CONF_OUTPUT_PIN = "output_pin"
CONF_FRIENDLY_NAME = "friendly_name"
CONF_VERBOSE_LEVEL = "verbose_level"
CONF_RELAY_MODE = "relay_mode"
CONF_TIMER_DELAY = "timer_delay"

# Acceptable Commands for controlling the I2C bus
# These are the commands you need to use to control the DIR register of the MCP23017, or
# for setting and clearing pins.
IDENTIFY = "IDENTIFY"         # Polls an MCP23017 board on the I2C bus (True/False)
GETDIRBIT = "GETDBIT"         # Read the specific IO pin dir value (1 = input)
GETDIRREGISTER = "GETDIRREG"  # Read the full DIR register (low:1 or high:2)
SETDIRBIT = "SETDBIT"         # Set DIR pin to INPUT (1)
CLEARDIRBIT = "CLRDBIT"       # Clear DIR pin command to OUTPUT (0)
GETIOPIN = "GETPIN"           # Read the specific IO pin value
GETIOREGISTER = "GETIOREG"    # Read the full IO register (low:1 or high:2)
SETDATAPIN = "SETPIN"         # Set pin to High
CLEARDATAPIN = "CLRPIN"       # Set pin to low
TOGGLEPIN = "TOGGLE"          # Toggle a pin to the "other" value for TOGGLEDELAY time

# The dummy command is sent during initialization of the database and verification if
# the database can be written to. Dummy commands are not processed.
DUMMY_COMMAND = 'dummycommand'

### END OF CONSTANTS SECTION #########################################################

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_OUTPUT_I2C_ADDRESS): vol.All(int, vol.Range(min=0x03, max=0x77)),
        vol.Required(CONF_OUTPUT_PIN): vol.All(int, vol.Range(min=0, max=15)),
        vol.Optional(CONF_INPUT_I2C_ADDRESS, default=0xFF): vol.All(int, vol.Range(min=0x03, max=0xFF)),
        vol.Optional(CONF_INPUT_PIN, default=15): vol.All(int, vol.Range(min=0, max=15)),
        vol.Optional(CONF_NAME, default="MCP23017"): cv.string,
        vol.Optional(CONF_FRIENDLY_NAME, default="MCP23017"): cv.string,
        vol.Optional(CONF_VERBOSE_LEVEL, default=0): vol.All(int, vol.Range(min=0, max=3)),
        vol.Optional(CONF_TIMER_DELAY, default=2.0): vol.All(float, vol.Range(min=1.0, max=604800.0)),
        vol.Optional(CONF_RELAY_MODE, default="A"): vol.In(["A", "B", "C", "D", "E", "F"])
    }
)

def setup_platform(hass, config, add_devices, discovery_info=None):
    # Collect parameters from configuration.yaml
    name = config.get(CONF_NAME)
    friendlyname = config.get(CONF_FRIENDLY_NAME)
    input_i2c_address = config.get(CONF_INPUT_I2C_ADDRESS)
    input_pin_num = config.get(CONF_INPUT_PIN)
    output_i2c_address = config.get(CONF_OUTPUT_I2C_ADDRESS)
    output_pin_num = config.get(CONF_OUTPUT_PIN)
    verbosity = config.get(CONF_VERBOSE_LEVEL)
    timer_delay = config.get(CONF_TIMER_DELAY)
    relay_mode = config.get(CONF_RELAY_MODE)

    # Present device to hassio
    add_devices([MCP23017_Relay(input_i2c_address, input_pin_num, output_i2c_address, \
        output_pin_num, verbosity, timer_delay, relay_mode, friendlyname, name)])

class mcp23017client():
    """
    A class for starting an in-memory Redis database communication with the mcp23017server service.
    """
    def __init__(self):
        # Commands have id   datetime.now().strftime("%d-%b-%Y %H:%M:%S.%f")}, i.e. the primary key is a timestamp. 
        # Commands given at exactly the same time, will overwrite each other, but this is not expected to happen.
        # The commands table is then formatted as (all fields are TEXT, even if formatted as "0xff" !!)
        # id, command TEXT, boardnr TEXT DEFAULT '0x00', pinnr TEXT DEFAULT '0x00', datavalue TEXT DEFAULT '0x00'
        self._commands = None
        # Responses have id   datetime.now().strftime("%d-%b-%Y %H:%M:%S.%f")}, i.e. the primary key is a timestamp. 
        # The Responses table is then formatted as (all fields are TEXT, even if formatted as "0xff" !!)
        # id, command_id TEXT, datavalue TEXT, response TEXT
        self._responses = None

    def OpenAndVerifyDatabase(self):
        """
        Opens an existing database, or creates a new one if not yet existing. Then 
        verifies if the Redis database is accessible.
        """
        # First try to open the database itself.
        try:
            # Open the shared memory databases.
            # Redis database [0] is for commands that are sent from the clients to the server.
            nowTrying = "Commands"
            self._commands = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=0)
            # Redis database [1] is for responses from the server so the clients.
            nowTrying = "Responses"
            self._responses = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=1)
        except OSError as err:
            # Capturing OS error.
            return "FATAL OS ERROR. Could not open [{}] database. This program is now exiting with error [{}].".format(nowTrying, err)
        except:
            # Capturing all other errors.
            return "FATAL UNEXPECTED ERROR. Could not open [{}] database. This program is now exiting with error [{}].".format(nowTrying, sys.exc_info()[0])
        
        # Do a dummy write to the Commands database, as verification that the database is fully up and running.
        try:
            # Remember: fields are 
            #    id, command TEXT, boardnr TEXT DEFAULT '0x00', pinnr TEXT DEFAULT '0x00', datavalue TEXT DEFAULT '0x00'
            id =  (datetime.now() - datetime.utcfromtimestamp(0)).total_seconds()
            datamap = {'command':DUMMY_COMMAND, 'boardnr':0x00, 'pinnr':0xff, 'datavalue':0x00}
            # Write the info to the Redis database
            self._commands.hset(id, None, None, datamap)
            # Set expiration to 1 second, after which Redis will automatically delete the record
            self._commands.expire(id, 1)
        except:
            # Capturing all errors.
            return "FATAL UNEXPECTED ERROR. Could not read and/or write the [Commands] database. This program is now exiting with error [{}].".format(sys.exc_info()[0])

        # Next, do a dummy write to the Responses database, as verification that the database is fully up and running.
        try:
            # Remember: fields are 
            #    id, command_id TEXT, datavalue TEXT, response TEXT
            id =  (datetime.now() - datetime.utcfromtimestamp(0)).total_seconds()
            datamap = {'datavalue':0x00, 'response':'OK'}
            # Write the info to the Redis database
            self._responses.hset(id, None, None, datamap)
            # Set expiration to 1 second, after which Redis will automatically delete the record
            self._responses.expire(id, 1)
        except:
            # Capturing all errors.
            return "FATAL UNEXPECTED ERROR. Could not read and/or write the [Responses] database. This program is now exiting with error [{}].".format(sys.exc_info()[0])
        # We got here, so return zero error message.
        return ""

    def SendCommand(self, whichCommand, board_id, pin_id):
        """
        Send a new command to the mcp23017server through a Redis database record.
        The commands will get a time-out, to avoid that e.g. a button pushed now, is only processed hours later.
        Response times are expected to be in the order of (fractions of) seconds.
        """
        # Prepare new id based on timestamp. Since this is up to the milliseconds, the ID is expected to be unique
        id = (datetime.now() - datetime.utcfromtimestamp(0)).total_seconds()
        # Create data map
        mapping = {'command':whichCommand, 'boardnr':board_id, 'pinnr':pin_id}
        # Expiration in the Redis database can be set already. Use the software expiration with some grace period.
        # Expiration must be an rounded integer, or Redis will complain.
        expiration = round(COMMAND_TIMEOUT + 1)
        # Now send the command to the Redis in-memory database
        self._commands.hset(id, None, None, mapping)
        # Command must self-delete within the expiration period. Redis can take care.
        self._commands.expire(id, expiration)
        # The timestamp is also the id of the command (needed for listening to the response)
        return id

    def WaitForReturn(self, command_id):
        """
        Wait for a response to come back from the mcp23017server, once the command has been processed on the
        I2C bus. If the waiting is too long (> COMMAND_TIMEOUT), cancel the operation and return an error.
        """
        answer = None
        # If no timely answer, then cancel anyway. So, keep track of when we started.
        checking_time = datetime.now()
        while answer == None:
            # request the data from the Redis database, based on the Command ID.
            datafetch = self._responses.hgetall(command_id)
            # Verify if a response is available.
            if len(datafetch) > 0:
                # Do data verification, to cover for crippled data entries without crashing the software.
                try:
                    datavalue = datafetch[b'datavalue'].decode('ascii')
                except:
                    datavalue = 0x00

                try:
                    response = datafetch[b'response'].decode('ascii')
                except:
                    response = "Error Parsing mcp23017server data."

                answer = (datavalue, response)
            if (datetime.now() - checking_time).total_seconds()  > COMMAND_TIMEOUT:
                answer = (0x00, "Time-out error trying to get result from server for Command ID {}".format(command_id))
        return answer

    def ProcessCommand(self, whichCommand, board_id, pin_id):
        """
        The ProcessCommand function is a combination of sending the Command to the mcp23017server host, and 
        waiting for the respone back.
        """
        retval = -1
        # First send the command to the server
        command_id = self.SendCommand(whichCommand, board_id, pin_id)
        # Then wait for the response back
        response = self.WaitForReturn(command_id)
        # A good command will result in an "OK" to come back from the server.
        if response[1].strip().upper() == 'OK':
            # OK Received, now process the data value that was sent back.
            retval = response[0]
            if(isinstance(retval,str)):
                if len(retval) == 0:
                    retval = 0x00
                else:
                    try:
                        if 'x' in retval:
                            retval = int(retval, 16)
                        else:
                            retval = int(retval, 10)
                    except:
                        # wrong type of data received
                        retval = "Error when processing return value. Received value that I could not parse: [{}]".format(response[0])
        else:
            retval = "Error when processing pin '0x{:02X}' on board '0x{:02X}'. Error Received: {}".format(board_id, pin_id, response[1])
        return retval

class MCP23017_Relay(SwitchEntity):
    """
    Relay for MCP23017 GPIO
    """
    def __init__(self, i2c_in, pin_in, i2c_out, pin_out, verbosity, \
        timer_delay, relay_mode, friendlyname, name, invert_logic = False):
        self._name = name
        self._friendly_name = friendlyname
        self._verbose = verbosity
        self._invert_logic = invert_logic
        self._state = False
        self._relay_mode = relay_mode
        self._timer_delay = timer_delay
        self._datapipe = mcp23017client()

        # input and output chips
        self._i2c_in = i2c_in
        self._pin_in = pin_in
        self._i2c_out = i2c_out
        self._pin_out = pin_out

        # In case input is same as output, or if input is default 0xff, then chip is output only
        if (i2c_in==0xff) or ((i2c_in==i2c_out) and (pin_in == pin_out)):
            self._output_only = True
        else:
            self._output_only = False

        # Initiate data pipe to the Redis database server, and set the proper DIR bits (input vs. output)
        err_msg = self._datapipe.OpenAndVerifyDatabase()
        if err_msg == "":
            self.SetDirBits()
        else:
            if self._verbose > 0:
                self._SendStatusMessage("ERROR initializing: [{}]. ".format(err_msg))

        if self._verbose > 0:
            self._SendStatusMessage("\n\nCompleted Initialization.")

    @property
    def name(self):
        return self._friendly_name

    @property
    def is_on(self) -> bool:
        # The input must always be read from the I2C bus. Reason is that states can also be changed by 
        # human interaction, i.e. not controlled by the Home Assistant software.
        self._read_bus()
        return self._state

    def SetDirBits(self):
        """
        Set the MCP23017 DIR bits, which determine whether a pin is an input (High) or an output (Low).
        This software handles two possibilities:
           * PASSIVE OUTPUT - the output is determined by Home Assistant. If Home Assistant tells the output
             to be high, then it will stay high. This is for e.g. status lights.
           * INPUT-OUTPUT - the output is toggled (or set) by one MCP23017 pin, and the status of the light
             is read on another pin. This allows monitoring of the input (e.g. caused by human interaction) 
             and software changing the state through the output pin. 
        """
        # In case input is same as output, or if input is default 0xff, then chip is output only
        if self._output_only:
            msg_update = self._datapipe.ProcessCommand(CLEARDIRBIT, self._i2c_out, self._pin_out)
            if self._verbose > 1:
                self._SendStatusMessage("Info: Clearing DIR bit for OUTPUT ONLY: [{}] cleared on board [{}]. Update Message is: [{}]".format(self._pin_out, self._i2c_out, msg_update))
        else:
            msg_update = self._datapipe.ProcessCommand(CLEARDIRBIT, self._i2c_out, self._pin_out)
            if self._verbose > 1:
                self._SendStatusMessage("Info: Clearing DIR bit for OUTPUT: [{}] cleared on board [{}]. Update Message is: [{}]".format(self._pin_out, self._i2c_out, msg_update))
            msg_update = self._datapipe.ProcessCommand(SETDIRBIT, self._i2c_in, self._pin_in)
            if self._verbose > 1:
                self._SendStatusMessage("Info: Setting DIR bit for INPUT: [{}] set on board [{}]. Update Message is: [{}]".format(self._pin_in, self._i2c_in, msg_update))

    def turn_on(self):
        """
        Switches output on in case the IC is output only.
        In case of a toggle output: monitors input if it not switched on already, and toggles output if not.
        """
        self.SetDirBits()
        if self._output_only:
            msg_update = self._datapipe.ProcessCommand(SETDATAPIN, self._i2c_out, self._pin_out)
            if self._verbose > 1:
                self._SendStatusMessage("Turned pin [{}] on board [{}] ON. Update Message is: [{}]".format(self._pin_out, self._i2c_out, msg_update))
        else:
            self._read_bus()
            if self._state:
                if self._verbose > 1:
                    self._SendStatusMessage("Wanted to turn pin [{}] on board [{}] ON through TOGGLING, but input was already on. Nothing to do.".format(self._pin_out, self._i2c_out))
            else:
                msg_update = self._datapipe.ProcessCommand(TOGGLEPIN, self._i2c_out, self._pin_out)
                if self._verbose > 1:
                    self._SendStatusMessage("Turned pin [{}] on board [{}] ON through TOGGLING. Update Message is: [{}]".format(self._pin_out, self._i2c_out, msg_update))
        # Re-read the bus state for the specific input
        self._read_bus()

    def turn_off(self):
        """
        Switches output off in case the IC is output only.
        In case of a toggle output: monitors input if it not switched off already, and toggles output if not.
        """
        self.SetDirBits()
        if self._output_only:
            msg_update = self._datapipe.ProcessCommand(CLEARDATAPIN, self._i2c_out, self._pin_out)
            if self._verbose > 1:
                self._SendStatusMessage("Turned pin [{}] on board [{}] OFF. Update Message is: [{}]".format(self._pin_out, self._i2c_out, msg_update))
        else:
            self._read_bus()
            if self._state:
                msg_update = self._datapipe.ProcessCommand(TOGGLEPIN, self._i2c_out, self._pin_out)
                if self._verbose > 1:
                    self._SendStatusMessage("Turned pin [{}] on board [{}] OFF through TOGGLING. Update Message is: [{}]".format(self._pin_out, self._i2c_out, msg_update))
            else:
                if self._verbose > 1:
                    self._SendStatusMessage("Wanted to turn pin [{}] on board [{}] OFF through TOGGLING, but input was already off. Nothing to do.".format(self._pin_out, self._i2c_out))
        # Re-read the bus state for the specific input
        self._read_bus()

    def toggle(self):
        """
        Toggles output. In case of an output only, the polarity is switched. 
        In case of an input/output configuration, the output is momentarily activated (toggle switch).
        """
        self.SetDirBits()
        if self._output_only:
            self._read_bus()
            if self._state:
                msg_update = self._datapipe.ProcessCommand(CLEARDATAPIN, self._i2c_out, self._pin_out)
                if self._verbose > 1:
                    self._SendStatusMessage("Toggle command for OUTPUT ONLY case: switched pin [{}] on board [{}] OFF.".format(self._pin_out, self._i2c_out))
            else:
                msg_update = self._datapipe.ProcessCommand(SETDATAPIN, self._i2c_out, self._pin_out)
                if self._verbose > 1:
                    self._SendStatusMessage("Toggle command for OUTPUT ONLY case: switched pin [{}] on board [{}] ON.".format(self._pin_out, self._i2c_out))
        else:
            msg_update = self._datapipe.ProcessCommand(TOGGLEPIN, self._i2c_out, self._pin_out)
            if self._verbose > 1:
                self._SendStatusMessage("Toggle command received for output pin [{}] on board [{}]. Input should now have reversed.".format(self._pin_out, self._i2c_out))
        # Re-read the bus state for the specific input
        self._read_bus()

    def _read_bus(self):
        """
        Read input pin from the I2C bus in an input/output configuration, or read the
        output pin in an output-only configuration.
        """
        if self._output_only:
            self._state = self._datapipe.ProcessCommand(GETIOPIN, self._i2c_out, self._pin_out)
        else:
            self._state = self._datapipe.ProcessCommand(GETIOPIN, self._i2c_in, self._pin_in)

    def _SendStatusMessage(self, extraText = ""):
        """
        Send an email with current status. Dependent of the verbosity level, more or less information is provided.
        """
        dateTimeObj = datetime.now()
        txtmsg = "Home Assistant Info on: " + dateTimeObj.strftime("%d-%b-%Y -- %H:%M:%S.%f")
        if extraText != "":
            txtmsg = txtmsg + "\n" + extraText + "\n"
        if self._verbose == 1:
            sendMyEmail(extraText + self._name + " is switched " + \
                ("[on]" if self._state else "[off]"))
        if self._verbose > 2:
            if self._state:
                txtmsg = txtmsg + "{} is switched ON.\n\n".format(self._name)
            else:
                txtmsg = txtmsg + "{} is switched OFF.\n\n".format(self._name)
            txtmsg = txtmsg + "Switch details: \n"
            if self._output_only:
                txtmsg = txtmsg + "This is an OUTPUT ONLY \n"
                txtmsg = txtmsg + "   * output pin: [{}] on board [{}] \n".format(self._pin_out, self._i2c_out)
            else:
                txtmsg = txtmsg + "This is an INPUT DRIVEN OUTPUT \n"
                txtmsg = txtmsg + "   * input pin: [{}] on board [{}] \n".format(self._pin_in, self._i2c_in)
                txtmsg = txtmsg + "   * output pin: [{}] on board [{}] \n".format(self._pin_out, self._i2c_out)
            txtmsg = txtmsg + "Relay mode = [{}]\n".format(self._relay_mode)
            sendMyEmail(txtmsg)

def sendMyEmail(txtMessage):
    """
    Send an email to an smtp server.
    """
    mailsender = CONST_EMAIL_SENDER
    mailrecipient = CONST_EMAIL_RECEIVER
    smtpserver = CONST_EMAIL_SMTPSERVER
    msg = "From: " + mailsender + "\r\nTo: " + mailrecipient + "\r\n\r\n"
    msg = msg + txtMessage
    server = smtplib.SMTP(smtpserver, 25)
    server.set_debuglevel(1)
    server.sendmail(mailsender, mailrecipient, msg)
    server.close()
