from .water_bath import (  # noqa: F401 unused imports
    OnOffArraySettings,
    get_temperature_validation_errors,
    send_command_and_parse_response,
    send_settings_command_and_parse_response,
    initialize,
)

"""
A driver for the Thermo Scientific NESLAB RTE 17 Temperature-controlled water bath

Excerpts from the datasheet:
(https://drive.google.com/file/d/1Tg-e1C8Ht8BE7AYzKVSqjw9bhWWxqKlz?disco=AAAADMVYeIw)

All data is sent and received in binary form, do not use ASCII. In the following
pages the binary data is represented in hexadecimal (hex) format.

The NC Serial Communications Protocol is based on a master-slave model.
The master is a host computer, while the slave is the bath's controller. Only
the master can initiate a communications transaction (half-duplex). The bath
ends the transaction by responding to the master’s query. The protocol uses
either an RS-232 or RS-485 serial interface with the default parameters: 19200
baud, 1 start bit, 8 data bits, 1 stop bit, no parity.

(See SerialPacket for the framing of the communications packet)

The master requests information by sending one of the Read Functions. Since no data is
sent to the bath during a read request, the master uses 00 for the number of data bytes
following the command byte.

The bath will respond to a Read Function by echoing the lead character, address, and
command byte, followed by the requested data and checksum. When the bath sends data, a
qualifier byte is sent first, followed by a two byte signed integer (16 bit, MSB sent
first). The qualifier byte indicates the precision and units of measure for the
requested data as detailed in Table 2.

The master sets parameters in the bath by sending one of the Set Functions. The master
does not send a qualifier byte in the data field. The master should be pre-programmed to
send the correct precision and units (it could also read the parameter of interest first
to decode the correct precision and units needed).

"""
