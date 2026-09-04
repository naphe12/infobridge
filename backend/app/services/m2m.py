from app.schemas.integration import ApiScope


M2M_SCOPE_DEFINITIONS: dict[ApiScope, tuple[str, str]] = {
    "cases:read": ("Lire les demandes", "Consulter les demandes du périmètre institutionnel du client."),
    "documents:read": ("Lire les documents", "Lister et télécharger les pièces des demandes autorisées."),
}


def normalize_scopes(scopes: list[ApiScope]) -> list[ApiScope]:
    return sorted(set(scopes))


def scope_views() -> list[dict[str, str]]:
    return [
        {"code": code, "label": label, "description": description}
        for code, (label, description) in M2M_SCOPE_DEFINITIONS.items()
    ]
