#! /usr/bin/env python
"""
Part of SolarSan.

Copyright 2013 Trevor Joynson

"""

from setuptools import setup

setup(
    name='solarsan',
    version='0.0.1',
    description='SolarSan Core',
    license='GPL3',
    maintainer='Trevor Joynson',
    maintainer_email='github@skywww.net',
    url='http://github.com/akatrevorjay/solarsan',
    packages=['san', 'san.core', 'san.cli', 'san.networking', 'san.utils'],
    #use_2to3=True,
    entry_points=dict(
        console_scripts=['sancli=san.cli:main'],
    ),
)
