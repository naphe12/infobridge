from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.governance import ReferenceItem


class ReferenceDataValidationError(ValueError):
    pass


CatalogKey = Literal["institution_type", "case_priority", "classification", "attachment_purpose"]


@dataclass(frozen=True)
class ReferenceDefinition:
    code: str
    label: str
    description: str
    sort_order: int
    required_active: bool = False


@dataclass(frozen=True)
class CatalogDefinition:
    key: CatalogKey
    label: str
    items: tuple[ReferenceDefinition, ...]


CATALOG_DEFINITIONS: dict[str, CatalogDefinition] = {
    "institution_type": CatalogDefinition(
        "institution_type",
        "Types d’institution",
        (
            ReferenceDefinition("MINISTRY", "Ministère", "Administration ministérielle.", 10),
            ReferenceDefinition("BANK", "Banque", "Établissement bancaire ou financier.", 20),
            ReferenceDefinition("COMMUNE", "Commune", "Administration communale.", 30),
            ReferenceDefinition("AGENCY", "Agence", "Agence ou autorité publique.", 40, True),
            ReferenceDefinition("OPERATOR", "Opérateur", "Opérateur de service.", 50),
            ReferenceDefinition("PRIVATE", "Privé", "Organisation privée.", 60),
            ReferenceDefinition("OTHER", "Autre", "Autre type d’organisation.", 70),
        ),
    ),
    "case_priority": CatalogDefinition(
        "case_priority",
        "Priorités des demandes",
        (
            ReferenceDefinition("LOW", "Basse", "Traitement non prioritaire.", 10),
            ReferenceDefinition("NORMAL", "Normale", "Priorité appliquée par défaut.", 20, True),
            ReferenceDefinition("HIGH", "Haute", "Traitement prioritaire.", 30),
            ReferenceDefinition("URGENT", "Urgente", "Traitement urgent requis.", 40),
            ReferenceDefinition("CRITICAL", "Critique", "Traitement immédiat requis.", 50),
        ),
    ),
    "classification": CatalogDefinition(
        "classification",
        "Classifications de l’information",
        (
            ReferenceDefinition("PUBLIC", "Public", "Diffusion ouverte.", 10),
            ReferenceDefinition("INTERNE", "Interne", "Usage institutionnel.", 20, True),
            ReferenceDefinition("CONFIDENTIEL", "Confidentiel", "Accès restreint.", 30),
            ReferenceDefinition("SECRET", "Secret", "Traitement renforcé.", 40),
        ),
    ),
    "attachment_purpose": CatalogDefinition(
        "attachment_purpose",
        "Usages des pièces jointes",
        (
            ReferenceDefinition("REQUEST", "Pièce de demande", "Document associé à la demande.", 10, True),
            ReferenceDefinition("RESPONSE", "Pièce de réponse", "Document associé à la réponse.", 20),
            ReferenceDefinition("EVIDENCE", "Justificatif", "Élément justificatif ou probant.", 30),
        ),
    ),
}


def list_reference_items(db: Session, catalog: str | None = None) -> list[dict[str, object]]:
    catalogs = [_catalog(catalog)] if catalog is not None else list(CATALOG_DEFINITIONS.values())
    stored_items = list(db.scalars(select(ReferenceItem)))
    stored_by_key = {(item.catalog, item.code): item for item in stored_items}
    result = []
    for catalog_definition in catalogs:
        for definition in catalog_definition.items:
            stored = stored_by_key.get((catalog_definition.key, definition.code))
            result.append(_item_view(catalog_definition, definition, stored))
    return sorted(result, key=lambda item: (str(item["catalog"]), int(item["sort_order"]), str(item["code"])))


def update_reference_item(
    db: Session,
    catalog: str,
    code: str,
    *,
    label: str,
    description: str | None,
    active: bool,
    sort_order: int,
    updated_by,
) -> dict[str, object]:
    catalog_definition = _catalog(catalog)
    definition = _definition(catalog_definition, code)
    if definition.required_active and not active:
        raise ReferenceDataValidationError("This default value cannot be disabled")
    normalized_label = label.strip()
    if not normalized_label:
        raise ReferenceDataValidationError("Reference label cannot be empty")
    stored = db.scalar(
        select(ReferenceItem).where(ReferenceItem.catalog == catalog_definition.key, ReferenceItem.code == definition.code)
    )
    if stored is None:
        stored = ReferenceItem(catalog=catalog_definition.key, code=definition.code)
        db.add(stored)
    stored.label = normalized_label
    stored.description = description.strip() if description and description.strip() else None
    stored.active = active
    stored.sort_order = sort_order
    stored.updated_by = updated_by
    db.flush()
    return _item_view(catalog_definition, definition, stored)


def ensure_reference_active(db: Session, catalog: str, code: str) -> None:
    catalog_definition = _catalog(catalog)
    definition = _definition(catalog_definition, code)
    stored = db.scalar(
        select(ReferenceItem).where(ReferenceItem.catalog == catalog_definition.key, ReferenceItem.code == definition.code)
    )
    if stored is not None and not stored.active:
        raise ReferenceDataValidationError(f"Reference value {catalog}/{code} is disabled")


def _catalog(catalog: str) -> CatalogDefinition:
    definition = CATALOG_DEFINITIONS.get(catalog)
    if definition is None:
        raise ReferenceDataValidationError("Unknown reference catalog")
    return definition


def _definition(catalog: CatalogDefinition, code: str) -> ReferenceDefinition:
    normalized_code = code.upper()
    definition = next((item for item in catalog.items if item.code == normalized_code), None)
    if definition is None:
        raise ReferenceDataValidationError("Unknown reference value")
    return definition


def _item_view(
    catalog: CatalogDefinition,
    definition: ReferenceDefinition,
    stored: ReferenceItem | None,
) -> dict[str, object]:
    return {
        "catalog": catalog.key,
        "catalog_label": catalog.label,
        "code": definition.code,
        "label": stored.label if stored is not None else definition.label,
        "description": stored.description if stored is not None else definition.description,
        "active": stored.active if stored is not None else True,
        "sort_order": stored.sort_order if stored is not None else definition.sort_order,
        "required_active": definition.required_active,
        "source": "database" if stored is not None else "built_in",
    }
