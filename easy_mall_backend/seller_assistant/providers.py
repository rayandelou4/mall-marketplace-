LISTING_ASSISTANT_INSTRUCTIONS = """
Toutes les sorties sont des suggestions que le vendeur doit vérifier et valider.
Décris uniquement ce qui est directement visible sur les photos fournies.
N'infère et ne prétends jamais vérifier une marque, un modèle, une capacité,
une matière, un état interne, une authenticité ou toute autre caractéristique
technique qui n'est pas certaine et visible. Pour ces éléments, demande au
vendeur de les renseigner lui-même. N'invente pas de faits manquants.
""".strip()


class ListingAssistantProvider:
    """Provider plug-in contract. Suggestions are never verified product facts."""

    def suggest_listing(self, *, image_urls, current_fields, categories, instructions):
        """Return title, description, category_id, visual_attributes, keywords and quality_suggestions."""
        raise NotImplementedError