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
    def __init__(self, device_vendor=None, device_product=None, led_color="555555", led_mode="fixed", fan_speed=100,
                 dry_run=False):
        self.led_color = led_color
        self.led_mode = led_mode
        self.fan_speed = fan_speed
        self.device_vendor = device_vendor
        self.device_product = device_product
        self.dry_run = dry_run
        self._init_device()
        self.set_fan_speed(self.fan_speed)
        self.set_led(self.led_mode, self.led_color)

    def _init_device(self):
        logging.info("Initializing device")
        cmd = ["/usr/bin/liquidctl", ] + self._liquidctl_device_cmd() + ["initialize"]
        if self.dry_run:
            return
        init = subprocess.run(cmd)
        if init.returncode != 0:
            sys.exit(init.returncode)

    def _liquidctl_device_cmd(self):
        if self.device_product:
            return ["--product", self.device_product]
        elif self.device_vendor:
            return ["--vendor", self.device_vendor]
        return None

    def set_fan_speed(self, percent):
        if self.fan_speed != percent:
            logging.info("Setting fan speed to {}%".format(percent))
            cmd = ["/usr/bin/liquidctl", ] + self._liquidctl_device_cmd() + ["set", "sync", "speed", str(percent)]
            if self.dry_run:
                return
            result = subprocess.run(cmd)
            if result.returncode != 0:
                logging.critical("Error setting fan speed")
                sys.exit(result.returncode)
            self.fan_speed = percent

    def set_led(self, mode, color):
        if self.led_color != color or self.led_mode != mode:
            logging.info("Setting LED mode to {} and color {}".format(mode, color))
            cmd = ["/usr/bin/liquidctl", ] + self._liquidctl_device_cmd() + ["set", "led", "color", mode, color]
            if self.dry_run:
                return
            result = subprocess.run(cmd)
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
                    logging.debug(
                        "Adding sensor temperature: device={} sensor={} input={} value={}".format(device, sensor, key,
                                                                                                  sensors[device][
                                                                                                      sensor][key]))
                    temps.append(sensors[device][sensor][key])
    return max(temps)


def calculate_fan_speed(current_max_temp, max_temp):
    ratio = current_max_temp / args.max_temp
    if ratio >= 0.95:
        return 100
    elif ratio >= 0.9:
        return 75
    elif ratio >= 0.85:
        return 60
    elif ratio >= 0.8:
        return 40
    elif ratio >= 0.75:
        return 25
    else:
        return 0


parser = argparse.ArgumentParser(description="NZXT smart device control")
parser.add_argument("--product", type=str, help="Filter devices by hexadecimal product ID")
parser.add_argument("--vendor", type=str, help="Filter devices by hexadecimal vendor ID")
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
parser.add_argument("--dry-run", default=False, action="store_true", help="Don't do real actions")
args = parser.parse_args()

numeric_level = getattr(logging, args.log_level.upper(), None)
if not isinstance(numeric_level, int):
    raise ValueError('Invalid log level: %s' % args.log_level)
logging.basicConfig(level=numeric_level)

# Validate args
if args.min_speed >= args.max_speed:
    logging.critical("Minimum fan speed has to be less than the max speed")
    sys.exit(1)
if args.max_temp <= 0:
    logging.critical("Max temp has to be greater than 0")
    sys.exit(1)

nzxt_device = NzxtDevice(device_vendor=args.vendor, device_product=args.product, led_color=args.led_color,
                         led_mode=args.led_mode, fan_speed=args.max_speed,
                         dry_run=args.dry_run)
while True:
    current_max_temp = get_sensors_max_temp()
    if current_max_temp >= args.max_temp:
        if nzxt_device.fan_speed != args.max_speed:
            logging.warning("Temperature is greater than the configured threshold of {}ºC".format(args.max_temp))
            logging.info("Current max temperature: {}ºC".format(current_max_temp))
        nzxt_device.set_fan_speed(args.max_speed)
        nzxt_device.set_led(args.led_mode_warn, args.led_color_warn)
    else:
        fan_speed = calculate_fan_speed(current_max_temp, args.max_temp)
        fan_speed = max(fan_speed, args.min_speed)
        fan_speed = min(fan_speed, args.max_speed)
        if nzxt_device.fan_speed != fan_speed:
            logging.info("Current max temperature: {}ºC".format(current_max_temp))
        nzxt_device.set_fan_speed(fan_speed)
        nzxt_device.set_led(args.led_mode, args.led_color)
    sleep(args.interval)
