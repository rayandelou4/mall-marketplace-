class BuyerAssistantProvider:
    """Provider contract; listing facts are always resolved by the application."""

    def understand_needs(self, *, message, categories):
        """Return structured budget, category, condition, keywords and features."""
        raise NotImplementedError

    def rank_candidates(self, *, message, criteria, candidates):
        """Return an ordered list of product IDs selected only from candidates."""
        raise NotImplementedError