"""
Module to log data retrieved from the sensors connected to a machine.
"""

import logging
import time
import devices.yoctodevices as yoctodevices
import devices.chirpdevices as chirpdevices
from configparser import ConfigParser
from threading import Thread
from influxdb import InfluxDBClient
from yoctopuce.yocto_api import *
from yoctopuce.yocto_relay import *

logger = logging.getLogger(__name__)
logging.basicConfig(filename="{}.log".format(__name__), level=logging.INFO)


class DataLogger(Thread):
    """
    Datalogger to log information retrieved from devices (sensors).
    """

    def __init__(self, configfile):
        # A configuration file is used by the system to define the database on
        # which to log data, as well as which devices to log data for.
        self.configfile = configfile
        self.config = ConfigParser()
        super().__init__()

    def start(self):
        self.config.read(self.configfile)

        # Initialisation of the data server on startup.
        dataserver = self.config['DataServer']
        self.client = InfluxDBClient(host=dataserver['host'],
                                     port=dataserver['port'],
                                     username=dataserver['username'],
                                     password=dataserver['password'],
                                     database=dataserver['database'])

        # Creation of the database if it doesn't exist.
        db_names = [db['name'] for db in self.client.get_list_database()]
        if dataserver['database'] not in db_names:
            self.client.create_database(dataserver['database'])

        # Flag to indicate whether new information has been added to the
        # configuration during the execution of the thread.
        self.config_changed = False

        logger.info("Starting to log data on server {}:{}, db: {}."
                    .format(dataserver['host'],
                            dataserver['port'],
                            dataserver['database']))
        self.stop = False
        super().start()

    def stop(self):
        logger.info("Stopping to log data on the server.")
        self.stop = True

    def run(self):
        while not self.stop:
            # The configuration file is read again every time that new
            # data is being logged by the system, in case modifications were
            # made since the last iteration.
            self.config.read(self.configfile)

            # Log the data produced by the devices connected to the
            # machine.
            self.log_data()

            if 'timeout' in self.config['DataLogging']:
                timeout = self.config['DataLogging']['timeout']
            else:
                timeout = 60  # Default timeout is set to 1 minute.

            time.sleep(int(timeout))

    def log_data(self):
        """
        Log data received from the devices.

        Args:
            devconf: A ConfigParser object containing information about the
                     devices connected and indicating whether to log their data
                     or not.
        """
        # This method must be implemented by subclasses specialised in logging
        # data from specific devices.
        raise NotImplementedError

    def save_config(self):
        """
        Save the current devices configuration associated to the object if it
        has changed.
        """
        if not self.config_changed:
            return

        with open(self.configfile, 'w') as configfile:
            self.config.write(configfile)

        # Reset the 'devconf_changed' flag.
        self.config_changed = False


class YoctoLogger(DataLogger):
    """
    Datalogger to log information retrieved from Yoctopuce devices.
    """

    def start(self):
        self.config.read(self.configfile)

        # Track the last time data was retrieved by the datalogger. Initially
        # equal to 0, to indicate no data has been retrieved yet.
        if 'last-log' in self.config['DataLogging']:
            self.start_log = float(self.config['DataLogging']['last-log'])
        else:
            self.start_log = 0
        self.end_log = self.start_log
        yoctodevices.init_yocto_api(self.config['VirtualHub']['host'],
                                    self.config['VirtualHub']['port'])
        super().start()

    def stop(self):
        YAPI.FreeAPI()
        super().stop()

    def log_data(self):
        self.start_log = self.end_log
        self.end_log = time.time()

        try:
            for module in yoctodevices.modules():
                # Ignore relays, as they are detected as a Yoctopuce
                # module but don't posess any actual physical sensors
                # to log data from.
                if 'relay' in module.get_productName().lower():
                    continue
                self.log_yocto(module)

            # Save the last time data was retrieved in the configuration file.
            logger.info("Finished last log at {}"
                        .format(time.strftime("%d %b %Y %H:%M:%S",
                                              time.localtime())))
            self.config['DataLogging']['last-log'] = str(self.end_log)
            self.config_changed = True

        except Exception as e:
            logger.error("Error while iterating over Yoctopuce devices: {}"
                         .format(e))

        finally:
            self.save_config()

    def log_yocto(self, module):
        """
        Log the data retrieved from the sensor of a given Yoctopuce module.

        Args:
            module: The Yoctopuce module for which the datapoints must be
                    retrieved.
        """
        try:
            datapoints = []

            module_serial = module.get_serialNumber()
            module_name = module.get_logicalName() or module_serial

            # If no information exists in the configuration about a device
            # that is detected by the system, default information about it is
            # added to the configuration.
            if module_serial not in self.config:
                self.config[module_serial] = {}
                self.config[module_serial]['logical-name'] = module_name
                self.config_changed = True

            for (function, _) in yoctodevices.get_functions(module):
                # Ignore the datalogger of a module as it is identified as one
                # of its functions but it doesn't actually log any value on
                # itself.
                if function == "dataLogger":
                    continue

                if 'log-'+function not in self.config[module_serial]:
                    # By default, all functions from a module are logged.
                    self.config[module_serial]['log-'+function] = 'true'

                if self.config[module_serial]['log-'+function] == 'true':
                    try:
                        datapoints.extend(yoctodevices.get_data(module,
                                                                function,
                                                                self.start_log,
                                                                self.end_log))
                    except Exception as e:
                        logger.error("Impossible to read data from the\
 datalogger of module {}: {}".format(module_name, e))

            # Send the datapoints to the InfluxDB database.
            if len(datapoints) != 0:
                self.client.write_points(datapoints)

        except Exception as e:
            logger.error("Error while logging data from module {}: {}"
                         .format(module.get_logicalName(), e))


class ChirpLogger(DataLogger):
    """
    Datalogger to log information retrieved from Chirp devices.
    """

    def log_data(self):
        try:
            datapoints = []

            # Iterate over all the Chirp devices connected to the machine and
            # log the data they produce if logging is set to 'true' in the
            # deviceconfig configuration.
            for chirp in chirpdevices.chirps(self.config):
                self.log_chirp(chirp, datapoints)

            self.client.write_points(datapoints)

        except Exception as e:
            logger.error("Error while iterating over chirp devices: {}"
                         .format(e))

        finally:
            self.save_config()

    def log_chirp(self, chirp, datapoints):
        """
        Log the data from a Chirp device in a list of data points.

        Args:
            chirp: The Chirp device to log the data from.
            deviceconfig: A ConfigParser object containing the configuration
                          for data logging.
            datapoints: The list of datapoints to which the data from the
                        module must be appended.
        """
        try:
            address = str(chirp.address)
            logical_name = ""

            if address in self.config:
                logical_name = self.config[address]['logical-name']
            else:
                # If a new Chirp device is detected and no information about
                # it exists in the devices configuration, add default
                # information about it.
                self.config[address] = {}
                self.config[address]['logical-name'] = address
                logical_name = address
                self.config_changed = True

            datapoints.append({
                "measurement": "{}".format(logical_name),
                "time": time.strftime("%a, %d %b %Y %H:%M:%S",
                                      time.localtime()),
                "fields": {}
            })

            for (func_name, func_value) in chirpdevices.get_functions(chirp):
                # By default, all functions from Chirp devices are read and
                # logged on the server.
                if 'log-'+func_name not in self.config[address]:
                    self.config[address]['log-'+func_name] = 'true'
                    self.config_changed = True

                if self.config[address]['log-'+func_name] == 'true':
                    datapoints[-1]["fields"][func_name] = func_value

        except Exception as e:
            logger.error("Error logging the data from Chirp device {}: {}"
                         .format(logical_name, e))
