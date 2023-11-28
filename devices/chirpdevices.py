"""
Module to detect and access Chirp devices connected to a machine.
"""

import logging
from chirp.chirp import Chirp

logger = logging.getLogger(__name__)


def detect_i2c_devices():
    """
    Detect the adresses where I2C devices are responding.

    Returns:
        A list of hexadecimal adresses.
    """
    try:
        import smbus
        bus = smbus.SMBus(1)  # 1 is for /dev/i2c-1
        addresses = []

        for device in range(128):
            try:
                bus.read_byte(device)
                addresses.append(hex(device))
            except Exception:
                pass  # Handle the case where read_byte fails.

        return addresses

    except ImportError:
        logger.error("Couldn't load smbus module. Cannot identify I2C\
 devices.")
        return []


def chirps(config):
    """
    Generator to iterate over the Chirp devices connected to the machine.

    Args:
        config: A ConfigParser object potentially containing information about
                the Chirps connected to the machine.

    Yields:
        The next Chirp device connected to machine (as long as there is one
        that hasn't already been yielded).
    """
    for hex_address in detect_i2c_devices():
        min_moist = False
        max_moist = False

        address = int(hex_address, 16)
        str_address = str(address)
        if str_address in config:
            if 'min-moist' in config[str_address]:
                min_moist = int(config[str_address]['min-moist'])

            if 'max-moist' in config[str_address]:
                max_moist = int(config[str_address]['max-moist'])

        chirp = Chirp(address=address,
                      read_moist=True,
                      read_temp=True,
                      read_light=True,
                      min_moist=min_moist,
                      max_moist=max_moist,
                      temp_scale='celsius',
                      temp_offset=0)
        yield chirp


def get_functions(chirp):
    """
    Generator to iterate over the functions of a Chirp device.

    Args:
        chirp: A Chirp device interface.

    Yields:
        The next function of the Chirp and its associated value
        (as long as there is one that hasn't already been yielded).
    """
    funcs = ["temperature", "moisture", "light"]

    # The moisture percentage is only returned if the min_moist and max_moist
    # attributes of the Chirp are set (the value can't be retrieved otherwise).
    if chirp.min_moist and chirp.max_moist:
        funcs.append("moisture-percent")

    chirp.trigger()
    chirp.trigger()  # Called twice to retrieve the latest values.

    for func_name in funcs:
        if func_name == "temperature":
            func_value = chirp.temp
        elif func_name == "moisture":
            func_value = chirp.moist
        elif func_name == "moisture-percent":
            func_value = chirp.moist_percent
        elif func_value == "light":
            func_value = chirp.light

        yield (func_name, func_value)
