import voluptuous as vol
import os
import logging
from homeassistant import config_entries
from homeassistant.helpers.selector import selector
from homeassistant.data_entry_flow import section
from homeassistant.exceptions import ServiceValidationError
from .providers import (
    OpenAI,
    AzureOpenAI,
    Anthropic,
    Google,
    Groq,
    LocalAI,
    Ollama,
    AWSBedrock
)
from .const import (
    DOMAIN,
    CONF_PROVIDER,
    CONF_API_KEY,
    CONF_IP_ADDRESS,
    CONF_PORT,
    CONF_HTTPS,
    CONF_DEFAULT_MODEL,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    CONF_AZURE_VERSION,
    CONF_AZURE_BASE_URL,
    CONF_AZURE_DEPLOYMENT,
    CONF_CUSTOM_OPENAI_ENDPOINT,
    CONF_RETENTION_TIME,
    CONF_FALLBACK_PROVIDER,
    CONF_TIMELINE_TODAY_SUMMARY,
    CONF_TIMELINE_SUMMARY_PROMPT,
    CONF_MEMORY_PATHS,
    CONF_MEMORY_STRINGS,
    CONF_SYSTEM_PROMPT,
    CONF_TITLE_PROMPT,
    CONF_AWS_ACCESS_KEY_ID,
    CONF_AWS_SECRET_ACCESS_KEY,
    CONF_AWS_REGION_NAME,
    DEFAULT_TITLE_PROMPT,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_ANTHROPIC_MODEL,
    DEFAULT_AZURE_MODEL,
    DEFAULT_GOOGLE_MODEL,
    DEFAULT_GROQ_MODEL,
    DEFAULT_LOCALAI_MODEL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_CUSTOM_OPENAI_MODEL,
    DEFAULT_AWS_MODEL,
    DEFAULT_OPENWEBUI_MODEL,
    ENDPOINT_OPENWEBUI,
    ENDPOINT_AZURE,
    CONF_CONTEXT_WINDOW,
    CONF_KEEP_ALIVE,
    DEFAULT_SUMMARY_PROMPT,
)

_LOGGER = logging.getLogger(__name__)


class llmvisionConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):

    VERSION = 4
    MINOR_VERSION = 0

    async def handle_provider(self, provider):
        provider_steps = {
            "Timeline": self.async_step_timeline,
            "Settings": self.async_step_settings,
            "Anthropic": self.async_step_anthropic,
            "AWS Bedrock": self.async_step_aws_bedrock,
            "Azure": self.async_step_azure,
            "Custom OpenAI": self.async_step_custom_openai,
            "Google": self.async_step_google,
            "Groq": self.async_step_groq,
            "LocalAI": self.async_step_localai,
            "Ollama": self.async_step_ollama,
            "OpenAI": self.async_step_openai,
            "OpenWebUI": self.async_step_openwebui,
        }

        step_method = provider_steps.get(provider)
        if step_method:
            return await step_method()
        else:
            _LOGGER.error(f"Unknown provider: {provider}")
            return self.async_abort(reason="unknown_provider")

    async def async_step_user(self, user_input=None):
        # Check if "Settings" provider is already configured
        settings_configured = False
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data.get(CONF_PROVIDER) == "Settings":
                settings_configured = True
                break
        _LOGGER.debug(f"Settings configured flag: {settings_configured}")
        if not settings_configured:
            self.init_info = {CONF_PROVIDER: "Settings"}
            _LOGGER.debug(f"user_info: {self.init_info}")
            return await self.async_step_settings()

        data_schema = vol.Schema({
            vol.Required(CONF_PROVIDER, default="Timeline"): selector({
                "select": {
                    # Azure removed until fixed
                    "options": ["Timeline", "Anthropic", "AWS Bedrock", "Google", "Groq", "LocalAI", "Ollama", "OpenAI", "OpenWebUI", "Custom OpenAI"],
                    "mode": "dropdown",
                    "sort": False,
                    "custom_value": False
                }
            }),
        })

        if user_input is not None:
            self.init_info = user_input
            provider = user_input[CONF_PROVIDER]
            return await self.handle_provider(provider)

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            description_placeholders=user_input
        )

    async def async_step_localai(self, user_input=None):
        data_schema = vol.Schema({
            vol.Optional("connection_section"): section(
                vol.Schema({
                    vol.Required(CONF_IP_ADDRESS): str,
                    vol.Required(CONF_PORT, default=8080): int,
                    vol.Required(CONF_HTTPS, default=False): bool,
                }),
                {"collapsed": False},
            ),
            vol.Optional("model_section"): section(
                vol.Schema({
                    vol.Optional(CONF_DEFAULT_MODEL, default=DEFAULT_LOCALAI_MODEL): str,
                    vol.Optional(CONF_TEMPERATURE, default=0.5): selector({
                        "number": {
                            "min": 0,
                            "max": 1,
                            "step": 0.1,
                            "mode": "slider"
                        }
                    }),
                    vol.Optional(CONF_TOP_P, default=0.9): selector({
                        "number": {
                            "min": 0,
                            "max": 1,
                            "step": 0.1,
                            "mode": "slider"
                        }
                    }),
                }),
                {"collapsed": False},
            ),
        })

        if self.source == config_entries.SOURCE_RECONFIGURE:
            # load existing configuration and add it to the dialog
            self.init_info = self._get_reconfigure_entry().data
            # Re-nest the flat config entry data into sections
            suggested = {
                "connection_section": {
                    CONF_IP_ADDRESS: self.init_info.get(CONF_IP_ADDRESS),
                    CONF_PORT: self.init_info.get(CONF_PORT, 11434),
                    CONF_HTTPS: self.init_info.get(CONF_HTTPS, False),
                },
                "model_section": {
                    CONF_DEFAULT_MODEL: self.init_info.get(CONF_DEFAULT_MODEL, DEFAULT_LOCALAI_MODEL),
                    CONF_TEMPERATURE: self.init_info.get(CONF_TEMPERATURE, 0.5),
                    CONF_TOP_P: self.init_info.get(CONF_TOP_P, 0.9),
                },
            }
            data_schema = self.add_suggested_values_to_schema(
                data_schema, suggested
            )

        if user_input is not None:
            # save provider to user_input
            user_input[CONF_PROVIDER] = self.init_info[CONF_PROVIDER]
            # flatten dict to remove nested keys
            user_input = flatten_dict(user_input)
            try:
                localai = LocalAI(self.hass,
                                  api_key="",
                                  model=user_input[CONF_DEFAULT_MODEL],
                                  endpoint={
                                      'ip_address': user_input[CONF_IP_ADDRESS],
                                      'port': user_input[CONF_PORT],
                                      'https': user_input[CONF_HTTPS]
                                  })
                await localai.validate()
                # add the mode to user_input
                if self.source == config_entries.SOURCE_RECONFIGURE:
                    # we're reconfiguring an existing config
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        data_updates=user_input,
                    )
                else:
                    # New config entry
                    return self.async_create_entry(title=f"LocalAI ({user_input[CONF_IP_ADDRESS]})", data=user_input)
            except ServiceValidationError as e:
                _LOGGER.error(f"Validation failed: {e}")
                return self.async_show_form(
                    step_id="localai",
                    data_schema=data_schema,
                    errors={"base": "handshake_failed"}
                )

        return self.async_show_form(
            step_id="localai",
            data_schema=data_schema
        )

    async def async_step_ollama(self, user_input=None):
        data_schema = vol.Schema({
            vol.Optional("connection_section"): section(
                vol.Schema({
                    vol.Required(CONF_IP_ADDRESS): str,
                    vol.Required(CONF_PORT, default=11434): int,
                    vol.Required(CONF_HTTPS, default=False): bool,
                }),
                {"collapsed": False},
            ),
            vol.Optional("model_section"): section(
                vol.Schema({
                    vol.Required(CONF_DEFAULT_MODEL, default=DEFAULT_OLLAMA_MODEL): str,
                    vol.Optional(CONF_TEMPERATURE, default=0.5): selector({
                        "number": {
                            "min": 0,
                            "max": 1,
                            "step": 0.1,
                            "mode": "slider"
                        }
                    }),
                    vol.Optional(CONF_TOP_P, default=0.9): selector({
                        "number": {
                            "min": 0,
                            "max": 1,
                            "step": 0.1,
                            "mode": "slider"
                        }
                    }),
                }),
                {"collapsed": False},
            ),
            vol.Optional("advanced_section"): section(
                vol.Schema({
                    vol.Required(CONF_CONTEXT_WINDOW, default=2048): int,
                    vol.Optional(CONF_KEEP_ALIVE, default=5): int,
                }),
                {"collapsed": True},
            ),
        })

        if self.source == config_entries.SOURCE_RECONFIGURE:
            # load existing configuration and add it to the dialog
            self.init_info = self._get_reconfigure_entry().data

            # Re-nest the flat config entry data into sections
            suggested = {
                "connection_section": {
                    CONF_IP_ADDRESS: self.init_info.get(CONF_IP_ADDRESS),
                    CONF_PORT: self.init_info.get(CONF_PORT, 11434),
                    CONF_HTTPS: self.init_info.get(CONF_HTTPS, False),
                },
                "model_section": {
                    CONF_DEFAULT_MODEL: self.init_info.get(CONF_DEFAULT_MODEL, DEFAULT_OLLAMA_MODEL),
                    CONF_TEMPERATURE: self.init_info.get(CONF_TEMPERATURE, 0.5),
                    CONF_TOP_P: self.init_info.get(CONF_TOP_P, 0.9),
                },
                "advanced_section": {
                    CONF_CONTEXT_WINDOW: self.init_info.get(CONF_CONTEXT_WINDOW, 2048),
                    CONF_KEEP_ALIVE: self.init_info.get(CONF_KEEP_ALIVE, 5),
                }
            }
            data_schema = self.add_suggested_values_to_schema(
                data_schema, suggested
            )

        if user_input is not None:
            # save provider to user_input
            user_input[CONF_PROVIDER] = self.init_info[CONF_PROVIDER]
            # flatten dict to remove nested keys
            user_input = flatten_dict(user_input)
            try:
                ollama = Ollama(self.hass,
                                api_key="",
                                model=user_input[CONF_DEFAULT_MODEL],
                                endpoint={
                                    'ip_address': user_input[CONF_IP_ADDRESS],
                                    'port': user_input[CONF_PORT],
                                    'https': user_input[CONF_HTTPS],
                                    'keep_alive': user_input[CONF_KEEP_ALIVE],
                                    'context_window': user_input[CONF_CONTEXT_WINDOW]
                                })
                await ollama.validate()
                # add the mode to user_input
                if self.source == config_entries.SOURCE_RECONFIGURE:
                    # we're reconfiguring an existing config
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        data_updates=user_input,
                    )
                else:
                    # New config entry
                    return self.async_create_entry(title=f"Ollama ({user_input[CONF_IP_ADDRESS]})", data=user_input)
            except ServiceValidationError as e:
                _LOGGER.error(f"Validation failed: {e}")
                return self.async_show_form(
                    step_id="ollama",
                    data_schema=data_schema,
                    errors={"base": "handshake_failed"}
                )

        return self.async_show_form(
            step_id="ollama",
            data_schema=data_schema,
        )

    async def async_step_openwebui(self, user_input=None):
        data_schema = vol.Schema({
            vol.Optional("connection_section"): section(
                vol.Schema({
                    vol.Required(CONF_API_KEY): selector({
                        "text": {
                            "type": "password"
                        }
                    }),
                    vol.Required(CONF_IP_ADDRESS): str,
                    vol.Required(CONF_PORT, default=3000): int,
                    vol.Required(CONF_HTTPS, default=False): bool,
                }),
                {"collapsed": False},
            ),
            vol.Optional("model_section"): section(
                vol.Schema({
                    vol.Required(CONF_DEFAULT_MODEL, default=DEFAULT_OPENWEBUI_MODEL): str,
                    vol.Optional(CONF_TEMPERATURE, default=0.5): selector({
                        "number": {
                            "min": 0,
                            "max": 1,
                            "step": 0.1,
                            "mode": "slider"
                        }
                    }),
                    vol.Optional(CONF_TOP_P, default=0.9): selector({
                        "number": {
                            "min": 0,
                            "max": 1,
                            "step": 0.1,
                            "mode": "slider"
                        }
                    }),
                }),
                {"collapsed": False},
            ),
        })

        if self.source == config_entries.SOURCE_RECONFIGURE:
            # load existing configuration and add it to the dialog
            self.init_info = self._get_reconfigure_entry().data
            # Re-nest the flat config entry data into sections
            suggested = {
                "connection_section": {
                    CONF_API_KEY: self.init_info.get(CONF_API_KEY),
                    CONF_IP_ADDRESS: self.init_info.get(CONF_IP_ADDRESS),
                    CONF_PORT: self.init_info.get(CONF_PORT, 3000),
                    CONF_HTTPS: self.init_info.get(CONF_HTTPS, False),
                },
                "model_section": {
                    CONF_DEFAULT_MODEL: self.init_info.get(CONF_DEFAULT_MODEL, DEFAULT_OPENWEBUI_MODEL),
                    CONF_TEMPERATURE: self.init_info.get(CONF_TEMPERATURE, 0.5),
                    CONF_TOP_P: self.init_info.get(CONF_TOP_P, 0.9),
                }
            }
            data_schema = self.add_suggested_values_to_schema(
                data_schema, suggested
            )

        if user_input is not None:
            # save provider to user_input
            user_input[CONF_PROVIDER] = self.init_info[CONF_PROVIDER]
            # flatten dict to remove nested keys
            user_input = flatten_dict(user_input)
            try:
                endpoint = ENDPOINT_OPENWEBUI.format(
                    ip_address=user_input[CONF_IP_ADDRESS],
                    port=user_input[CONF_PORT],
                    protocol="https" if user_input[CONF_HTTPS] else "http"
                )
                openwebui = OpenAI(hass=self.hass,
                                   api_key=user_input[CONF_API_KEY],
                                   model=user_input[CONF_DEFAULT_MODEL],
                                   endpoint={
                                       'base_url': endpoint
                                   })
                await openwebui.validate()
                # add the mode to user_input
                if self.source == config_entries.SOURCE_RECONFIGURE:
                    # we're reconfiguring an existing config
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        data_updates=user_input,
                    )
                else:
                    # New config entry
                    return self.async_create_entry(title=f"OpenWebUI ({user_input[CONF_IP_ADDRESS]})", data=user_input)
            except ServiceValidationError as e:
                _LOGGER.error(f"Validation failed: {e}")
                return self.async_show_form(
                    step_id="openwebui",
                    data_schema=data_schema,
                    errors={"base": "handshake_failed"}
                )

        return self.async_show_form(
            step_id="openwebui",
            data_schema=data_schema,
        )

    async def async_step_openai(self, user_input=None):
        data_schema = vol.Schema({
            vol.Optional("connection_section"): section(
                vol.Schema({
                    vol.Required(CONF_API_KEY): selector({
                        "text": {
                            "type": "password"
                        }
                    })
                }),
                {"collapsed": False},
            ),
            vol.Optional("model_section"): section(
                vol.Schema({
                    vol.Required(CONF_DEFAULT_MODEL, default=DEFAULT_OPENAI_MODEL): str,
                    vol.Optional(CONF_TEMPERATURE, default=0.5): selector({
                        "number": {
                            "min": 0,
                            "max": 1,
                            "step": 0.1,
                            "mode": "slider"
                        }
                    }),
                    vol.Optional(CONF_TOP_P, default=0.9): selector({
                        "number": {
                            "min": 0,
                            "max": 1,
                            "step": 0.1,
                            "mode": "slider"
                        }
                    }),
                }),
                {"collapsed": False},
            ),
        })

        if self.source == config_entries.SOURCE_RECONFIGURE:
            # load existing configuration and add it to the dialog
            self.init_info = self._get_reconfigure_entry().data
            # Re-nest the flat config entry data into sections
            suggested = {
                "connection_section": {
                    CONF_API_KEY: self.init_info.get(CONF_API_KEY)
                },
                "model_section": {
                    CONF_DEFAULT_MODEL: self.init_info.get(CONF_DEFAULT_MODEL, DEFAULT_OPENAI_MODEL),
                    CONF_TEMPERATURE: self.init_info.get(CONF_TEMPERATURE, 0.5),
                    CONF_TOP_P: self.init_info.get(CONF_TOP_P, 0.9),
                }
            }
            data_schema = self.add_suggested_values_to_schema(
                data_schema, suggested
            )

        if user_input is not None:
            # save provider to user_input
            user_input[CONF_PROVIDER] = self.init_info[CONF_PROVIDER]
            # flatten dict to remove nested keys
            user_input = flatten_dict(user_input)
            try:
                openai = OpenAI(self.hass,
                                api_key=user_input[CONF_API_KEY],
                                model=[CONF_DEFAULT_MODEL]
                                )
                await openai.validate()
                # add the mode to user_input
                user_input[CONF_PROVIDER] = self.init_info[CONF_PROVIDER]
                if self.source == config_entries.SOURCE_RECONFIGURE:
                    # we're reconfiguring an existing config
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        data_updates=user_input,
                    )
                else:
                    # New config entry
                    return self.async_create_entry(title="OpenAI", data=user_input)
            except ServiceValidationError as e:
                _LOGGER.error(f"Validation failed: {e}")
                return self.async_show_form(
                    step_id="openai",
                    data_schema=data_schema,
                    errors={"base": "handshake_failed"}
                )

        return self.async_show_form(
            step_id="openai",
            data_schema=data_schema,
        )

    async def async_step_azure(self, user_input=None):
        data_schema = vol.Schema({
            vol.Optional("connection_section"): section(
                vol.Schema({
                    vol.Required(CONF_API_KEY): selector({
                        "text": {
                            "type": "password"
                        }
                    }),
                    vol.Required(CONF_AZURE_BASE_URL, default="https://domain.openai.azure.com/"): str,
                    vol.Required(CONF_AZURE_DEPLOYMENT, default="deployment"): str,
                    vol.Required(CONF_AZURE_VERSION, default="2024-10-01-preview"): str,
                }),
                {"collapsed": False},
            ),
            vol.Optional("model_section"): section(
                vol.Schema({
                    vol.Required(CONF_DEFAULT_MODEL, default=DEFAULT_AZURE_MODEL): str,
                    vol.Optional(CONF_TEMPERATURE, default=0.5): selector({
                        "number": {
                            "min": 0,
                            "max": 1,
                            "step": 0.1,
                            "mode": "slider"
                        }
                    }),
                    vol.Optional(CONF_TOP_P, default=0.9): selector({
                        "number": {
                            "min": 0,
                            "max": 1,
                            "step": 0.1,
                            "mode": "slider"
                        }
                    }),
                }),
                {"collapsed": False},
            )
        })

        if self.source == config_entries.SOURCE_RECONFIGURE:
            # load existing configuration and add it to the dialog
            self.init_info = self._get_reconfigure_entry().data
            # Re-nest the flat config entry data into sections
            suggested = {
                "connection_section": {
                    CONF_API_KEY: self.init_info.get(CONF_API_KEY)
                },
                "model_section": {
                    CONF_DEFAULT_MODEL: self.init_info.get(CONF_DEFAULT_MODEL, DEFAULT_AZURE_MODEL),
                    CONF_TEMPERATURE: self.init_info.get(CONF_TEMPERATURE, 0.5),
                    CONF_TOP_P: self.init_info.get(CONF_TOP_P, 0.9),
                }
            }
            data_schema = self.add_suggested_values_to_schema(
                data_schema, suggested
            )

        if user_input is not None:
            # save provider to user_input
            user_input[CONF_PROVIDER] = self.init_info[CONF_PROVIDER]
            # flatten dict to remove nested keys
            user_input = flatten_dict(user_input)
            try:
                azure = AzureOpenAI(self.hass,
                                    api_key=user_input[CONF_API_KEY],
                                    model=user_input[CONF_DEFAULT_MODEL],
                                    endpoint={
                                        'base_url': ENDPOINT_AZURE,
                                        'endpoint': user_input[CONF_AZURE_BASE_URL],
                                        'deployment': user_input[CONF_AZURE_DEPLOYMENT],
                                        'api_version': user_input[CONF_AZURE_VERSION]
                                    })
                await azure.validate()
                # add the mode to user_input
                user_input[CONF_PROVIDER] = self.init_info[CONF_PROVIDER]
                if self.source == config_entries.SOURCE_RECONFIGURE:
                    # we're reconfiguring an existing config
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        data_updates=user_input,
                    )
                else:
                    # New config entry
                    return self.async_create_entry(title="Azure", data=user_input)
            except ServiceValidationError as e:
                _LOGGER.error(f"Validation failed: {e}")
                return self.async_show_form(
                    step_id="azure",
                    data_schema=data_schema,
                    errors={"base": "handshake_failed"}
                )

        return self.async_show_form(
            step_id="azure",
            data_schema=data_schema,
        )

    async def async_step_anthropic(self, user_input=None):
        data_schema = vol.Schema({
            vol.Optional("connection_section"): section(
                vol.Schema({
                    vol.Required(CONF_API_KEY): selector({
                        "text": {
                            "type": "password"
                        }
                    })
                }),
                {"collapsed": False},
            ),
            vol.Optional("model_section"): section(
                vol.Schema({
                    vol.Required(CONF_DEFAULT_MODEL, default=DEFAULT_ANTHROPIC_MODEL): str,
                    vol.Optional(CONF_TEMPERATURE, default=0.5): selector({
                        "number": {
                            "min": 0,
                            "max": 1,
                            "step": 0.1,
                            "mode": "slider"
                        }
                    }),
                    vol.Optional(CONF_TOP_P, default=0.9): selector({
                        "number": {
                            "min": 0,
                            "max": 1,
                            "step": 0.1,
                            "mode": "slider"
                        }
                    }),
                }),
                {"collapsed": False},
            )
        })

        if self.source == config_entries.SOURCE_RECONFIGURE:
            # load existing configuration and add it to the dialog
            self.init_info = self._get_reconfigure_entry().data
            # Re-nest the flat config entry data into sections
            suggested = {
                "connection_section": {
                    CONF_API_KEY: self.init_info.get(CONF_API_KEY)
                },
                "model_section": {
                    CONF_DEFAULT_MODEL: self.init_info.get(CONF_DEFAULT_MODEL, DEFAULT_ANTHROPIC_MODEL),
                    CONF_TEMPERATURE: self.init_info.get(CONF_TEMPERATURE, 0.5),
                    CONF_TOP_P: self.init_info.get(CONF_TOP_P, 0.9),
                }
            }
            data_schema = self.add_suggested_values_to_schema(
                data_schema, suggested
            )

        if user_input is not None:
            # save provider to user_input
            user_input[CONF_PROVIDER] = self.init_info[CONF_PROVIDER]
            # flatten dict to remove nested keys
            user_input = flatten_dict(user_input)
            try:
                anthropic = Anthropic(self.hass,
                                      api_key=user_input[CONF_API_KEY],
                                      model=user_input[CONF_DEFAULT_MODEL]
                                      )
                await anthropic.validate()
                # add the mode to user_input
                user_input[CONF_PROVIDER] = self.init_info[CONF_PROVIDER]
                if self.source == config_entries.SOURCE_RECONFIGURE:
                    # we're reconfiguring an existing config
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        data_updates=user_input,
                    )
                else:
                    # New config entry
                    return self.async_create_entry(title="Anthropic Claude", data=user_input)
            except ServiceValidationError as e:
                _LOGGER.error(f"Validation failed: {e}")
                return self.async_show_form(
                    step_id="anthropic",
                    data_schema=data_schema,
                    errors={"base": "empty_api_key"}
                )

        return self.async_show_form(
            step_id="anthropic",
            data_schema=data_schema,
        )

    async def async_step_google(self, user_input=None):
        data_schema = vol.Schema({
            vol.Optional("connection_section"): section(
                vol.Schema({
                    vol.Required(CONF_API_KEY): selector({
                        "text": {
                            "type": "password"
                        }
                    })
                }),
                {"collapsed": False},
            ),
            vol.Optional("model_section"): section(
                vol.Schema({
                    vol.Required(CONF_DEFAULT_MODEL, default=DEFAULT_GOOGLE_MODEL): str,
                    vol.Optional(CONF_TEMPERATURE, default=0.5): selector({
                        "number": {
                            "min": 0,
                            "max": 1,
                            "step": 0.1,
                            "mode": "slider"
                        }
                    }),
                    vol.Optional(CONF_TOP_P, default=0.9): selector({
                        "number": {
                            "min": 0,
                            "max": 1,
                            "step": 0.1,
                            "mode": "slider"
                        }
                    }),
                }),
                {"collapsed": False},
            )
        })

        if self.source == config_entries.SOURCE_RECONFIGURE:
            # load existing configuration and add it to the dialog
            self.init_info = self._get_reconfigure_entry().data
            # Re-nest the flat config entry data into sections
            suggested = {
                "connection_section": {
                    CONF_API_KEY: self.init_info.get(CONF_API_KEY)
                },
                "model_section": {
                    CONF_DEFAULT_MODEL: self.init_info.get(CONF_DEFAULT_MODEL, DEFAULT_GOOGLE_MODEL),
                    CONF_TEMPERATURE: self.init_info.get(CONF_TEMPERATURE, 0.5),
                    CONF_TOP_P: self.init_info.get(CONF_TOP_P, 0.9),
                }
            }
            data_schema = self.add_suggested_values_to_schema(
                data_schema, suggested
            )

        if user_input is not None:
            # save provider to user_input
            user_input[CONF_PROVIDER] = self.init_info[CONF_PROVIDER]
            # flatten dict to remove nested keys
            user_input = flatten_dict(user_input)
            try:
                google = Google(self.hass,
                                api_key=user_input[CONF_API_KEY],
                                model=user_input[CONF_DEFAULT_MODEL],
                                )
                await google.validate()
                # add the mode to user_input
                user_input[CONF_PROVIDER] = self.init_info[CONF_PROVIDER]
                if self.source == config_entries.SOURCE_RECONFIGURE:
                    # we're reconfiguring an existing config
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        data_updates=user_input,
                    )
                else:
                    # New config entry
                    return self.async_create_entry(title="Google Gemini", data=user_input)
            except ServiceValidationError as e:
                _LOGGER.error(f"Validation failed: {e}")
                return self.async_show_form(
                    step_id="google",
                    data_schema=data_schema,
                    errors={"base": "empty_api_key"}
                )

        return self.async_show_form(
            step_id="google",
            data_schema=data_schema,
        )

    async def async_step_groq(self, user_input=None):
        data_schema = vol.Schema({
            vol.Optional("connection_section"): section(
                vol.Schema({
                    vol.Required(CONF_API_KEY): selector({
                        "text": {
                            "type": "password"
                        }
                    })
                }),
                {"collapsed": False},
            ),
            vol.Optional("model_section"): section(
                vol.Schema({
                    vol.Required(CONF_DEFAULT_MODEL, default=DEFAULT_GROQ_MODEL): str,
                    vol.Optional(CONF_TEMPERATURE, default=0.5): selector({
                        "number": {
                            "min": 0,
                            "max": 1,
                            "step": 0.1,
                            "mode": "slider"
                        }
                    }),
                    vol.Optional(CONF_TOP_P, default=0.9): selector({
                        "number": {
                            "min": 0,
                            "max": 1,
                            "step": 0.1,
                            "mode": "slider"
                        }
                    }),
                }),
                {"collapsed": False},
            )
        })

        if self.source == config_entries.SOURCE_RECONFIGURE:
            # load existing configuration and add it to the dialog
            self.init_info = self._get_reconfigure_entry().data
            # Re-nest the flat config entry data into sections
            suggested = {
                "connection_section": {
                    CONF_API_KEY: self.init_info.get(CONF_API_KEY)
                },
                "model_section": {
                    CONF_DEFAULT_MODEL: self.init_info.get(CONF_DEFAULT_MODEL, DEFAULT_GROQ_MODEL),
                    CONF_TEMPERATURE: self.init_info.get(CONF_TEMPERATURE, 0.5),
                    CONF_TOP_P: self.init_info.get(CONF_TOP_P, 0.9),
                }
            }
            data_schema = self.add_suggested_values_to_schema(
                data_schema, suggested
            )

        if user_input is not None:
            # save provider to user_input
            user_input[CONF_PROVIDER] = self.init_info[CONF_PROVIDER]
            # flatten dict to remove nested keys
            user_input = flatten_dict(user_input)
            try:
                groq = Groq(self.hass,
                            api_key=user_input[CONF_API_KEY],
                            model=user_input[CONF_DEFAULT_MODEL]
                            )
                await groq.validate()
                # add the mode to user_input
                user_input[CONF_PROVIDER] = self.init_info[CONF_PROVIDER]
                if self.source == config_entries.SOURCE_RECONFIGURE:
                    # we're reconfiguring an existing config
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        data_updates=user_input,
                    )
                else:
                    # New config entry
                    return self.async_create_entry(title="Groq", data=user_input)
            except ServiceValidationError as e:
                _LOGGER.error(f"Validation failed: {e}")
                return self.async_show_form(
                    step_id="groq",
                    data_schema=data_schema,
                    errors={"base": "handshake_failed"}
                )

        return self.async_show_form(
            step_id="groq",
            data_schema=data_schema,
        )

    async def async_step_custom_openai(self, user_input=None):
        data_schema = vol.Schema({
            vol.Optional("connection_section"): section(
                vol.Schema({
                    vol.Required(CONF_API_KEY): selector({
                        "text": {
                            "type": "password"
                        }
                    }),
                    vol.Required(CONF_CUSTOM_OPENAI_ENDPOINT, default="http://replace.with.your.host.com/v1/chat/completions"): str,
                }),
                {"collapsed": False},
            ),
            vol.Optional("model_section"): section(
                vol.Schema({
                    vol.Required(CONF_DEFAULT_MODEL, default=DEFAULT_CUSTOM_OPENAI_MODEL): str,
                    vol.Optional(CONF_TEMPERATURE, default=0.5): selector({
                        "number": {
                            "min": 0,
                            "max": 1,
                            "step": 0.1,
                            "mode": "slider"
                        }
                    }),
                    vol.Optional(CONF_TOP_P, default=0.9): selector({
                        "number": {
                            "min": 0,
                            "max": 1,
                            "step": 0.1,
                            "mode": "slider"
                        }
                    }),
                }),
                {"collapsed": False},
            )
        })

        if self.source == config_entries.SOURCE_RECONFIGURE:
            # load existing configuration and add it to the dialog
            self.init_info = self._get_reconfigure_entry().data
            # Re-nest the flat config entry data into sections
            suggested = {
                "connection_section": {
                    CONF_API_KEY: self.init_info.get(CONF_API_KEY)
                },
                "model_section": {
                    CONF_DEFAULT_MODEL: self.init_info.get(CONF_DEFAULT_MODEL, DEFAULT_CUSTOM_OPENAI_MODEL),
                    CONF_TEMPERATURE: self.init_info.get(CONF_TEMPERATURE, 0.5),
                    CONF_TOP_P: self.init_info.get(CONF_TOP_P, 0.9),
                }
            }
            data_schema = self.add_suggested_values_to_schema(
                data_schema, suggested
            )

        if user_input is not None:
            # save provider to user_input
            user_input[CONF_PROVIDER] = self.init_info[CONF_PROVIDER]
            # flatten dict to remove nested keys
            user_input = flatten_dict(user_input)
            try:
                custom_openai = OpenAI(self.hass,
                                       api_key=user_input[CONF_API_KEY],
                                       model=user_input[CONF_DEFAULT_MODEL],
                                       endpoint={
                                           'base_url': user_input[CONF_CUSTOM_OPENAI_ENDPOINT]
                                       })
                await custom_openai.validate()
                # add the mode to user_input
                user_input[CONF_PROVIDER] = self.init_info[CONF_PROVIDER]
                if self.source == config_entries.SOURCE_RECONFIGURE:
                    # we're reconfiguring an existing config
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        data_updates=user_input,
                    )
                else:
                    # New config entry
                    return self.async_create_entry(title="Custom OpenAI compatible Provider", data=user_input)
            except ServiceValidationError as e:
                _LOGGER.error(f"Validation failed: {e}")
                return self.async_show_form(
                    step_id="custom_openai",
                    data_schema=data_schema,
                    errors={"base": "handshake_failed"}
                )

        return self.async_show_form(
            step_id="custom_openai",
            data_schema=data_schema,
        )

    async def async_step_aws_bedrock(self, user_input=None):
        data_schema = vol.Schema({
            vol.Optional("connection_section"): section(
                vol.Schema({
                    vol.Required(CONF_AWS_ACCESS_KEY_ID): selector({
                        "text": {
                            "type": "password"
                        }
                    }),
                    vol.Required(CONF_AWS_SECRET_ACCESS_KEY): selector({
                        "text": {
                            "type": "password"
                        }
                    }),
                    vol.Required(CONF_AWS_REGION_NAME, default="us-east-1"): str,
                }),
                {"collapsed": False},
            ),
            vol.Optional("model_section"): section(
                vol.Schema({
                    vol.Required(CONF_DEFAULT_MODEL, default=DEFAULT_AWS_MODEL): str,
                    vol.Optional(CONF_TEMPERATURE, default=0.5): selector({
                        "number": {
                            "min": 0,
                            "max": 1,
                            "step": 0.1,
                            "mode": "slider"
                        }
                    }),
                    vol.Optional(CONF_TOP_P, default=0.9): selector({
                        "number": {
                            "min": 0,
                            "max": 1,
                            "step": 0.1,
                            "mode": "slider"
                        }
                    }),
                }),
                {"collapsed": False},
            )
        })

        if self.source == config_entries.SOURCE_RECONFIGURE:
            # load existing configuration and add it to the dialog
            self.init_info = self._get_reconfigure_entry().data
            # Re-nest the flat config entry data into sections
            suggested = {
                "connection_section": {
                    CONF_AWS_ACCESS_KEY_ID: self.init_info.get(CONF_AWS_ACCESS_KEY_ID),
                    CONF_AWS_SECRET_ACCESS_KEY: self.init_info.get(CONF_AWS_SECRET_ACCESS_KEY),
                    CONF_AWS_REGION_NAME: self.init_info.get(CONF_AWS_REGION_NAME, "us-east-1"),
                },
                "model_section": {
                    CONF_DEFAULT_MODEL: self.init_info.get(CONF_DEFAULT_MODEL, DEFAULT_AWS_MODEL),
                    CONF_TEMPERATURE: self.init_info.get(CONF_TEMPERATURE, 0.5),
                    CONF_TOP_P: self.init_info.get(CONF_TOP_P, 0.9),
                }
            }
            data_schema = self.add_suggested_values_to_schema(
                data_schema, suggested
            )

        if user_input is not None:
            # save provider to user_input
            user_input[CONF_PROVIDER] = self.init_info[CONF_PROVIDER]
            # flatten dict to remove nested keys
            user_input = flatten_dict(user_input)
            try:
                aws_bedrock = AWSBedrock(hass=self.hass,
                                         aws_access_key_id=user_input[CONF_AWS_ACCESS_KEY_ID],
                                         aws_secret_access_key=user_input[CONF_AWS_SECRET_ACCESS_KEY],
                                         aws_region_name=user_input[CONF_AWS_REGION_NAME],
                                         model=user_input[CONF_DEFAULT_MODEL],
                                         )
                await aws_bedrock.validate()
                # add the mode to user_input
                user_input[CONF_PROVIDER] = self.init_info[CONF_PROVIDER]
                if self.source == config_entries.SOURCE_RECONFIGURE:
                    # we're reconfiguring an existing config
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        data_updates=user_input,
                    )
                else:
                    # New config entry
                    return self.async_create_entry(title="AWS Bedrock Provider", data=user_input)
            except ServiceValidationError as e:
                _LOGGER.error(f"Validation failed: {e}")
                return self.async_show_form(
                    step_id="aws_bedrock",
                    data_schema=data_schema,
                    errors={"base": "handshake_failed"}
                )

        return self.async_show_form(
            step_id="aws_bedrock",
            data_schema=data_schema,
        )

    async def async_step_timeline(self, user_input=None):
        data_schema = vol.Schema({
            vol.Required(CONF_RETENTION_TIME, default=7): int,
            vol.Required(CONF_TIMELINE_TODAY_SUMMARY, default=True): bool,
            vol.Optional(CONF_TIMELINE_SUMMARY_PROMPT, default=DEFAULT_SUMMARY_PROMPT): selector({
                "text": {
                    "multiline": True,
                    "multiple": False
                }
            }),
        })

        if self.source == config_entries.SOURCE_RECONFIGURE:
            # load existing configuration and add it to the dialog
            self.init_info = self._get_reconfigure_entry().data
            data_schema = self.add_suggested_values_to_schema(
                data_schema, self.init_info
            )

        if user_input is not None:
            user_input[CONF_PROVIDER] = self.init_info[CONF_PROVIDER]
            try:
                for uid in self.hass.data[DOMAIN]:
                    if 'retention_time' in self.hass.data[DOMAIN][uid]:
                        self.async_abort(reason="already_configured")
            except KeyError:
                # no existing configuration, continue
                pass
            if self.source == config_entries.SOURCE_RECONFIGURE:
                # we're reconfiguring an existing config
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates=user_input,
                )
            else:
                # New config entry
                return self.async_create_entry(title="LLM Vision Timeline", data=user_input)

        return self.async_show_form(
            step_id="timeline",
            data_schema=data_schema,
        )

    async def async_step_settings(self, user_input=None):
        _LOGGER.debug("Settings step")
        data_schema = vol.Schema({
            vol.Optional("general_section"): section(
                # Dropdown for selecting fallback provider (fetch any existing providers)
                vol.Schema({
                    vol.Optional(CONF_FALLBACK_PROVIDER, default=""): selector({
                        "select": {
                            "options": (
                                [{"label": "No Fallback", "value": ""}] +
                                [
                                    {"label": self.hass.data[DOMAIN][provider].get(
                                        "provider", provider), "value": provider}
                                    for provider in (self.hass.data.get(DOMAIN) or {}).keys()
                                    if provider != self.init_info[CONF_PROVIDER]
                                ]
                            )
                        }
                    })
                }),
                {"collapsed": False},
            ),
            vol.Optional("memory_section"): section(
                vol.Schema({
                    vol.Optional(CONF_MEMORY_PATHS): selector({
                        "text": {
                            "multiline": False,
                            "multiple": True
                        }
                    }),
                    vol.Optional(CONF_MEMORY_STRINGS): selector({
                        "text": {
                            "multiline": False,
                            "multiple": True
                        }
                    }),
                    vol.Optional(CONF_SYSTEM_PROMPT, default=DEFAULT_SYSTEM_PROMPT): selector({
                        "text": {
                            "multiline": True,
                            "multiple": False
                        }
                    }),
                    vol.Optional(CONF_TITLE_PROMPT, default=DEFAULT_TITLE_PROMPT): selector({
                        "text": {
                            "multiline": True,
                            "multiple": False
                        }
                    }),
                }),
                {"collapsed": True},
            )
        })

        if self.source == config_entries.SOURCE_RECONFIGURE:
            _LOGGER.debug("Reconfigure Settings step")
            # load existing configuration and add it to the dialog
            self.init_info = self._get_reconfigure_entry().data
            # Re-nest the flat config entry data into sections
            suggested = {
                "general_section": {
                    CONF_FALLBACK_PROVIDER: self.init_info.get(
                        CONF_FALLBACK_PROVIDER, "")
                },
                "memory_section": {
                    CONF_MEMORY_PATHS: self.init_info.get(CONF_MEMORY_PATHS),
                    CONF_MEMORY_STRINGS: self.init_info.get(CONF_MEMORY_STRINGS),
                    CONF_SYSTEM_PROMPT: self.init_info.get(CONF_SYSTEM_PROMPT, DEFAULT_SYSTEM_PROMPT),
                    CONF_TITLE_PROMPT: self.init_info.get(CONF_TITLE_PROMPT, DEFAULT_TITLE_PROMPT),
                }
            }
            data_schema = self.add_suggested_values_to_schema(
                data_schema, suggested
            )

        if user_input is not None:
            user_input[CONF_PROVIDER] = self.init_info[CONF_PROVIDER]

            try:
                for uid in self.hass.data[DOMAIN]:
                    if 'system_prompt' in self.hass.data[DOMAIN][uid]:
                        self.async_abort(reason="already_configured")
            except KeyError:
                # no existing configuration, continue
                pass

            errors = {}
            if len(user_input.get(CONF_MEMORY_PATHS, [])) != len(user_input.get(CONF_MEMORY_STRINGS, [])):
                errors = {"base": "mismatched_lengths"}
            for path in user_input.get(CONF_MEMORY_PATHS, []):
                if not os.path.exists(path):
                    errors = {"base": "invalid_image_path"}

            if errors:
                return self.async_show_form(
                    step_id="settings",
                    data_schema=data_schema,
                    errors=errors
                )
            if self.source == config_entries.SOURCE_RECONFIGURE:
                # we're reconfiguring an existing config
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates=user_input,
                )
            else:
                # New config entry
                return self.async_create_entry(title="LLM Vision Settings", data=user_input)

        return self.async_show_form(
            step_id="settings",
            data_schema=data_schema,
        )

    async def async_step_reconfigure(self, user_input):
        data = self._get_reconfigure_entry().data
        provider = data[CONF_PROVIDER]
        self.init_info = data
        return await self.handle_provider(provider)


# Helper functions
def flatten_dict(data: dict) -> dict:
    """Flatten one level of nested dicts (from section fields) into the top-level dict."""
    flat = {}
    for key, value in data.items():
        if isinstance(value, dict):
            flat.update(value)
        else:
            flat[key] = value
    return flat
