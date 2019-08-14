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
    entry_points={
        "console_scripts": ["run_calibration = calibration_environment.run:run"]
    },
    # fmt: off
    install_requires=[
        "backoff",
        "pandas",
        "paramiko",
        "plotly>=4",
        "pyserial"
    ],
    # fmt: on
    include_package_data=True,
)
