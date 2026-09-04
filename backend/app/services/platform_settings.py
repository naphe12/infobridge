from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.governance import PlatformSetting


class PlatformSettingValidationError(ValueError):
    pass


@dataclass(frozen=True)
class SettingDefinition:
    key: str
    label: str
    description: str
    category: Literal["SECURITY", "RETENTION", "AUTOMATION"]
    value_type: Literal["integer", "boolean"]
    default_attribute: str
    minimum: int | None = None
    maximum: int | None = None

    @property
    def default_value(self) -> bool | int:
        return getattr(settings, self.default_attribute)


SETTING_DEFINITIONS = {
    definition.key: definition
    for definition in [
        SettingDefinition("access_token_minutes", "Durée du jeton d’accès", "Expiration des jetons utilisateurs et M2M, en minutes.", "SECURITY", "integer", "access_token_expire_minutes", 5, 1440),
        SettingDefinition("refresh_token_days", "Durée de session", "Durée maximale d’une session renouvelable, en jours.", "SECURITY", "integer", "refresh_token_expire_days", 1, 90),
        SettingDefinition("login_lock_threshold", "Seuil de verrouillage", "Nombre d’échecs de connexion avant verrouillage.", "SECURITY", "integer", "login_failure_lock_threshold", 3, 20),
        SettingDefinition("auto_archive_days", "Archivage automatique", "Délai après clôture avant archivage, en jours.", "RETENTION", "integer", "auto_archive_after_days", 1, 3650),
        SettingDefinition("default_retention_days", "Conservation par défaut", "Durée de conservation après archivage, en jours.", "RETENTION", "integer", "default_retention_days", 1, 36500),
        SettingDefinition("document_purge_enabled", "Purge physique automatique", "Supprime les fichiers dont la conservation est expirée.", "RETENTION", "boolean", "document_purge_enabled"),
        SettingDefinition("due_alerts_enabled", "Relances d’échéance", "Active la génération automatique des relances.", "AUTOMATION", "boolean", "due_alerts_enabled"),
        SettingDefinition("due_soon_hours", "Seuil d’échéance proche", "Fenêtre des alertes avant échéance, en heures.", "AUTOMATION", "integer", "due_soon_hours", 1, 720),
        SettingDefinition("lifecycle_interval_seconds", "Fréquence du planificateur", "Intervalle entre deux scans, en secondes.", "AUTOMATION", "integer", "lifecycle_scan_interval_seconds", 60, 86400),
    ]
}


def get_platform_setting(db: Session, key: str) -> bool | int:
    definition = SETTING_DEFINITIONS[key]
    stored = db.get(PlatformSetting, key)
    return stored.value if stored is not None else definition.default_value


def set_platform_setting(db: Session, key: str, value: Any, *, updated_by) -> PlatformSetting:
    definition = SETTING_DEFINITIONS.get(key)
    if definition is None:
        raise PlatformSettingValidationError("Unknown platform setting")
    validated = _validate_value(definition, value)
    stored = db.get(PlatformSetting, key)
    if stored is None:
        stored = PlatformSetting(key=key, value=validated, updated_by=updated_by)
        db.add(stored)
    else:
        stored.value = validated
        stored.updated_by = updated_by
    return stored


def setting_view(db: Session, definition: SettingDefinition) -> dict[str, Any]:
    stored = db.get(PlatformSetting, definition.key)
    return {
        "key": definition.key,
        "value": stored.value if stored is not None else definition.default_value,
        "default_value": definition.default_value,
        "value_type": definition.value_type,
        "category": definition.category,
        "label": definition.label,
        "description": definition.description,
        "minimum": definition.minimum,
        "maximum": definition.maximum,
        "source": "database" if stored is not None else "environment",
    }


def _validate_value(definition: SettingDefinition, value: Any) -> bool | int:
    if definition.value_type == "boolean":
        if not isinstance(value, bool):
            raise PlatformSettingValidationError("Setting value must be a boolean")
        return value
    if not isinstance(value, int) or isinstance(value, bool):
        raise PlatformSettingValidationError("Setting value must be an integer")
    if definition.minimum is not None and value < definition.minimum:
        raise PlatformSettingValidationError(f"Setting value must be at least {definition.minimum}")
    if definition.maximum is not None and value > definition.maximum:
        raise PlatformSettingValidationError(f"Setting value must be at most {definition.maximum}")
    return value
