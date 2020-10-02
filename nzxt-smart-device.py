#!/usr/bin/python -u

# Copyright 2020 Juan Orti Alcaine <jortialc@redhat.com>
#
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import subprocess
import json
import sys
import logging
import re
import argparse
from time import sleep


def init_device():
    logging.info("Initializing devices")
    init = subprocess.run(["/usr/bin/liquidctl", "--vendor", "0x1e71", "initialize"])
    if init.returncode != 0:
        sys.exit(init.returncode)


def set_fan_speed(percent):
    global current_speed
    if current_speed != percent:
        logging.info("Setting fan speed to {}%".format(percent))
        result = subprocess.run(["/usr/bin/liquidctl", "--vendor", "0x1e71", "set", "sync", "speed", str(percent)])
        if result.returncode != 0:
            logging.critical("Error setting fan speed")    
            sys.exit(result.returncode)
        current_speed = percent


def set_led(color, mode):
    global current_led_color
    global current_led_mode
    if current_led_color != color or current_led_mode != mode:
        logging.info("Setting LED color to {} and mode {}".format(color, mode))
        result = subprocess.run(["/usr/bin/liquidctl", "--vendor", "0x1e71", "set", "led", "color", mode, color])
        if result.returncode != 0:
            logging.critical("Error setting LEDs")
            sys.exit(result.returncode)
        current_led_color = color
        current_led_mode = mode


parser = argparse.ArgumentParser(description="NZXT smart device control")
parser.add_argument("--interval", type=int, default=10, help="Interval between checks, in seconds")
parser.add_argument("--min-speed", type=int, default=10, help="Minimum fan speed, in percent")
parser.add_argument("--max-speed", type=int, default=100, help="Maximum fan speed, in percent")
parser.add_argument("--max-temp", type=int, default=65, help="Maximum temperature allowed, in Celsius")
parser.add_argument("--led-mode", default="fixed", help="Normal LED mode")
parser.add_argument("--led-mode-warn", default="fixed", help="Warning LED mode")
parser.add_argument("--led-color", default="555555", help="Normal LED color")
parser.add_argument("--led-color-warn", default="ff0000", help="Warning LED color")
parser.add_argument("--log-level", default="INFO", help="Log level", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
args = parser.parse_args()

numeric_level = getattr(logging, args.log_level.upper(), None)
if not isinstance(numeric_level, int):
    raise ValueError('Invalid log level: %s' % loglevel)
logging.basicConfig(level=numeric_level)

# Initialize global variables
current_speed = 0
current_led_color = ""
current_led_mode = ""

init_device()
while True:
    # lm_sensors
    sensors_output = subprocess.check_output(["/usr/bin/sensors", "-j"])
    logging.debug(sensors_output)
    sensors = json.loads(sensors_output)
    temp_cpu = sensors["k10temp-pci-00c3"]["Tdie"]["temp2_input"]
    temp_gpu = sensors["amdgpu-pci-0b00"]["edge"]["temp1_input"]
    temp_nvme = sensors["nvme-pci-0100"]["Composite"]["temp1_input"]
    
    current_max_temp = max(temp_cpu, temp_gpu, temp_nvme)
    if current_max_temp >= args.max_temp:
        logging.warning("Highest temperature: {}ºC".format(current_max_temp))
        logging.info("CPU temperature:   {}ºC".format(temp_cpu))
        logging.info("GPU temperature:   {}ºC".format(temp_gpu))
        logging.info("NVMe temperature:  {}ºC".format(temp_nvme))
        set_fan_speed(args.max_speed)
        set_led(args.led_color_warn, args.led_mode_warn)
    else:
        # Calculate percentage of current temp over max temp and choose a speed based on it
        percent = (current_max_temp*100)/args.max_temp
        if percent >= 95:
            final_percent = 75
        elif percent >= 90:
            final_percent = 50
        elif percent >= 80:
            final_percent = 25
        else:
            final_percent = 0
        logging.debug("current_max_temp: {}, configured_max_temp: {}, percent: {}, final_percent: {}".format(current_max_temp, args.max_temp, percent, final_percent))
        set_fan_speed(max(final_percent, args.min_speed))
        set_led(args.led_color, args.led_mode)
    sleep(args.interval)
