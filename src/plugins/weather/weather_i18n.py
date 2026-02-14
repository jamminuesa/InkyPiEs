"""
Internationalization (i18n) utilities for Weather plugin
Provides locale-aware formatting and translations
Uses the system locale configured in inkypi.py main
"""

import locale as system_locale
from datetime import datetime
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Translation dictionary for common weather terms
TRANSLATIONS = {
    'en_US': {
        'feels_like': 'Feels Like',
        'sunrise': 'Sunrise',
        'sunset': 'Sunset',
        'humidity': 'Humidity',
        'wind': 'Wind',
        'rain': 'Rain',
        'pressure': 'Pressure',
        'uv_index': 'UV Index',
        'visibility': 'Visibility',
        'air_quality': 'Air Quality',
        'last_refresh': 'Last refresh',
        'moon_phase': 'Moon Phase',
        # Air quality scales
        'good': 'Good',
        'fair': 'Fair',
        'moderate': 'Moderate',
        'poor': 'Poor',
        'very_poor': 'Very Poor',
        'ext_poor': 'Ext Poor',
    },
    'es_ES': {
        'feels_like': 'Sensación térmica',
        'sunrise': 'Amanecer',
        'sunset': 'Atardecer',
        'humidity': 'Humedad',
        'wind': 'Viento',
        'rain': 'Lluvia',
        'pressure': 'Presión',
        'uv_index': 'Índice UV',
        'visibility': 'Visibilidad',
        'air_quality': 'Calidad del aire',
        'last_refresh': 'Última actualización',
        'moon_phase': 'Fase lunar',
        # Air quality scales
        'good': 'Buena',
        'fair': 'Aceptable',
        'moderate': 'Moderada',
        'poor': 'Mala',
        'very_poor': 'Muy Mala',
        'ext_poor': 'Extremadamente Mala',
    },
    'ca_ES': {  # Catalan
        'feels_like': 'Sensació tèrmica',
        'sunrise': 'Alba',
        'sunset': 'Posta de sol',
        'humidity': 'Humitat',
        'wind': 'Vent',
        'rain': 'Pluja',
        'pressure': 'Pressió',
        'uv_index': 'Índex UV',
        'visibility': 'Visibilitat',
        'air_quality': 'Qualitat de l\'aire',
        'last_refresh': 'Última actualització',
        'moon_phase': 'Fase lunar',
        # Air quality scales
        'good': 'Bona',
        'fair': 'Acceptable',
        'moderate': 'Moderada',
        'poor': 'Dolenta',
        'very_poor': 'Molt Dolenta',
        'ext_poor': 'Extremadament Dolenta',
    },
    'fr_FR': {  # French
        'feels_like': 'Ressenti',
        'sunrise': 'Lever du soleil',
        'sunset': 'Coucher du soleil',
        'humidity': 'Humidité',
        'wind': 'Vent',
        'rain': 'Pluie',
        'pressure': 'Pression',
        'uv_index': 'Indice UV',
        'visibility': 'Visibilité',
        'air_quality': 'Qualité de l\'air',
        'last_refresh': 'Dernière mise à jour',
        'moon_phase': 'Phase lunaire',
        # Air quality scales
        'good': 'Bonne',
        'fair': 'Moyenne',
        'moderate': 'Modérée',
        'poor': 'Mauvaise',
        'very_poor': 'Très Mauvaise',
        'ext_poor': 'Extrêmement Mauvaise',
    },
    'de_DE': {  # German
        'feels_like': 'Gefühlt',
        'sunrise': 'Sonnenaufgang',
        'sunset': 'Sonnenuntergang',
        'humidity': 'Feuchtigkeit',
        'wind': 'Wind',
        'rain': 'Regen',
        'pressure': 'Luftdruck',
        'uv_index': 'UV-Index',
        'visibility': 'Sichtweite',
        'air_quality': 'Luftqualität',
        'last_refresh': 'Letzte Aktualisierung',
        'moon_phase': 'Mondphase',
        # Air quality scales
        'good': 'Gut',
        'fair': 'Mäßig',
        'moderate': 'Durchschnittlich',
        'poor': 'Schlecht',
        'very_poor': 'Sehr Schlecht',
        'ext_poor': 'Extrem Schlecht',
    },
    'it_IT': {  # Italian
        'feels_like': 'Percepita',
        'sunrise': 'Alba',
        'sunset': 'Tramonto',
        'humidity': 'Umidità',
        'wind': 'Vento',
        'rain': 'Pioggia',
        'pressure': 'Pressione',
        'uv_index': 'Indice UV',
        'visibility': 'Visibilità',
        'air_quality': 'Qualità dell\'aria',
        'last_refresh': 'Ultimo aggiornamento',
        'moon_phase': 'Fase lunare',
        # Air quality scales
        'good': 'Buona',
        'fair': 'Discreta',
        'moderate': 'Moderata',
        'poor': 'Scarsa',
        'very_poor': 'Pessima',
        'ext_poor': 'Estremamente Pessima',
    },
    'pt_PT': {  # Portuguese
        'feels_like': 'Sensação',
        'sunrise': 'Nascer do sol',
        'sunset': 'Pôr do sol',
        'humidity': 'Humidade',
        'wind': 'Vento',
        'rain': 'Chuva',
        'pressure': 'Pressão',
        'uv_index': 'Índice UV',
        'visibility': 'Visibilidade',
        'air_quality': 'Qualidade do ar',
        'last_refresh': 'Última atualização',
        'moon_phase': 'Fase lunar',
        # Air quality scales
        'good': 'Boa',
        'fair': 'Razoável',
        'moderate': 'Moderada',
        'poor': 'Má',
        'very_poor': 'Muito Má',
        'ext_poor': 'Extremamente Má',
    },
}

# Date format patterns per locale
# Format: (current_date_format, short_day_format)
DATE_FORMATS = {
    'en_US': ('%A, %B %d', '%a'),      # Saturday, February 14 | Sat
    'en_GB': ('%A, %d %B', '%a'),      # Saturday, 14 February | Sat
    'es_ES': ('%A %d de %B', '%a'),    # sábado 14 de febrero | sáb
    'ca_ES': ('%A %d de %B', '%a'),    # dissabte 14 de febrer | ds
    'fr_FR': ('%A %d %B', '%a'),       # samedi 14 février | sam
    'de_DE': ('%A, %d. %B', '%a'),     # Samstag, 14. Februar | Sa
    'it_IT': ('%A %d %B', '%a'),       # sabato 14 febbraio | sab
    'pt_PT': ('%A, %d de %B', '%a'),   # sábado, 14 de fevereiro | sáb
}


class WeatherI18n:
    """
    Internationalization handler for Weather plugin
    Uses the system locale configured in inkypi.py
    """
    
    def __init__(self):
        """
        Initialize i18n handler using system locale
        The locale should already be set in inkypi.py via setup_locale()
        """
        self.locale_code = self._get_system_locale()
        self.translations = self._get_translations()
        self.date_formats = self._get_date_formats()
        
        logger.info(f"Weather i18n initialized with locale: {self.locale_code}")
    
    def _get_system_locale(self) -> str:
        """
        Get the system locale that was configured in inkypi.py
        
        Returns:
            Locale code like 'es_ES'
        """
        try:
            # Get locale from system (already set in inkypi.py)
            loc = system_locale.getlocale(system_locale.LC_TIME)
            
            if loc and loc[0]:
                locale_code = loc[0]
                logger.debug(f"Detected system locale: {locale_code}")
                return locale_code
            
        except Exception as e:
            logger.warning(f"Could not get system locale: {e}")
        
        # Fallback to English if can't detect
        logger.warning("Using fallback locale: en_US")
        return 'en_US'
    
    def _get_translations(self) -> Dict:
        """
        Get translations for current locale with fallback
        
        Returns:
            Translation dictionary
        """
        # Try exact match first (e.g., 'es_ES')
        if self.locale_code in TRANSLATIONS:
            return TRANSLATIONS[self.locale_code]
        
        # Try language-only match (e.g., 'es' from 'es_ES')
        lang_code = self.locale_code.split('_')[0]
        for locale_key in TRANSLATIONS:
            if locale_key.startswith(lang_code):
                logger.debug(f"Using translations for {locale_key} (from {self.locale_code})")
                return TRANSLATIONS[locale_key]
        
        # Fallback to English
        logger.warning(f"No translations found for {self.locale_code}, using English")
        return TRANSLATIONS['en_US']
    
    def _get_date_formats(self) -> tuple:
        """
        Get date formats for current locale with fallback
        
        Returns:
            Tuple of (current_date_format, short_day_format)
        """
        # Try exact match
        if self.locale_code in DATE_FORMATS:
            return DATE_FORMATS[self.locale_code]
        
        # Try language-only match
        lang_code = self.locale_code.split('_')[0]
        for locale_key in DATE_FORMATS:
            if locale_key.startswith(lang_code):
                logger.debug(f"Using date formats for {locale_key} (from {self.locale_code})")
                return DATE_FORMATS[locale_key]
        
        # Fallback to English
        logger.warning(f"No date formats found for {self.locale_code}, using English")
        return DATE_FORMATS['en_US']
    
    def translate(self, key: str) -> str:
        """
        Translate a key to current locale
        
        Args:
            key: Translation key (lowercase with underscores)
        
        Returns:
            Translated string
        """
        return self.translations.get(key, key.replace('_', ' ').title())
    
    def format_current_date(self, dt: datetime) -> str:
        """
        Format current date according to locale
        Uses system locale for month/day names
        
        Args:
            dt: Datetime object
        
        Returns:
            Formatted date string
        
        Examples:
            en_US: "Saturday, February 14"
            es_ES: "sábado 14 de febrero"
        """
        format_str = self.date_formats[0]
        return dt.strftime(format_str)
    
    def format_short_day(self, dt: datetime) -> str:
        """
        Format short day name according to locale
        Uses system locale for day names
        
        Args:
            dt: Datetime object
        
        Returns:
            Short day name
        
        Examples:
            en_US: "Sat"
            es_ES: "sáb"
        """
        format_str = self.date_formats[1]
        return dt.strftime(format_str)
    
    def format_last_refresh(self, dt: datetime, time_format: str = "12h") -> str:
        """
        Format last refresh time according to locale
        
        Args:
            dt: Datetime object
            time_format: "12h" or "24h"
        
        Returns:
            Formatted datetime string
        """
        # Date part depends on locale
        if self.locale_code.startswith('en'):
            date_part = dt.strftime("%Y-%m-%d")
        else:
            # Most other locales prefer DD-MM-YYYY or DD/MM/YYYY
            date_part = dt.strftime("%d/%m/%Y")
        
        # Time part depends on format preference
        if time_format == "24h":
            time_part = dt.strftime("%H:%M")
        else:
            time_part = dt.strftime("%I:%M %p")
        
        return f"{date_part} {time_part}"
    
    def get_air_quality_label(self, aqi_value: float) -> str:
        """
        Get translated air quality label based on AQI value
        
        Args:
            aqi_value: Air Quality Index value
        
        Returns:
            Translated quality label
        """
        if aqi_value < 20:
            return self.translate('good')
        elif aqi_value < 40:
            return self.translate('fair')
        elif aqi_value < 60:
            return self.translate('moderate')
        elif aqi_value < 80:
            return self.translate('poor')
        elif aqi_value < 100:
            return self.translate('very_poor')
        else:
            return self.translate('ext_poor')
