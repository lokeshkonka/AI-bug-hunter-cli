import yaml
from pathlib import Path
from pydantic import ValidationError
from bughunter.models.scope import Scope, ScanMode

class ScopeValidator:
    """Validates bughunter-scope.yml structure and semantics."""

    @staticmethod
    def load_and_validate(file_path: str) -> Scope:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Scope file not found: {file_path}")
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML format in {file_path}: {e}")

        if not isinstance(data, dict):
            raise ValueError("Scope file must contain a YAML dictionary at the root.")
        
        try:
            scope = Scope.model_validate(data)
        except ValidationError as e:
            raise ValueError(f"Scope validation failed:\n{e}")

        ScopeValidator._validate_semantics(scope)
        return scope

    @staticmethod
    def _validate_semantics(scope: Scope):
        # URLs must be explicit; no wildcard internet scanning.
        for url in scope.targets.urls:
            if "*" in url:
                raise ValueError(f"Wildcards are not allowed in URLs: {url}")
        
        # lab-validation requires allow_lab_validation: true.
        if scope.scan.mode == ScanMode.lab_validation and not scope.safety.allow_lab_validation:
            raise ValueError("Scan mode 'lab-validation' requires safety.allow_lab_validation = true")
        
        # max_cost_usd must be a positive float.
        if scope.cost.max_cost_usd <= 0:
            raise ValueError(f"max_cost_usd must be positive, got {scope.cost.max_cost_usd}")
