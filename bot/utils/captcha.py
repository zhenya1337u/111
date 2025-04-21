#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CAPTCHA generation and verification for the Discord bot.
Used for user verification in servers.
"""

import io
import os
import random
import string
import logging
import asyncio
from PIL import Image, ImageDraw, ImageFont
import disnake

logger = logging.getLogger('bot.captcha')

class CaptchaGenerator:
    """Generates and verifies CAPTCHAs for user verification"""
    
    def __init__(self):
        """Initialize the CAPTCHA generator"""
        self.font_path = os.path.join(os.path.dirname(__file__), '../../assets/fonts/arial.ttf')
        
        # Try to load a font, or use default if not available
        try:
            self.font = ImageFont.truetype(self.font_path, 40)
        except Exception as e:
            logger.warning(f"Could not load font: {e}. Using default font.")
            self.font = ImageFont.load_default()
        
        # Active verification sessions
        self.verification_sessions = {}
    
    def generate_code(self, length=6):
        """
        Generate a random CAPTCHA code.
        
        Args:
            length (int, optional): Length of the code. Defaults to 6.
        
        Returns:
            str: Random code
        """
        # Use uppercase letters and digits, excluding similar-looking characters
        characters = string.ascii_uppercase + string.digits
        characters = characters.replace('0', '').replace('O', '').replace('1', '').replace('I', '')
        
        return ''.join(random.choice(characters) for _ in range(length))
    
    def generate_image_captcha(self, code):
        """
        Generate a CAPTCHA image.
        
        Args:
            code (str): CAPTCHA code
        
        Returns:
            io.BytesIO: Image buffer
        """
        # Create image
        width, height = 280, 80
        image = Image.new('RGB', (width, height), color=(240, 240, 240))
        draw = ImageDraw.Draw(image)
        
        # Add noise (dots)
        for _ in range(50):
            x = random.randint(0, width)
            y = random.randint(0, height)
            draw.point((x, y), fill=(random.randint(0, 200), random.randint(0, 200), random.randint(0, 200)))
        
        # Add noise (lines)
        for _ in range(5):
            x1 = random.randint(0, width)
            y1 = random.randint(0, height)
            x2 = random.randint(0, width)
            y2 = random.randint(0, height)
            draw.line((x1, y1, x2, y2), fill=(random.randint(0, 200), random.randint(0, 200), random.randint(0, 200)))
        
        # Draw text
        text_width, text_height = draw.textsize(code, font=self.font)
        x = (width - text_width) // 2
        y = (height - text_height) // 2
        
        # Draw each character with slight rotation and offset
        for i, char in enumerate(code):
            char_x = x + i * (text_width // len(code))
            char_y = y + random.randint(-5, 5)
            draw.text((char_x, char_y), char, fill=(0, 0, 0), font=self.font)
        
        # Save to buffer
        buffer = io.BytesIO()
        image.save(buffer, 'PNG')
        buffer.seek(0)
        
        return buffer
    
    async def start_verification(self, user_id, guild_id, channel_id, timeout=300):
        """
        Start a verification process for a user.
        
        Args:
            user_id (int): User ID
            guild_id (int): Guild ID
            channel_id (int): Channel ID where verification is happening
            timeout (int, optional): Timeout in seconds. Defaults to 300.
        
        Returns:
            tuple: (code, image_buffer)
            - code: CAPTCHA code
            - image_buffer: CAPTCHA image buffer
        """
        code = self.generate_code()
        image_buffer = self.generate_image_captcha(code)
        
        # Store session
        key = f"{user_id}_{guild_id}"
        self.verification_sessions[key] = {
            'code': code,
            'channel_id': channel_id,
            'expires_at': asyncio.get_event_loop().time() + timeout,
            'attempts': 0
        }
        
        # Set timer to remove session when expired
        asyncio.get_event_loop().call_later(
            timeout,
            lambda: self.verification_sessions.pop(key, None)
        )
        
        return code, image_buffer
    
    def verify_code(self, user_id, guild_id, provided_code):
        """
        Verify a CAPTCHA code.
        
        Args:
            user_id (int): User ID
            guild_id (int): Guild ID
            provided_code (str): Code provided by the user
        
        Returns:
            bool: True if code is correct, False otherwise
        """
        key = f"{user_id}_{guild_id}"
        session = self.verification_sessions.get(key)
        
        if not session:
            return False
        
        # Increment attempts
        session['attempts'] += 1
        
        # Check if code is correct (case-insensitive)
        is_correct = session['code'].lower() == provided_code.strip().lower()
        
        # If correct or max attempts reached, remove session
        if is_correct or session['attempts'] >= 3:
            self.verification_sessions.pop(key, None)
        
        return is_correct
    
    def generate_text_captcha(self):
        """
        Generate a text-based CAPTCHA question.
        
        Returns:
            tuple: (question, answer)
        """
        # Simple math problems
        operations = [
            lambda: (f"What is {a} plus {b}?", str(a + b))
            for a, b in [(random.randint(1, 10), random.randint(1, 10)) for _ in range(5)]
        ]
        
        # Simple questions
        questions = [
            ("What color is the sky on a clear day?", "blue"),
            ("What is the opposite of hot?", "cold"),
            ("What is the opposite of black?", "white"),
            ("What comes after Monday?", "tuesday"),
            ("How many days are in a week?", "7"),
            ("What season comes after winter?", "spring")
        ]
        
        # Choose randomly from operations and questions
        if random.choice([True, False]):
            func = random.choice(operations)
            return func()
        else:
            return random.choice(questions)
    
    def generate_reaction_captcha(self):
        """
        Generate a reaction-based CAPTCHA.
        
        Returns:
            tuple: (emojis, correct_emoji, instruction)
        """
        # Common emojis for reaction verification
        emoji_sets = [
            ("🍎", "🍌", "🍇", "🍊", "🍓"),
            ("🐶", "🐱", "🐭", "🐰", "🦊"),
            ("🚗", "🚕", "🚙", "🚌", "🚑"),
            ("⚽", "🏀", "🎾", "⚾", "🏐"),
            ("💻", "📱", "⌚", "📷", "🎮")
        ]
        
        # Instructions
        instructions = [
            "React with the {emoji} emoji to verify.",
            "Please click on the {emoji} to verify your account.",
            "To verify, react with {emoji}.",
            "Click the {emoji} emoji to complete verification."
        ]
        
        # Choose random emoji set and correct emoji
        emojis = random.choice(emoji_sets)
        correct_emoji = random.choice(emojis)
        instruction = random.choice(instructions).format(emoji=correct_emoji)
        
        return emojis, correct_emoji, instruction

# Create a singleton instance
captcha_generator = CaptchaGenerator()

def get_captcha_generator():
    """Get the singleton CAPTCHA generator instance"""
    return captcha_generator
