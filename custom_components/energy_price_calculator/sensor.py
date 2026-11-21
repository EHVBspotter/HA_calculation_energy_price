"""Sensors for a supplier price."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_change
from homeassistant.util import dt as dt_util

from . import calc
from .const import (
    COMMODITY_GAS,
    CONF_COMMODITY,
    CONF_EXTRA_COST,
    CONF_PRICES_ATTRIBUTE,
    CONF_SOURCE_ENTITY,
    CONF_SOURCE_INCLUDES_VAT,
    CONF_SUPPLIER,
    CONF_TAX,
    CONF_VAT,
    DEFAULT_PRICES_ATTRIBUTE,
    DOMAIN,
)


def _commodity_label(gas: bool, lang: str) -> str:
    if lang.startswith("nl"):
        return "gas" if gas else "stroom"
    return "gas" if gas else "electricity"


@dataclass(frozen=True)
class Desc:
    key: str
    name: str
    value: Callable[[list, datetime], Any]
    time_attr: Callable[[list, datetime], dict[str, Any]] | None = None


def _today(rows, now):
    return calc.stats(calc.day_rows(rows, now))


def _cur(rows, now):
    r = calc.current_row(rows, now)
    return r["price"] if r else None


def _nxt(rows, now):
    r = calc.next_row(rows, now)
    return r["price"] if r else None


def _min(rows, now):
    s = _today(rows, now)
    return s["min"]["price"] if s else None


def _max(rows, now):
    s = _today(rows, now)
    return s["max"]["price"] if s else None


def _avg(rows, now):
    s = _today(rows, now)
    return s["avg"] if s else None


def _tom_avg(rows, now):
    s = calc.stats(calc.day_rows(rows, now + timedelta(days=1)))
    return s["avg"] if s else None


DESCRIPTIONS = [
    Desc("price", "Price", _cur),
    Desc("next_price", "Next price", _nxt),
    Desc("lowest_today", "Lowest price today", _min),
    Desc("highest_today", "Highest price today", _max),
    Desc("average_today", "Average price today", _avg),
    Desc("average_tomorrow", "Average price tomorrow", _tom_avg),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    lang = hass.config.language
    async_add_entities(SupplierPriceSensor(entry, d, i == 0, lang) for i, d in enumerate(DESCRIPTIONS))


class SupplierPriceSensor(SensorEntity):
    """A price derived from the source sensor and the supplier tariff."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 4

    def __init__(self, entry: ConfigEntry, desc: Desc, main: bool, lang: str = "en") -> None:
        self._entry = entry
        self._desc = desc
        self._main = main
        c = {**entry.data, **entry.options}
        gas = c[CONF_COMMODITY] == COMMODITY_GAS
        self._attr_unique_id = f"{entry.entry_id}_{desc.key}"
        self._attr_translation_key = desc.key
        self._attr_native_unit_of_measurement = "€/m³" if gas else "€/kWh"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"{c[CONF_SUPPLIER]} ({_commodity_label(gas, lang)})",
            entry_type=None,
        )
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}

    def _conf(self) -> dict[str, Any]:
        return {**self._entry.data, **self._entry.options}

    async def async_added_to_hass(self) -> None:
        c = self._conf()
        self.async_on_remove(
            async_track_state_change_event(self.hass, [c[CONF_SOURCE_ENTITY]], self._source_changed)
        )
        # re-evaluate at every quarter, the price period may have changed
        self.async_on_remove(
            async_track_time_change(self.hass, self._tick, minute=[0, 15, 30, 45], second=1)
        )
        self._recalc()

    @callback
    def _source_changed(self, event: Event) -> None:
        self._recalc()
        self.async_write_ha_state()

    @callback
    def _tick(self, now: datetime) -> None:
        self._recalc()
        self.async_write_ha_state()

    def _recalc(self) -> None:
        c = self._conf()
        st = self.hass.states.get(c[CONF_SOURCE_ENTITY])
        now = dt_util.now()
        extra, tax, vat = float(c[CONF_EXTRA_COST]), float(c[CONF_TAX]), float(c[CONF_VAT])
        inc = bool(c.get(CONF_SOURCE_INCLUDES_VAT, False))
        if st is None or st.state in ("unknown", "unavailable"):
            self._attr_native_value = None
            self._attr_available = False
            return
        self._attr_available = True
        rows = calc.apply_supplier(
            calc.normalize_prices(st.attributes.get(c.get(CONF_PRICES_ATTRIBUTE, DEFAULT_PRICES_ATTRIBUTE))),
            extra, tax, vat, inc,
        )
        value = self._desc.value(rows, now)
        if value is None and self._desc.key == "price":
            try:  # no usable list: fall back to the source state
                value = calc.supplier_price(float(st.state), extra, tax, vat, inc)
            except ValueError:
                value = None
        self._attr_native_value = None if value is None else round(value, 6)
        attrs: dict[str, Any] = {}
        if self._main:
            attrs = {
                "source_entity": c[CONF_SOURCE_ENTITY],
                "prices": [
                    {
                        "from": r["start"].isoformat(),
                        "till": r["end"].isoformat(),
                        "time": r["start"].isoformat(),
                        "price": round(r["price"], 6),
                    }
                    for r in rows
                ],
            }
        self._attr_extra_state_attributes = attrs
