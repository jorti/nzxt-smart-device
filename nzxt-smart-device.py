#!/usr/bin/python3 -u

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
from time import sleep


def set_fan_speed(percent):
    logging.info("Setting fan speed to {}%".format(percent))
    subprocess.run(["/usr/bin/liquidctl", "set", "sync", "speed", str(percent)])


def set_led_color(color):
    logging.info("Setting LED color to {}".format(color))
    subprocess.run(["/usr/bin/liquidctl", "set", "led", "color", "fixed", color])


CHECK_INTERVAL = 10
MIN_SPEED = 10
TEMP1 = 55
SPEED1 = 25
TEMP2 = 60
SPEED2 = 50
TEMP3 = 63
SPEED3 = 75
TEMP4 = 65
SPEED4 = 100
RED = "ff0000"
WHITE = "ffffff"

logging.basicConfig(level=logging.INFO)
logging.debug("Initializing devices")
init = subprocess.run(["/usr/bin/liquidctl", "initialize", "all"])
if init.returncode != 0:
    sys.exit(init.returncode)

current_speed = MIN_SPEED
set_fan_speed(MIN_SPEED)
while True:
    # lm_sensors
    sensors_output = subprocess.check_output(["/usr/bin/sensors", "-j"])
    logging.debug(sensors_output)
    sensors = json.loads(sensors_output)
    temp_cpu = sensors["k10temp-pci-00c3"]["Tdie"]["temp1_input"]
    temp_gpu = sensors["amdgpu-pci-0b00"]["edge"]["temp1_input"]
    temp_nvme = sensors["nvme-pci-0100"]["Composite"]["temp1_input"]
    
    max_temp = max(temp_cpu, temp_gpu, temp_nvme)
    if max_temp >= TEMP4:
        logging.warning("Highest temperature: {}ºC".format(max_temp))
        logging.info("CPU temperature:   {}ºC".format(temp_cpu))
        logging.info("GPU temperature:   {}ºC".format(temp_gpu))
        logging.info("NVMe temperature:  {}ºC".format(temp_nvme))
        new_speed = SPEED4
    elif max_temp >= TEMP3:
        new_speed = SPEED3
    elif max_temp >= TEMP2:
        new_speed = SPEED2
    elif max_temp >= TEMP1:
        new_speed = SPEED1
    else:
        new_speed = MIN_SPEED
    if new_speed != current_speed:
        set_fan_speed(new_speed)
        if max_temp >= TEMP4:
            set_led_color(RED)
        else:
            set_led_color(WHITE)
        current_speed = new_speed
    sleep(CHECK_INTERVAL)
