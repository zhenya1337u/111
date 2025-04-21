#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Localization utilities for the Discord bot.
Handles loading and retrieving translations from JSON files.
"""

import os
import json
import logging
from functools import lru_cache

class Localization:
    """Handles loading and retrieving translations from JSON files"""
    
    def __init__(self, lang_dir=None):
        """
        Initialize the localization handler.
        
        Args:
            lang_dir (str, optional): Directory containing language files. 
                                     Defaults to '../lang/'.
        """
        if lang_dir is None:
            self.lang_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../lang/'))
        else:
            self.lang_dir = os.path.abspath(lang_dir)
        
        self.logger = logging.getLogger('bot.localization')
        self.languages = {}
        self.default_language = 'en'
        self.load_all_languages()
    
    def load_all_languages(self):
        """Load all language files from the language directory"""
        try:
            if not os.path.exists(self.lang_dir):
                self.logger.error(f"Language directory not found: {self.lang_dir}")
                return
            
            for filename in os.listdir(self.lang_dir):
                if filename.endswith('.json'):
                    lang_code = filename[:-5]  # Remove .json extension
                    self.load_language(lang_code)
            
            self.logger.info(f"Loaded {len(self.languages)} languages: {', '.join(self.languages.keys())}")
        except Exception as e:
            self.logger.error(f"Error loading language files: {e}")
    
    @lru_cache(maxsize=16)
    def load_language(self, lang_code):
        """
        Load a specific language file.
        
        Args:
            lang_code (str): Language code (e.g., 'en', 'ru', 'de')
        
        Returns:
            bool: True if loaded successfully, False otherwise
        """
        lang_file = os.path.join(self.lang_dir, f"{lang_code}.json")
        try:
            if not os.path.exists(lang_file):
                self.logger.warning(f"Language file not found: {lang_file}")
                return False
            
            with open(lang_file, 'r', encoding='utf-8') as file:
                self.languages[lang_code] = json.load(file)
            
            self.logger.debug(f"Loaded language {lang_code} from {lang_file}")
            return True
        except json.JSONDecodeError:
            self.logger.error(f"Error parsing language file: {lang_file}")
            return False
        except Exception as e:
            self.logger.error(f"Error loading language {lang_code}: {e}")
            return False
    
    def get_text(self, key, lang_code):
        """
        Get a translated text by key.
        
        Args:
            key (str): Translation key
            lang_code (str): Language code
        
        Returns:
            str: Translated text, or key if not found
        """
        # Ensure the language is loaded
        if lang_code not in self.languages:
            self.load_language(lang_code)
        
        # Try to get translation from the specified language
        if lang_code in self.languages and key in self.languages[lang_code]:
            return self.languages[lang_code][key]
        
        # Fall back to default language
        if lang_code != self.default_language:
            if self.default_language in self.languages and key in self.languages[self.default_language]:
                self.logger.debug(f"Translation for key '{key}' not found in {lang_code}, using {self.default_language}")
                return self.languages[self.default_language][key]
        
        # Return the key as fallback
        self.logger.debug(f"Translation key '{key}' not found in any language")
        return key
    
    def set_default_language(self, lang_code):
        """Set the default language"""
        if lang_code in self.languages:
            self.default_language = lang_code
            return True
        return False

# Global translation function
def _(key, lang_code='en', **kwargs):
    """
    Global function to get a translated text.
    
    Args:
        key (str): Translation key
        lang_code (str, optional): Language code. Defaults to 'en'.
        **kwargs: Format parameters for the translated text
    
    Returns:
        str: Translated and formatted text
    """
    # This is a placeholder that will be replaced at runtime
    # by the actual localization instance from the bot
    # For now, just return the key for testing
    return key

# Set up the global translation function with an actual localization instance
def setup_global_translations(localization_instance):
    """
    Set up the global translation function with an actual localization instance.
    
    Args:
        localization_instance (Localization): Localization instance
    """
    global _
    
    def _translate(key, lang_code='en', **kwargs):
        """
        Get a translated and formatted text.
        
        Args:
            key (str): Translation key
            lang_code (str, optional): Language code. Defaults to 'en'.
            **kwargs: Format parameters for the translated text
        
        Returns:
            str: Translated and formatted text
        """
        text = localization_instance.get_text(key, lang_code)
        try:
            if kwargs:
                return text.format(**kwargs)
            return text
        except KeyError as e:
            logger = logging.getLogger('bot.localization')
            logger.error(f"Missing format parameter in translation: {e}")
            return text
        except Exception as e:
            logger = logging.getLogger('bot.localization')
            logger.error(f"Error formatting translation: {e}")
            return text
    
    _ = _translate
