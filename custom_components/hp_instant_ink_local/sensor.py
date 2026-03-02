"""
@ Author      : Steven Tierney
@ Description : HP Instant Ink Local - It queries the local HP Printer to obtain the page usage & Ink Levels
@ Notes.      : The following resources from the XML are used:
                  - Subscription Impressions
                  - Total Impressions
                  - Percentage Ink Level Remaining (Cyan)
                  - Percentage Ink Level Remaining (Magenta)
                  - Percentage Ink Level Remaining (Yellow)
                  - Percentage Ink Level Remaining (Black)

To install do the following

1. Copy this file and place it in your 'Home Assistant Config folder/custom_components/hp_instant_ink_local' folder.

2. On Line 41 below, update the URL to the XML page of your printer.

3. Add the following paragraph to the configuration in sensor.yaml:

- platform: hp_instant_ink_local
  resources:
    - sp
    - tp
    - cy
    - mg
    - yl
    - br

"""

import logging
import xmltodict
from datetime import datetime, timedelta

import homeassistant.helpers.config_validation as cv
import requests
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME, CONF_RESOURCES
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'http://192.168.10.6/DevMgmt/ProductUsageDyn.xml'

ATTRIBUTION = 'Data provided by HP Printer'
DEFAULT_ICON = 'mdi:printer'

SCAN_INTERVAL = timedelta(seconds=30)
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)

"""
sp = Subscription Pages
tp = Total Pages
cy = Cyan Ink Remaining
mg = Magenta Ink Remaining
yl = Yellow Ink Remaining
br = Black Ink Remaining
cr = Colour Remaining (minimum of cy, mg, yl)
"""

SENSOR_TYPES = {
    'sp': ['HP Printer Subscription Pages', ' '],
    'tp': ['HP Printer Total Pages', ' '],
    'cy': ['HP Printer Cyan Remaining', ' '],
    'mg': ['HP Printer Magenta Remaining', ' '],
    'yl': ['HP Printer Yellow Remaining', ' '],
    'br': ['HP Printer Black Remaining', ' '],
    'cr': ['HP Printer Colour Remaining', ' '],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RESOURCES):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the HP Instant Ink sensor."""
    rest = HPPrinterData(_RESOURCE)
    sensors = []
    for resource in config[CONF_RESOURCES]:
        sensors.append(HPPrinterSensor(resource, rest))

    add_devices(sensors, True)


class HPPrinterSensor(Entity):
    """Implementing the HP Printer sensor."""

    def __init__(self, sensor_type, rest):
        """Initialize the sensor."""
        self._name = SENSOR_TYPES[sensor_type][0]
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._icon = DEFAULT_ICON
        self.rest = rest
        self.type = sensor_type
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name.rstrip()

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return DEFAULT_ICON

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        attr = {}
        attr[ATTR_ATTRIBUTION] = ATTRIBUTION
        return attr

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self.rest.available

    def update(self):
        """Update current data."""
        self.rest.update()
        try:
            if self.type == 'cr':
                # Colour remaining is the minimum of the three individual colour cartridges
                self._state = min(
                    int(self.rest.data['cy']),
                    int(self.rest.data['mg']),
                    int(self.rest.data['yl']),
                )
            else:
                self._state = int(self.rest.data[self.type])
        except (TypeError, KeyError):
            self._state = 'NA'


class HPPrinterData(object):
    """Gets data from the printer."""

    def __init__(self, resource):
        """Initialize the data object."""
        self._resource = resource
        self.data = {}
        self.available = True

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from the printer."""
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.77 Safari/537.36'}
        try:
            r = requests.get(self._resource, headers=headers, timeout=10)
            doc = xmltodict.parse(r.content)
            printer = doc["pudyn:ProductUsageDyn"]["pudyn:PrinterSubunit"]

            data = {}
            data['sp'] = printer["pudyn:SubscriptionImpressions"]
            data['tp'] = printer["dd:TotalImpressions"]["#text"]

            for consumable in doc["pudyn:ProductUsageDyn"]["pudyn:ConsumableSubunit"]["pudyn:Consumable"]:
                color = consumable["dd:MarkerColor"]
                level = consumable["dd:ConsumableRawPercentageLevelRemaining"]
                if color == "Cyan":
                    data['cy'] = level
                elif color == "Magenta":
                    data['mg'] = level
                elif color == "Yellow":
                    data['yl'] = level
                elif color == "Black":
                    data['br'] = level

            self.data = data
            self.available = True
        except requests.exceptions.ConnectionError:
            _LOGGER.error('Connection error')
            self.data = {}
            self.available = False
