#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : gaode_weather.py.py
"""
import json
import os
from typing import Any, Type

import requests
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.tools import BaseTool

from internal.lib.helper import add_attribute


class GaodeWeatherArgsSchema(BaseModel):
    city: str = Field(description="The target city for which to fetch the weather forecast, e.g., Guangzhou")


class GaodeWeatherTool(BaseTool):
    """Fetch weather information for a given city."""
    name = "gaode_weather"
    description = "A tool to use when you want to query the weather or ask weather-related questions."
    args_schema: Type[BaseModel] = GaodeWeatherArgsSchema

    def _run(self, *args: Any, **kwargs: Any) -> str:
        """Call the Gaode API to retrieve the weather forecast for the specified city."""
        try:
            # 1. Retrieve the Gaode API key from environment variables
            gaode_api_key = os.getenv("GAODE_API_KEY")
            if not gaode_api_key:
                return "Gaode API key is not configured."

            # 2. Extract the city name from the arguments
            city = kwargs.get("city", "")
            api_domain = "https://restapi.amap.com/v3"
            session = requests.session()

            # 3. Lookup the administrative code (adcode) for the city
            city_response = session.get(
                f"{api_domain}/config/district",
                params={"key": gaode_api_key, "keywords": city, "subdistrict": 0},
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
            city_response.raise_for_status()
            city_data = city_response.json()
            if city_data.get("info") == "OK":
                ad_code = city_data["districts"][0]["adcode"]

                # 4. Query the weather forecast using the adcode
                weather_response = session.get(
                    f"{api_domain}/weather/weatherInfo",
                    params={"key": gaode_api_key, "city": ad_code, "extensions": "all"},
                    headers={"Content-Type": "application/json; charset=utf-8"},
                )
                weather_response.raise_for_status()
                weather_data = weather_response.json()
                if weather_data.get("info") == "OK":
                    # 5. Return the weather data as a JSON string
                    return json.dumps(weather_data)

            return f"Failed to retrieve weather forecast for {city}."
        except Exception:
            return f"Failed to retrieve weather forecast for {kwargs.get('city', '')}."


@add_attribute("args_schema", GaodeWeatherArgsSchema)
def gaode_weather(**kwargs) -> BaseTool:
    """Return a Gaode weather forecast querying tool."""
    return GaodeWeatherTool()
