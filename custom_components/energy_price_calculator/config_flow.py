"""Config and options flow: add a supplier by hand."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    COMMODITY_ELECTRICITY,
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
    DEFAULT_VAT,
    DOMAIN,
)

_NUM = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=-10, max=10, step=0.00001, mode=selector.NumberSelectorMode.BOX
    )
)


def _schema(d: dict[str, Any], with_identity: bool) -> vol.Schema:
    fields: dict[Any, Any] = {}
    if with_identity:
        fields[vol.Required(CONF_SUPPLIER, default=d.get(CONF_SUPPLIER, ""))] = str
        fields[vol.Required(CONF_COMMODITY, default=d.get(CONF_COMMODITY, COMMODITY_ELECTRICITY))] = (
            selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[COMMODITY_ELECTRICITY, COMMODITY_GAS],
                    translation_key="commodity",
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        )
    fields[vol.Required(CONF_SOURCE_ENTITY, default=d.get(CONF_SOURCE_ENTITY, vol.UNDEFINED))] = (
        selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))
    )
    fields[vol.Required(CONF_PRICES_ATTRIBUTE, default=d.get(CONF_PRICES_ATTRIBUTE, DEFAULT_PRICES_ATTRIBUTE))] = str
    fields[vol.Required(CONF_SOURCE_INCLUDES_VAT, default=d.get(CONF_SOURCE_INCLUDES_VAT, False))] = bool
    fields[vol.Required(CONF_EXTRA_COST, default=d.get(CONF_EXTRA_COST, 0.0))] = _NUM
    fields[vol.Required(CONF_TAX, default=d.get(CONF_TAX, 0.0))] = _NUM
    fields[vol.Required(CONF_VAT, default=d.get(CONF_VAT, DEFAULT_VAT))] = selector.NumberSelector(
        selector.NumberSelectorConfig(min=0, max=100, step=0.1, mode=selector.NumberSelectorMode.BOX)
    )
    return vol.Schema(fields)


class EnergyPriceConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a supplier."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_SUPPLIER].strip().lower()}_{user_input[CONF_COMMODITY]}"
            )
            self._abort_if_unique_id_configured()
            title = f"{user_input[CONF_SUPPLIER]} ({user_input[CONF_COMMODITY]})"
            return self.async_create_entry(title=title, data=user_input)
        return self.async_show_form(step_id="user", data_schema=_schema({}, True))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return EnergyPriceOptionsFlow()


class EnergyPriceOptionsFlow(OptionsFlow):
    """Edit tariff values later (e.g. new tax rate in January)."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="init", data_schema=_schema(current, False))
