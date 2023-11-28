"""
Module to take pictures with an RPI-Cam when a Yoctopuce relay is ON.
"""

import logging
import time
import requests
import devices.yoctodevices as yoctodevices
from configparser import ConfigParser
from threading import Thread
from yoctopuce.yocto_api import *
from yoctopuce.yocto_relay import *

logger = logging.getLogger(__name__)
logging.basicConfig(filename="{}.log".format(__name__), level=logging.INFO)


def imagelogger(configfile):
    """
    Record images with a RPI-Cam when specific Yoctopuce relays are activated.

    Args:
        configfile: A configuration file containing information about the
                    relays for which image recording is enabled and the
                    RPI-Camera that must be used for recording.
    """
    logger.info("Activation of image recording")
    # -------------------- Configuration -------------------- #
    # Retrieve the information about the relays for which image recording is
    # enabled and the RPI-Cam to use.
    config = ConfigParser()
    config.read(configfile)

    # URL that must be called to record an image with the RPI-Cam.
    url = config['RPI-Cam']['url']
    # Info. about the recording duration and the timesteps between images.
    duration = int(config['Recording']['duration'])
    timesteps = int(config['Recording']['timesteps'])

    # Flag to indicate whether new information is added to the
    # configuration when iterating over the Yoctopuce relays.
    config_changed = False

    # -------------------- Callback function -------------------- #
    recording = False

    # Definition of the function that will actually record images.
    def record_images(url, duration, timesteps):
        logger.info("Starting to record images")
        time_elapsed = 0
        while time_elapsed < duration:
            # Record an image.
            requests.get(url)
            time_elapsed += timesteps
            time.sleep(timesteps)

        logger.info("Finished recording images")

    # Definition of the callback function called when a relay is activated.
    def start_recording(function, value):
        # Do nothing when a relay is turned OFF.
        if value == "A":
            return
        # The function is not started in a thread, as we do not want multiple
        # recordings at the same time.
        record_images(url, duration, timesteps)

    # -------------------- Activation of callbacks -------------------- #
    yoctodevices.init_yocto_api(config['VirtualHub']['host'],
                                config['VirtualHub']['port'])
    for module in yoctodevices.modules():
        # Ignore all modules that aren't Yocto-relays.
        if "relay" not in module.get_productName().lower():
            continue

        module_serial = module.get_serialNumber()
        module_name = module.get_logicalName() or module_serial

        # If a relay is detected and there is no information about it in
        # the configuration file, default information is added.
        if module_serial not in config:
            config[module_serial] = {}
            config_changed = True

        for (function, _) in yoctodevices.get_functions(module):
            # By default, pictures aren't recorded for a relay when it is
            # activated.
            if 'record-'+function not in config[module_serial]:
                config[module_serial]['record-'+function] = 'false'
                config_changed = True

            if config[module_serial]['record-'+function] == 'true':
                relay = YRelay.FindRelay("{}.{}".format(module_serial,
                                                        function))
                relay.registerValueCallback(start_recording)

    # -------------------- Configuration update -------------------- #
    # Save the configuration if new relays have been detected.
    if config_changed:
        with open(configfile, 'w') as config_f:
            config.write(config_f)

    # -------------------- Callbacks listening -------------------- #
    while True:
        YAPI.Sleep(1000)
