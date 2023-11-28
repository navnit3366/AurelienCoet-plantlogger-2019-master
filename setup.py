from setuptools import setup


setup(name='plantlogger',
      version=1.0,
      description='Data logger for a plant management system',
      author='Aurelien Coet',
      author_email='aurelien.coet19@gmail.com',
      packages=['datalogging',
                'devices'],
      install_requires=[
        'yoctopuce',
        'influxdb',
      ])
