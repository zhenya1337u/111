import asyncio
import disnake
from disnake.ext import commands
import logging
import aiohttp
from datetime import datetime
from typing import Optional

from bot.utils.logger import get_logger_for_cog

logger = get_logger_for_cog("utility.weather")

class Weather(commands.Cog):
    """Команды для получения информации о погоде"""
    
    def __init__(self, bot):
        self.bot = bot
        self.api_key = None
        self.session = None
        self.base_url = "https://api.openweathermap.org/data/2.5/weather"
        
        # Запуск задачи инициализации
        asyncio.create_task(self.initialize())
    
    async def initialize(self):
        """Инициализация модуля погоды"""
        # Ожидание готовности бота
        await self.bot.wait_until_ready()
        
        # Создание HTTP сессии
        self.session = aiohttp.ClientSession()
        
        # Получение API ключа
        self.api_key = self.bot.config.get("modules", {}).get("utility", {}).get("weather_api_key", "")
        
        logger.info("Модуль погоды инициализирован" if self.api_key else "Модуль погоды инициализирован, но API-ключ не найден")
    
    async def cog_unload(self):
        """Вызывается при выгрузке cog"""
        if self.session:
            await self.session.close()
    
    @commands.slash_command(name="weather", description="Получить информацию о погоде в указанном месте")
    async def weather(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        location: str = commands.Param(description="Местоположение (город, страна)"),
        units: str = commands.Param(
            "metric", 
            description="Единицы измерения",
            choices=["metric", "imperial"]
        )
    ):
        """Получить информацию о погоде в указанном месте"""
        # Проверка API ключа
        if not self.api_key:
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            error_text = self.bot.language_manager.get_text(
                "utility.weather.api_key_missing", 
                guild_language
            )
            return await inter.response.send_message(error_text, ephemeral=True)
        
        # Отложенный ответ, так как запрос может занять время
        await inter.response.defer()
        
        # Получение данных о погоде
        try:
            weather_data = await self._get_weather_data(location, units)
            
            if not weather_data:
                guild_language = await self.bot.get_guild_language(inter.guild.id)
                not_found_text = self.bot.language_manager.get_text(
                    "utility.weather.not_found", 
                    guild_language,
                    location=location
                )
                return await inter.followup.send(not_found_text)
            
            # Создание эмбеда с информацией о погоде
            embed = await self._create_weather_embed(inter, weather_data, location, units)
            
            # Отправка ответа
            await inter.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Ошибка при получении данных о погоде для {location}: {e}")
            
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            error_text = self.bot.language_manager.get_text(
                "utility.weather.error", 
                guild_language,
                error=str(e)
            )
            await inter.followup.send(error_text)
    
    async def _get_weather_data(self, location, units):
        """
        Получение данных о погоде через API
        
        Args:
            location (str): Местоположение (город, страна)
            units (str): Единицы измерения (metric, imperial)
        
        Returns:
            dict: Данные о погоде
        """
        try:
            params = {
                "q": location,
                "appid": self.api_key,
                "units": units,
                "lang": "ru"  # Можно также использовать локализацию из бота
            }
            
            async with self.session.get(self.base_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                elif response.status == 404:
                    logger.warning(f"Местоположение не найдено: {location}")
                    return None
                else:
                    logger.error(f"Ошибка API OpenWeatherMap: {response.status} - {await response.text()}")
                    return None
                
        except Exception as e:
            logger.error(f"Ошибка при запросе данных о погоде: {e}")
            return None
    
    async def _create_weather_embed(self, inter, weather_data, location, units):
        """
        Создание эмбеда с информацией о погоде
        
        Args:
            inter (disnake.ApplicationCommandInteraction): Объект взаимодействия
            weather_data (dict): Данные о погоде
            location (str): Местоположение (город, страна)
            units (str): Единицы измерения (metric, imperial)
        
        Returns:
            disnake.Embed: Эмбед с информацией о погоде
        """
        guild_language = await self.bot.get_guild_language(inter.guild.id)
        
        # Получение данных о погоде
        city_name = weather_data["name"]
        country = weather_data["sys"]["country"]
        temperature = weather_data["main"]["temp"]
        feels_like = weather_data["main"]["feels_like"]
        humidity = weather_data["main"]["humidity"]
        pressure = weather_data["main"]["pressure"]
        wind_speed = weather_data["wind"]["speed"]
        weather_description = weather_data["weather"][0]["description"]
        weather_icon = weather_data["weather"][0]["icon"]
        
        # Форматирование данных
        temperature_unit = "°C" if units == "metric" else "°F"
        wind_unit = "м/с" if units == "metric" else "миль/ч"
        
        # Создание эмбеда
        embed = disnake.Embed(
            title=self.bot.language_manager.get_text(
                "utility.weather.title", 
                guild_language,
                location=f"{city_name}, {country}"
            ),
            description=self.bot.language_manager.get_text(
                "utility.weather.description", 
                guild_language,
                condition=weather_description.capitalize()
            ),
            color=disnake.Color(self.bot.config.get('embed', {}).get('colors', {}).get('info', 0x7289da))
        )
        
        # Добавление иконки погоды
        embed.set_thumbnail(url=f"https://openweathermap.org/img/wn/{weather_icon}@2x.png")
        
        # Добавление полей
        embed.add_field(
            name=self.bot.language_manager.get_text("utility.weather.temperature", guild_language),
            value=f"{temperature:.1f}{temperature_unit}",
            inline=True
        )
        
        embed.add_field(
            name=self.bot.language_manager.get_text("utility.weather.feels_like", guild_language),
            value=f"{feels_like:.1f}{temperature_unit}",
            inline=True
        )
        
        embed.add_field(
            name=self.bot.language_manager.get_text("utility.weather.humidity", guild_language),
            value=f"{humidity}%",
            inline=True
        )
        
        embed.add_field(
            name=self.bot.language_manager.get_text("utility.weather.wind", guild_language),
            value=f"{wind_speed} {wind_unit}",
            inline=True
        )
        
        embed.add_field(
            name=self.bot.language_manager.get_text("utility.weather.pressure", guild_language),
            value=f"{pressure} гПа",
            inline=True
        )
        
        # Добавление футера и временной метки
        embed.set_footer(text="OpenWeatherMap API")
        embed.timestamp = datetime.utcnow()
        
        return embed

# Setup function for the cog
def setup(bot):
    bot.add_cog(Weather(bot))