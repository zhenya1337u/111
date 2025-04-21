import asyncio
import disnake
from disnake.ext import commands
import logging
import random
import string
from datetime import datetime, timedelta
import io
from PIL import Image, ImageDraw, ImageFont
import os
from typing import Dict, Any, Optional, Tuple

from bot.utils.logger import get_logger_for_cog

logger = get_logger_for_cog("verification")

class CaptchaGenerator:
    """Класс для генерации изображений с CAPTCHA"""
    
    def __init__(self):
        """Инициализация генератора CAPTCHA"""
        self.fonts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets", "fonts")
        # Создание директории для шрифтов, если она не существует
        os.makedirs(self.fonts_dir, exist_ok=True)
        
        # Проверка наличия шрифтов
        self.fonts = self._get_available_fonts()
        
        if not self.fonts:
            logger.warning("Шрифты не найдены, будет использован стандартный шрифт")
    
    def _get_available_fonts(self):
        """Получение списка доступных шрифтов"""
        fonts = []
        try:
            for filename in os.listdir(self.fonts_dir):
                if filename.endswith(".ttf"):
                    font_path = os.path.join(self.fonts_dir, filename)
                    fonts.append(font_path)
        except Exception as e:
            logger.error(f"Ошибка при поиске шрифтов: {e}")
        
        return fonts
    
    def generate_captcha_code(self, length: int = 6) -> str:
        """
        Генерация случайного кода CAPTCHA
        
        Args:
            length (int): Длина кода
        
        Returns:
            str: Сгенерированный код
        """
        # Используем только буквы и цифры, исключая похожие символы (0, O, 1, I, etc.)
        chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        return ''.join(random.choice(chars) for _ in range(length))
    
    def generate_captcha_image(self, code: str, width: int = 300, height: int = 100) -> bytes:
        """
        Генерация изображения с CAPTCHA
        
        Args:
            code (str): Код CAPTCHA
            width (int): Ширина изображения
            height (int): Высота изображения
        
        Returns:
            bytes: Бинарные данные изображения
        """
        # Создание фонового изображения
        background = self._create_noisy_background(width, height)
        draw = ImageDraw.Draw(background)
        
        # Выбор шрифта
        font_size = height // 2
        if self.fonts:
            font_path = random.choice(self.fonts)
        else:
            # Использование встроенного шрифта, если шрифты не найдены
            try:
                import pkg_resources
                font_path = pkg_resources.resource_filename('PIL', 'DejaVuSans.ttf')
            except (ImportError, FileNotFoundError):
                # Если не найден встроенный шрифт, используем шрифт по умолчанию
                font = ImageFont.load_default()
                font_path = None
        
        if font_path:
            try:
                font = ImageFont.truetype(font_path, font_size)
            except Exception as e:
                logger.error(f"Ошибка при загрузке шрифта {font_path}: {e}")
                font = ImageFont.load_default()
        else:
            font = ImageFont.load_default()
        
        # Расчет позиции текста
        text_width, text_height = draw.textsize(code, font=font) if hasattr(draw, 'textsize') else font.getsize(code)
        text_x = (width - text_width) // 2
        text_y = (height - text_height) // 2
        
        # Нанесение текста
        for i, char in enumerate(code):
            # Случайное смещение для каждого символа
            char_x = text_x + (i * text_width // len(code))
            char_y = text_y + random.randint(-10, 10)
            
            # Случайный цвет для каждого символа
            color = self._get_random_dark_color()
            
            # Случайный наклон
            angle = random.randint(-30, 30)
            
            # Создание отдельного изображения для символа и его поворот
            char_img = Image.new('RGBA', (font_size, font_size), (0, 0, 0, 0))
            char_draw = ImageDraw.Draw(char_img)
            
            # Рисование символа
            text_pos = ((font_size - (text_width // len(code))) // 2, (font_size - text_height) // 2)
            char_draw.text(text_pos, char, font=font, fill=color)
            
            # Поворот символа
            rotated = char_img.rotate(angle, expand=1)
            
            # Вставка символа в основное изображение
            background.paste(rotated, (char_x, char_y), rotated)
        
        # Добавление линий для усложнения распознавания
        self._add_lines(draw, width, height)
        
        # Сохранение изображения в байтовый буфер
        buffer = io.BytesIO()
        background.save(buffer, format="PNG")
        buffer.seek(0)
        
        return buffer.getvalue()
    
    def _create_noisy_background(self, width: int, height: int) -> Image.Image:
        """
        Создание фонового изображения с шумом
        
        Args:
            width (int): Ширина изображения
            height (int): Высота изображения
        
        Returns:
            Image.Image: Фоновое изображение
        """
        # Создание белого фона
        background = Image.new('RGB', (width, height), color=(255, 255, 255))
        draw = ImageDraw.Draw(background)
        
        # Добавление случайных точек
        for _ in range(width * height // 10):
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)
            draw.point((x, y), fill=self._get_random_light_color())
        
        return background
    
    def _add_lines(self, draw: ImageDraw.Draw, width: int, height: int, count: int = 5) -> None:
        """
        Добавление случайных линий на изображение
        
        Args:
            draw (ImageDraw.Draw): Объект для рисования
            width (int): Ширина изображения
            height (int): Высота изображения
            count (int): Количество линий
        """
        for _ in range(count):
            start_x = random.randint(0, width // 4)
            start_y = random.randint(0, height)
            end_x = random.randint(width * 3 // 4, width)
            end_y = random.randint(0, height)
            
            # Случайная кривая линия
            points = [
                (start_x, start_y),
                (random.randint(width // 4, width * 3 // 4), random.randint(0, height)),
                (random.randint(width // 4, width * 3 // 4), random.randint(0, height)),
                (end_x, end_y)
            ]
            
            # Случайный цвет для линии
            color = self._get_random_dark_color()
            
            # Рисование линии
            draw.line(points, fill=color, width=random.randint(1, 2))
    
    def _get_random_dark_color(self) -> Tuple[int, int, int]:
        """
        Получение случайного темного цвета
        
        Returns:
            tuple: RGB-цвет
        """
        return (random.randint(0, 100), random.randint(0, 100), random.randint(0, 100))
    
    def _get_random_light_color(self) -> Tuple[int, int, int]:
        """
        Получение случайного светлого цвета
        
        Returns:
            tuple: RGB-цвет
        """
        return (random.randint(180, 255), random.randint(180, 255), random.randint(180, 255))

class Verification(commands.Cog):
    """Модуль верификации пользователей"""
    
    def __init__(self, bot):
        self.bot = bot
        self.captcha_generator = CaptchaGenerator()
        self.active_verifications = {}  # user_id -> {guild_id, code, attempts, expires_at}
    
    @commands.slash_command(name="verify", description="Пройти верификацию на сервере")
    async def verify(self, inter: disnake.ApplicationCommandInteraction):
        """Команда для прохождения верификации на сервере"""
        # Проверка, включена ли верификация на сервере
        guild_id = inter.guild.id
        verification_enabled = await self._is_verification_enabled(guild_id)
        
        if not verification_enabled:
            guild_language = await self.bot.get_guild_language(guild_id)
            error_text = self.bot.language_manager.get_text("verification.not_enabled", guild_language)
            return await inter.response.send_message(error_text, ephemeral=True)
        
        # Проверка, верифицирован ли уже пользователь
        user_id = inter.author.id
        already_verified = await self._is_user_verified(guild_id, user_id)
        
        if already_verified:
            guild_language = await self.bot.get_guild_language(guild_id)
            already_verified_text = self.bot.language_manager.get_text("verification.captcha.already_verified", guild_language)
            return await inter.response.send_message(already_verified_text, ephemeral=True)
        
        # Проверка наличия активной верификации
        if user_id in self.active_verifications and self.active_verifications[user_id].get('guild_id') == guild_id:
            verification = self.active_verifications[user_id]
            
            # Проверка, не истекла ли верификация
            if verification['expires_at'] > datetime.utcnow():
                guild_language = await self.bot.get_guild_language(guild_id)
                in_progress_text = self.bot.language_manager.get_text("verification.in_progress", guild_language)
                return await inter.response.send_message(in_progress_text, ephemeral=True)
        
        # Отложенный ответ, так как генерация капчи может занять время
        await inter.response.defer(ephemeral=True)
        
        # Генерация кода CAPTCHA
        captcha_code = self.captcha_generator.generate_captcha_code()
        captcha_image = self.captcha_generator.generate_captcha_image(captcha_code)
        
        # Настройка таймаута верификации
        timeout_minutes = self.bot.config.get("modules", {}).get("verification", {}).get("timeout_minutes", 10)
        expires_at = datetime.utcnow() + timedelta(minutes=timeout_minutes)
        
        # Настройка попыток
        max_attempts = self.bot.config.get("modules", {}).get("verification", {}).get("captcha_attempts", 3)
        
        # Сохранение информации о верификации
        self.active_verifications[user_id] = {
            'guild_id': guild_id,
            'code': captcha_code,
            'attempts': 0,
            'max_attempts': max_attempts,
            'expires_at': expires_at
        }
        
        # Подготовка сообщения
        guild_language = await self.bot.get_guild_language(guild_id)
        
        embed = disnake.Embed(
            title=self.bot.language_manager.get_text("verification.captcha.title", guild_language),
            description=self.bot.language_manager.get_text("verification.captcha.description", guild_language),
            color=disnake.Color(self.bot.config.get('embed', {}).get('colors', {}).get('info', 0x7289da))
        )
        
        embed.set_image(url="attachment://captcha.png")
        
        file = disnake.File(io.BytesIO(captcha_image), filename="captcha.png")
        
        # Создание кастомного вида для ввода кода
        class CaptchaModal(disnake.ui.Modal):
            def __init__(self, cog, user_id, guild_id):
                self.cog = cog
                self.user_id = user_id
                self.guild_id = guild_id
                
                components = [
                    disnake.ui.TextInput(
                        label=cog.bot.language_manager.get_text("verification.captcha.input_label", guild_language),
                        placeholder=cog.bot.language_manager.get_text("verification.captcha.input_placeholder", guild_language),
                        custom_id="captcha_code",
                        style=disnake.TextInputStyle.short,
                        max_length=10,
                        required=True,
                    ),
                ]
                
                super().__init__(
                    title=cog.bot.language_manager.get_text("verification.captcha.modal_title", guild_language),
                    custom_id="captcha_modal",
                    components=components,
                )
            
            async def callback(self, inter: disnake.ModalInteraction):
                await self.cog._handle_captcha_submission(inter, self.user_id, inter.text_values["captcha_code"])
        
        # Создание кнопки для открытия модального окна ввода
        class CaptchaView(disnake.ui.View):
            def __init__(self, cog, user_id, guild_id):
                super().__init__(timeout=timeout_minutes * 60)
                self.cog = cog
                self.user_id = user_id
                self.guild_id = guild_id
            
            @disnake.ui.button(label=self.cog.bot.language_manager.get_text("verification.captcha.button", guild_language), style=disnake.ButtonStyle.primary)
            async def captcha_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
                if inter.author.id != self.user_id:
                    return await inter.response.send_message(
                        self.cog.bot.language_manager.get_text("verification.not_for_you", guild_language),
                        ephemeral=True
                    )
                
                # Открытие модального окна
                await inter.response.send_modal(CaptchaModal(self.cog, self.user_id, self.guild_id))
            
            async def on_timeout(self):
                # Удаление верификации при истечении таймаута
                if self.user_id in self.cog.active_verifications:
                    del self.cog.active_verifications[self.user_id]
        
        # Отправка сообщения с капчей
        await inter.followup.send(
            embed=embed,
            file=file,
            view=CaptchaView(self, user_id, guild_id),
            ephemeral=True
        )
        
        # Запуск таймера для удаления верификации по истечении времени
        asyncio.create_task(self._verification_expiry_task(user_id, guild_id, timeout_minutes))
    
    async def _handle_captcha_submission(self, inter: disnake.ModalInteraction, user_id: int, submitted_code: str):
        """Обработка ввода кода CAPTCHA"""
        if user_id not in self.active_verifications:
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            error_text = self.bot.language_manager.get_text("verification.captcha.timeout", guild_language)
            return await inter.response.send_message(error_text, ephemeral=True)
        
        verification = self.active_verifications[user_id]
        guild_id = verification['guild_id']
        
        if guild_id != inter.guild.id:
            return
        
        guild_language = await self.bot.get_guild_language(guild_id)
        
        # Проверка, не истекла ли верификация
        if verification['expires_at'] < datetime.utcnow():
            del self.active_verifications[user_id]
            error_text = self.bot.language_manager.get_text("verification.captcha.timeout", guild_language)
            return await inter.response.send_message(error_text, ephemeral=True)
        
        # Увеличение счетчика попыток
        verification['attempts'] += 1
        
        # Проверка кода (без учета регистра)
        if submitted_code.upper() == verification['code'].upper():
            # Код верный, верифицируем пользователя
            await self._verify_user(inter.guild, inter.author)
            
            # Удаление верификации
            del self.active_verifications[user_id]
            
            # Отправка сообщения об успешной верификации
            success_text = self.bot.language_manager.get_text("verification.captcha.success", guild_language)
            await inter.response.send_message(success_text, ephemeral=True)
        else:
            # Код неверный
            if verification['attempts'] >= verification['max_attempts']:
                # Превышено количество попыток
                del self.active_verifications[user_id]
                
                too_many_attempts_text = self.bot.language_manager.get_text("verification.captcha.too_many_attempts", guild_language)
                await inter.response.send_message(too_many_attempts_text, ephemeral=True)
            else:
                # Еще есть попытки
                failure_text = self.bot.language_manager.get_text(
                    "verification.captcha.failure", 
                    guild_language, 
                    attempt=verification['attempts'],
                    max_attempts=verification['max_attempts']
                )
                await inter.response.send_message(failure_text, ephemeral=True)
    
    async def _verify_user(self, guild: disnake.Guild, member: disnake.Member):
        """Верификация пользователя на сервере"""
        try:
            # Получение роли верификации
            verification_role_id = await self._get_verification_role_id(guild.id)
            if verification_role_id:
                role = guild.get_role(verification_role_id)
                if role and guild.me.guild_permissions.manage_roles and role.position < guild.me.top_role.position:
                    await member.add_roles(role, reason="Прохождение верификации")
            
            # Обновление статуса верификации в базе данных
            if self.bot.db:
                try:
                    await self.bot.db.execute(
                        """
                        INSERT INTO members (id, guild_id, username, is_verified)
                        VALUES ($1, $2, $3, TRUE)
                        ON CONFLICT (id, guild_id) DO UPDATE
                        SET is_verified = TRUE
                        """,
                        member.id, guild.id, str(member)
                    )
                except Exception as e:
                    logger.error(f"Ошибка при обновлении статуса верификации в базе данных: {e}")
        
        except Exception as e:
            logger.error(f"Ошибка при верификации пользователя {member.id} на сервере {guild.id}: {e}")
    
    async def _verification_expiry_task(self, user_id: int, guild_id: int, minutes: int):
        """Задача для удаления верификации по истечении времени"""
        await asyncio.sleep(minutes * 60)
        
        # Проверка, не была ли верификация уже удалена
        if (
            user_id in self.active_verifications and 
            self.active_verifications[user_id].get('guild_id') == guild_id
        ):
            del self.active_verifications[user_id]
    
    async def _is_verification_enabled(self, guild_id: int) -> bool:
        """Проверка, включена ли верификация на сервере"""
        if not self.bot.db:
            # Если база данных не доступна, используем настройки из конфига
            return self.bot.config.get("modules", {}).get("verification", {}).get("enabled", False)
        
        try:
            result = await self.bot.db.fetchval(
                "SELECT verification_enabled FROM guilds WHERE id = $1",
                guild_id
            )
            return result if result is not None else False
        except Exception as e:
            logger.error(f"Ошибка при проверке статуса верификации на сервере {guild_id}: {e}")
            return False
    
    async def _is_user_verified(self, guild_id: int, user_id: int) -> bool:
        """Проверка, верифицирован ли пользователь на сервере"""
        if not self.bot.db:
            return False
        
        try:
            result = await self.bot.db.fetchval(
                "SELECT is_verified FROM members WHERE guild_id = $1 AND id = $2",
                guild_id, user_id
            )
            return result if result is not None else False
        except Exception as e:
            logger.error(f"Ошибка при проверке статуса верификации пользователя {user_id} на сервере {guild_id}: {e}")
            return False
    
    async def _get_verification_role_id(self, guild_id: int) -> Optional[int]:
        """Получение ID роли верификации"""
        if not self.bot.db:
            return None
        
        try:
            result = await self.bot.db.fetchval(
                "SELECT verification_role_id FROM guilds WHERE id = $1",
                guild_id
            )
            return result
        except Exception as e:
            logger.error(f"Ошибка при получении ID роли верификации на сервере {guild_id}: {e}")
            return None
    
    # ===== Команды настройки верификации =====
    
    @commands.slash_command(name="setup-verification", description="Настройка системы верификации пользователей")
    @commands.has_permissions(administrator=True)
    async def setup_verification(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        enabled: bool = commands.Param(description="Включить или выключить верификацию"),
        role: Optional[disnake.Role] = commands.Param(None, description="Роль для верифицированных пользователей"),
        channel: Optional[disnake.TextChannel] = commands.Param(None, description="Канал для верификации")
    ):
        """Настройка системы верификации пользователей"""
        guild_id = inter.guild.id
        
        # Отложенный ответ
        await inter.response.defer(ephemeral=True)
        
        # Обновление настроек верификации в базе данных
        if self.bot.db:
            try:
                update_params = {"verification_enabled": enabled}
                
                if role:
                    update_params["verification_role_id"] = role.id
                
                if channel:
                    update_params["verification_channel_id"] = channel.id
                
                # Преобразование параметров в SQL-запрос
                set_parts = []
                args = [guild_id]
                
                for i, (key, value) in enumerate(update_params.items(), start=2):
                    set_parts.append(f"{key} = ${i}")
                    args.append(value)
                
                if set_parts:
                    query = f"""
                        UPDATE guilds
                        SET {', '.join(set_parts)}
                        WHERE id = $1
                        RETURNING id
                    """
                    
                    result = await self.bot.db.fetchval(query, *args)
                    
                    if not result:
                        # Если сервер еще не существует в базе данных, создаем его
                        insert_cols = ["id"] + list(update_params.keys())
                        insert_placeholders = [f"${i+1}" for i in range(len(insert_cols))]
                        
                        insert_query = f"""
                            INSERT INTO guilds ({', '.join(insert_cols)})
                            VALUES ({', '.join(insert_placeholders)})
                            RETURNING id
                        """
                        
                        insert_args = [guild_id] + list(update_params.values())
                        
                        await self.bot.db.fetchval(insert_query, *insert_args)
            except Exception as e:
                logger.error(f"Ошибка при обновлении настроек верификации на сервере {guild_id}: {e}")
                
                guild_language = await self.bot.get_guild_language(guild_id)
                error_text = self.bot.language_manager.get_text("commands.common.error", guild_language)
                return await inter.followup.send(error_text, ephemeral=True)
        
        # Формирование ответа
        guild_language = await self.bot.get_guild_language(guild_id)
        
        embed = disnake.Embed(
            title=self.bot.language_manager.get_text("verification.setup.title", guild_language),
            description=self.bot.language_manager.get_text(
                "verification.setup.description", 
                guild_language,
                enabled="✅" if enabled else "❌"
            ),
            color=disnake.Color(self.bot.config.get('embed', {}).get('colors', {}).get('success', 0x2ecc71))
        )
        
        if role:
            embed.add_field(
                name=self.bot.language_manager.get_text("verification.setup.role", guild_language),
                value=role.mention,
                inline=False
            )
        
        if channel:
            embed.add_field(
                name=self.bot.language_manager.get_text("verification.setup.channel", guild_language),
                value=channel.mention,
                inline=False
            )
        
        embed.add_field(
            name=self.bot.language_manager.get_text("verification.setup.usage", guild_language),
            value=self.bot.language_manager.get_text("verification.setup.usage_description", guild_language),
            inline=False
        )
        
        await inter.followup.send(embed=embed, ephemeral=True)

# Setup function for the cog
def setup(bot):
    bot.add_cog(Verification(bot))