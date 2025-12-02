"""
Configuration Loader for Henry the Hire Tracker
Loads and validates user configuration from config.yaml
"""

import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
import os


class Config:
    """Configuration manager for Henry the Hire Tracker."""

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration from YAML file.

        Args:
            config_path: Path to config.yaml (defaults to ./config.yaml)
        """
        if config_path is None:
            config_path = Path(__file__).parent / "config.yaml"

        self.config_path = config_path
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Config file not found: {self.config_path}\n"
                f"Copy config.example.yaml to config.yaml and fill in your information."
            )

        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)

        # Validate required fields
        self._validate_config(config)

        return config

    def _validate_config(self, config: Dict[str, Any]) -> None:
        """Validate that required configuration fields are present."""
        required_sections = ['user', 'resumes', 'preferences']
        for section in required_sections:
            if section not in config:
                raise ValueError(f"Missing required config section: {section}")

        # Validate user section
        required_user_fields = ['name', 'email']
        for field in required_user_fields:
            if not config['user'].get(field):
                raise ValueError(f"Missing required user field: {field}")

        # Validate resumes section
        if not config['resumes'].get('files'):
            raise ValueError("No resume files configured in 'resumes.files'")

    # ===== USER PROFILE =====

    @property
    def user_name(self) -> str:
        """Get user's full name."""
        return self._config['user']['name']

    @property
    def user_email(self) -> str:
        """Get user's email address."""
        return self._config['user']['email']

    @property
    def user_phone(self) -> str:
        """Get user's phone number."""
        return self._config['user'].get('phone', '')

    @property
    def user_location(self) -> str:
        """Get user's location."""
        return self._config['user'].get('location', '')

    @property
    def user_linkedin(self) -> str:
        """Get user's LinkedIn URL."""
        return self._config['user'].get('linkedin', '')

    @property
    def user_github(self) -> str:
        """Get user's GitHub URL."""
        return self._config['user'].get('github', '')

    @property
    def user_website(self) -> str:
        """Get user's website URL."""
        return self._config['user'].get('website', '')

    # ===== RESUMES =====

    @property
    def resume_files(self) -> List[str]:
        """Get list of resume file paths."""
        return self._config['resumes']['files']

    @property
    def default_resume(self) -> str:
        """Get default resume variant."""
        return self._config['resumes'].get('default', 'fullstack')

    def get_resume_variant(self, variant: str) -> Optional[Dict[str, str]]:
        """Get resume variant configuration."""
        return self._config['resumes'].get('variants', {}).get(variant)

    # ===== LOCATION PREFERENCES =====

    @property
    def primary_locations(self) -> List[Dict[str, Any]]:
        """Get primary target locations."""
        return self._config['preferences']['locations'].get('primary', [])

    @property
    def secondary_locations(self) -> List[Dict[str, Any]]:
        """Get secondary acceptable locations."""
        return self._config['preferences']['locations'].get('secondary', [])

    @property
    def excluded_locations(self) -> List[str]:
        """Get excluded locations."""
        return self._config['preferences']['locations'].get('excluded', [])

    def get_location_filter_prompt(self) -> str:
        """
        Generate AI prompt text for location filtering based on user preferences.

        Returns:
            Formatted string describing acceptable locations for AI filtering
        """
        lines = ["Keep ONLY if location is:"]

        # Add primary locations
        for loc in self.primary_locations:
            if loc['type'] == 'remote':
                lines.append(f"   - Remote (anywhere)")
            elif loc['type'] == 'city':
                city_name = loc['name']
                lines.append(f"   - {city_name}")

                # Add included neighborhoods/areas
                if 'includes' in loc and loc['includes']:
                    areas = ', '.join(loc['includes'])
                    lines.append(f"   - {city_name} area (including: {areas})")

        # Add secondary locations
        for loc in self.secondary_locations:
            if loc['type'] == 'state_remote':
                keywords = loc.get('keywords', [loc['name']])
                lines.append(f"   - {' / '.join(keywords)}")
            elif loc['type'] == 'hybrid':
                keywords = loc.get('keywords', [loc['name']])
                lines.append(f"   - {' / '.join(keywords)}")

        return '\n'.join(lines)

    # ===== JOB PREFERENCES =====

    @property
    def exclude_keywords(self) -> List[str]:
        """Get keywords to auto-reject in job titles."""
        return self._config['preferences'].get('filters', {}).get('exclude_keywords', [])

    @property
    def min_baseline_score(self) -> int:
        """Get minimum baseline score threshold."""
        return self._config['preferences'].get('filters', {}).get('min_baseline_score', 30)

    @property
    def auto_interest_threshold(self) -> int:
        """Get score threshold for auto-marking as interested."""
        return self._config['preferences'].get('filters', {}).get('auto_interest_threshold', 75)

    @property
    def experience_level(self) -> Dict[str, Any]:
        """Get experience level preferences."""
        return self._config['preferences'].get('experience_level', {
            'min_years': 1,
            'max_years': 5,
            'current_level': 'mid'
        })

    # ===== EMAIL CONFIGURATION =====

    @property
    def initial_scan_days(self) -> int:
        """Get number of days to scan on first run."""
        return self._config.get('email', {}).get('initial_scan_days', 7)

    @property
    def custom_email_sources(self) -> List[Dict[str, str]]:
        """Get custom email sources to scan."""
        return self._config.get('email', {}).get('custom_sources', [])

    # ===== AI CONFIGURATION =====

    @property
    def ai_model(self) -> str:
        """Get AI model to use for analysis."""
        return self._config.get('ai', {}).get('model', 'claude-sonnet-4-20250514')

    @property
    def strict_accuracy(self) -> bool:
        """Get whether to enforce strict accuracy in AI analysis."""
        return self._config.get('ai', {}).get('strict_accuracy', True)

    @property
    def cover_letter_config(self) -> Dict[str, Any]:
        """Get cover letter generation preferences."""
        return self._config.get('ai', {}).get('cover_letter', {
            'max_words': 350,
            'tone': 'professional',
            'include_metrics': True
        })

    # ===== TRACKING CONFIGURATION =====

    @property
    def default_status(self) -> str:
        """Get default status for new jobs."""
        return self._config.get('tracking', {}).get('default_status', 'new')

    @property
    def available_statuses(self) -> List[str]:
        """Get list of available job statuses."""
        return self._config.get('tracking', {}).get('statuses', [
            'new', 'interested', 'applied', 'interviewing',
            'offered', 'accepted', 'rejected', 'passed', 'hidden'
        ])

    # ===== UTILITY METHODS =====

    def reload(self) -> None:
        """Reload configuration from file."""
        self._config = self._load_config()

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-notation key.

        Example: config.get('user.name')
        """
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """
    Get global configuration instance.
    Creates instance on first call, then returns cached instance.
    """
    global _config
    if _config is None:
        _config = Config()
    return _config


def reload_config() -> None:
    """Reload configuration from file."""
    global _config
    if _config is not None:
        _config.reload()
    else:
        _config = Config()


if __name__ == '__main__':
    # Test configuration loading
    try:
        config = get_config()
        print(f"✓ Config loaded successfully")
        print(f"  User: {config.user_name} ({config.user_email})")
        print(f"  Resumes: {len(config.resume_files)} files")
        print(f"  Primary locations: {len(config.primary_locations)}")
        print(f"  AI Model: {config.ai_model}")
    except Exception as e:
        print(f"✗ Config error: {e}")
