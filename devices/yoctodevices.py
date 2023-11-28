"""
Module to detect and access Yoctopuce devices connected to a machine.
"""

import time
import logging
from yoctopuce.yocto_api import *


logger = logging.getLogger(__name__)


def init_yocto_api(ip, port):
    """
    Initialize the YoctoAPI.

    Args:
        ip: The IP adress of the Yoctopuce VirtualHub to detect the sensors.
        port: The port on which the VirtualHub listens

    Returns:
        True if the initialisation was a success, False otherwise.
    """
    errmsg = YRefParam()
    if YAPI.RegisterHub("{}:{}".format(ip, port), errmsg) != YAPI.SUCCESS:
        logger.error("YoctoAPI init error: " + str(errmsg))
        return False

    return True


def modules():
    """
    Generator to iterate over the Yoctopuce modules connected to the
    VirtualHub.

    Yields:
        The next Yoctopuce module connected to machine (as long as there is one
        that hasn't already been yielded).
    """
    module = YModule.FirstModule()
    while module:
        # Ignore the VirtualHub itself, as it is not a real physical
        # module and it doesn't interest us for data logging.
        if module.get_productName() != "VirtualHub":
            yield module
        module = module.nextModule()


def get_functions(module):
    """
    Iterate over the functions of a Yoctopuce module.

    Args:
        module: A Yoctopuce module.

    Yields:
        The next Yoctopuce function of the module and its associated value
        (as long as there is one that hasn't already been yielded).
    """
    for i in range(module.functionCount()):
        function = module.functionId(i)
        yield (function, module.functionValue(i))


def get_data(module, function, from_time, to_time):
    """
    Get the data saved on the datalogger of a Yoctopuce module for a given
    sensor (module function).

    Args:
        module: The YModule object corresponding to the module for which the
                data must be retrieved.
        function: The name of the function of the module for which the data
                  must be retrieved.
        from_time: The time from which to begin to retrieve data (seconds from
                   the 1 of January 1970).
        to_time: The time up to which the data must be retrieved (seconds from
                 the 1 of January 1970).

    Returns:
        A list of dictionnaries with times as keys and recorded measures as
        values.
    """
    sensor = YSensor.FindSensor("{}.{}".format(module.get_serialNumber(),
                                               function))
    dataset = sensor.get_recordedData(from_time, to_time)
    # Retrieve the data for the sensor. This must be done incrementally in the
    # API, hence the while loop. 'progress' indicates the completion %.
    dataset.loadMore()
    progress = 0
    while progress < 100:
        progress = dataset.loadMore()
    measures = dataset.get_measures()

    # Return data in the format accepted by InfluxDB.
    logs = []
    time_format = "%a, %d %b %Y %H:%M:%S"
    module_name = module.get_logicalName()
    if module_name == "":
        module_name = module.get_serialNumber()
    for measure in measures:
        logs.append({"measurement": module_name,
                     "time": measure.get_startTimeUTC_asDatetime()
                                    .strftime(time_format),
                     "fields": {function: measure.get_averageValue()}})
    return logs


def erase_data(module):
    """
    Erase all the data saved on the datalogger of a module.

    Args:
        module: The module for which all data must be erased.
    """
    datalogger = YDatalogger.FindDatalogger("{}.datalogger"
                                            .format(module.get_serialNumber()))
    datalogger.forgetAllDataStreams()
