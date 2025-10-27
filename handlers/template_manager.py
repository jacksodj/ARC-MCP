"""
Template Manager for Response Rewriting Prompts
"""
from pathlib import Path
from typing import Optional
from handlers.rewrite_utils import FindingType


class TemplateManager:
    """Manages prompt templates for different finding types"""

    def __init__(self, template_dir: str = "response_rewriting_prompts"):
        self.template_dir = Path(template_dir)

        # Ensure template directory exists
        if not self.template_dir.exists():
            raise ValueError(f"Template directory not found: {template_dir}")

    def get_template(self, finding_type: FindingType) -> Optional[str]:
        """Load template for a specific finding type"""
        # Skip templates for VALID and TOO_COMPLEX (handled specially)
        if finding_type in [FindingType.VALID, FindingType.TOO_COMPLEX]:
            return None

        template_file = self.template_dir / f"{finding_type.key}.txt"

        if not template_file.exists():
            return None

        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Error loading template {template_file}: {e}")
            return None

    def format_template(self, template: str, **kwargs) -> str:
        """Format template with provided variables"""
        try:
            return template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing required template variable: {e}")
