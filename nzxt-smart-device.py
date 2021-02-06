#!/usr/bin/python3

# Copyright 2021 Juan Orti Alcaine <jortialc@redhat.com>
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
import argparse
from time import sleep


class NzxtDevice():
    def __init__(self, device_vendor="0x1e71", led_color="555555", led_mode="fixed", fan_speed=100):
        self.led_color = led_color
        self.led_mode = led_mode
        self.fan_speed = fan_speed
        self.device_vendor = device_vendor
        self._init_device()
        self.set_fan_speed(self.fan_speed)
        self.set_led(self.led_mode, self.led_color)

    def _init_device(self):
        logging.info("Initializing device with vendor ID {}".format(self.device_vendor))
        init = subprocess.run(["/usr/bin/liquidctl", "--vendor", self.device_vendor, "initialize"])
        if init.returncode != 0:
            sys.exit(init.returncode)

    def set_fan_speed(self, percent):
        if self.fan_speed != percent:
            logging.info("Setting fan speed to {}%".format(percent))
            result = subprocess.run(["/usr/bin/liquidctl", "--vendor", self.device_vendor, "set", "sync", "speed", str(percent)])
            if result.returncode != 0:
                logging.critical("Error setting fan speed")
                sys.exit(result.returncode)
            self.fan_speed = percent

    def set_led(self, mode, color):
        if self.led_color != color or self.led_mode != mode:
            logging.info("Setting LED mode to {} and color {}".format(mode, color))
            result = subprocess.run(["/usr/bin/liquidctl", "--vendor", self.device_vendor, "set", "led", "color", mode, color])
            if result.returncode != 0:
                logging.critical("Error setting LEDs")
                sys.exit(result.returncode)
            self.led_color = color
            self.led_mode = mode


def get_sensors_max_temp(devices_hint=('k10temp', 'nvme', 'coretemp', 'acpitz', 'iwlwifi')):
    sensors_output = subprocess.check_output(["/usr/bin/sensors", "-j"])
    sensors = json.loads(sensors_output)
    temps = []
    for device in sensors.keys():
        device_ok = False
        for hint in devices_hint:
            if hint in device:
                device_ok = True
        if not device_ok:
            logging.debug("Skipping sensors in device: {}".format(device))
            continue
        for sensor in sensors[device].keys():
            if not isinstance(sensors[device][sensor], dict):
                continue
            for key in sensors[device][sensor].keys():
                if "input" in key:
                    logging.debug("Adding sensor temperature: device={} sensor={} input={}".format(device, sensor, key))
                    temps.append(sensors[device][sensor][key])
    return max(temps)


parser = argparse.ArgumentParser(description="NZXT smart device control")
parser.add_argument("--interval", type=int, default=10, help="Interval between checks, in seconds")
parser.add_argument("--min-speed", type=int, default=10, help="Minimum fan speed, in percent")
parser.add_argument("--max-speed", type=int, default=100, help="Maximum fan speed, in percent")
parser.add_argument("--max-temp", type=int, default=65, help="Maximum temperature allowed, in Celsius")
parser.add_argument("--led-mode", default="fixed", help="Normal LED mode")
parser.add_argument("--led-mode-warn", default="fixed", help="Warning LED mode")
parser.add_argument("--led-color", default="555555", help="Normal LED color")
parser.add_argument("--led-color-warn", default="ff0000", help="Warning LED color")
parser.add_argument("--log-level", default="INFO", help="Log level",
                    choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
args = parser.parse_args()

numeric_level = getattr(logging, args.log_level.upper(), None)
if not isinstance(numeric_level, int):
    raise ValueError('Invalid log level: %s' % args.log_level)
logging.basicConfig(level=numeric_level)

# Validate args
if args.min_speed >= args.max_speed:
    logging.error("Minimum fan speed has to be less than the max speed")
    sys.exit(1)

nzxt_device = NzxtDevice(led_color=args.led_color, led_mode=args.led_mode, fan_speed=args.max_speed)
while True:
    current_max_temp = get_sensors_max_temp()
    if current_max_temp >= args.max_temp:
        logging.warning("Highest temperature: {}ºC".format(current_max_temp))
        nzxt_device.set_fan_speed(args.max_speed)
        nzxt_device.set_led(args.led_mode_warn, args.led_color_warn)
    else:
        fan_speed = (current_max_temp // args.max_temp) * 100
        fan_speed = max(fan_speed, args.min_speed)
        fan_speed = min(fan_speed, args.max_speed)
        logging.debug("current_max_temp: {}, fan_speed {}".format(current_max_temp, fan_speed))
        nzxt_device.set_fan_speed(fan_speed)
        nzxt_device.set_led(args.led_mode, args.led_color)
    sleep(args.interval)
