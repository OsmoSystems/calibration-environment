#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name="calibration_environment",
    version="0.0.1",
    author="Osmo Systems",
    author_email="dev@osmobot.com",
    description="Automation and data collection tools for the Osmo calibration environment",
    url="https://www.github.com/osmosystems/calibration-environment.git",
    packages=find_packages(),
    entry_points={},
    install_requires=["pyserial"],
    include_package_data=True,
)
