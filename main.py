#!usr/bin/python3

import argparse
from datalogging.datalogger import YoctoLogger, ChirpLogger
from datalogging.imagelogger import imagelogger


def main(configfile, devicetype):
    """
    Entry point of the 'plantlogger' application.

    Args:
        configfile: The name of a .ini file containing the configuration to
                    be used by the application for datalogging.
        devicetype: The type of devices for which data is being logged.
    """
    if devicetype == "yocto":
        logger = YoctoLogger(configfile)
        logger.start()
    elif devicetype == "chirp":
        logger = ChirpLogger(configfile)
        logger.start()
    elif devicetype == "images":
        imagelogger(configfile)
    else:
        print("Error: cannot log data for input device type {}. Please choose\
 between 'yocto' and 'chirp'.".format(devicetype))
        return


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='An application to log data\
 from sensors on InfluxDB.')
    parser.add_argument('configfile', help='The name of a configuration file\
 (.ini) to be used by the application for datalogging.')
    parser.add_argument('devicetype', help='The type of devices being logged\
 (yocto or chirp).')
    args = parser.parse_args()

    main(args.configfile, args.devicetype)
