class VisualSearchProvider:
    """Provider contract for image features, similarity search and product indexing."""

    def search(self, *, image, filters):
        """Return ordered product IDs selected by a real visual similarity engine."""
        raise NotImplementedError

    def index_product(self, product):
        """Create or update the visual index entry for a catalog product."""
        raise NotImplementedError

    def remove_product(self, product_id):
        """Remove a product from the visual index when it is no longer searchable."""
        raise NotImplementedError