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
import yaml
from time import sleep


class NzxtDevice():
    def __init__(self, device):
        self.led_color = "000000"
        self.led_mode = "fixed"
        self.fan_speed_percent = 100
        self.name = device["name"]
        self.vendor_id = device["vendor_id"]
        self.product_id = device["product_id"]
        self._init_device()
        self._apply_state()

    def _init_device(self):
        cmd = ["/usr/bin/liquidctl", "-v"] + self._liquidctl_device_opts() + ["initialize"]
        init = subprocess.run(cmd)
        if init.returncode != 0:
            sys.exit(init.returncode)

    def _apply_state(self):
        cmd_fan = ["/usr/bin/liquidctl", "-v"] + self._liquidctl_device_opts() + ["set", "sync", "speed",
                                                                             str(self.fan_speed_percent)]
        cmd_led = ["/usr/bin/liquidctl", "-v"] + self._liquidctl_device_opts() + ["set", "led", "color", self.led_mode,
                                                                             self.led_color]
        subprocess.run(cmd_fan)
        subprocess.run(cmd_led)

    def _liquidctl_device_opts(self):
        opts = []
        if self.product_id:
            opts += ["--product", self.product_id]
        if self.vendor_id:
            opts += ["--vendor", self.vendor_id]
        return opts

    def set_fan_speed(self, percent):
        if  self.fan_speed_percent != percent:
            self.fan_speed_percent = percent
            self._apply_state()

    def set_led(self, mode, color):
        if self.led_color != color or self.led_mode != mode:
            self.led_color = color
            self.led_mode = mode
            self._apply_state()


def get_sensors_max_temp():
    sensors_output = subprocess.check_output(["/usr/bin/sensors", "-j"])
    sensors = json.loads(sensors_output)
    temps = []
    for device in sensors.keys():
        for sensor in sensors[device].keys():
            if not isinstance(sensors[device][sensor], dict):
                continue
            for key in sensors[device][sensor].keys():
                if "temp" in key and "input" in key:
                    logging.debug(
                        "Sensor temperature: device={} sensor={} input={} value={}".format(device, sensor, key,
                                                                                           sensors[device][
                                                                                               sensor][key]))
                    temps.append(sensors[device][sensor][key])
    return max(temps)


def calculate_fan_speed(current_max_temp, max_temp, min_fan_speed, max_fan_speed):
    ratio = current_max_temp / max_temp
    if ratio >= 0.95:
        fan_speed = 100
    elif ratio >= 0.9:
        fan_speed = 75
    elif ratio >= 0.85:
        fan_speed = 60
    elif ratio >= 0.8:
        fan_speed = 40
    elif ratio >= 0.75:
        fan_speed = 25
    else:
        fan_speed = 0
    fan_speed = max(fan_speed, min_fan_speed)
    fan_speed = min(fan_speed, max_fan_speed)
    return fan_speed


def parse_config(config_file=None):
    if not config_file:
        return {}
    try:
        with open(config_file, "r") as f:
            yaml_content = yaml.load(f, Loader=yaml.SafeLoader)
            return yaml_content
    except OSError as e:
        print("Error loading config: {}".format(e))
        sys.exit(1)


def validate_args():
    if config:
        if "max_fan_speed_percent" in config and "min_fan_speed_percent" in config:
            if config["min_fan_speed_percent"] >= config["max_fan_speed_percent"]:
                logging.critical("Minimum fan speed has to be less than the max speed")
                sys.exit(1)
        if "max_temp" in config:
            if config["max_temp"] >= 90:
                logging.warning("Dangerously high temperature: {}ºC".format(config["max_temp"]))


parser = argparse.ArgumentParser(description="NZXT smart device control")
parser.add_argument("-c", "--config-file", help="Config file", default="/etc/nzxt-smart-device.yaml")
parser.add_argument("--log-level", default="INFO", help="Log level",
                    choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
args = parser.parse_args()
log_numeric_level = getattr(logging, args.log_level.upper(), None)
if not isinstance(log_numeric_level, int):
    raise ValueError('Invalid log level: %s' % args.log_level)
logging.basicConfig(level=log_numeric_level)

config = parse_config(args.config_file)
validate_args()

nzxt_device = NzxtDevice(config["device"])

while True:
    current_max_temp = get_sensors_max_temp()
    if current_max_temp >= config["max_temp"]:
        logging.warning("Max temperature reached: {}ºC".format(current_max_temp))
        nzxt_device.set_fan_speed(config["max_fan_speed_percent"])
        nzxt_device.set_led(config["led_mode_warning"], config["led_color_warning"])
    else:
        fan_speed = calculate_fan_speed(current_max_temp, config["max_temp"], config["min_fan_speed_percent"],
                                        config["max_fan_speed_percent"])
        nzxt_device.set_fan_speed(fan_speed)
        nzxt_device.set_led(config["led_mode_ok"], config["led_color_ok"])
    sleep(config["check_interval_seconds"])
