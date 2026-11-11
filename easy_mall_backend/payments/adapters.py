from abc import ABC, abstractmethod


class PaymentProviderAdapter(ABC):
    """Provider contract; credentials must be read from server environment only."""

    @abstractmethod
    def initialize_payment(self, *, payment, return_url):
        """Initialize a provider transaction and return a safe redirect/USSD result."""

    @abstractmethod
    def verify_webhook(self, *, raw_body, headers):
        """Cryptographically authenticate a provider webhook."""

    @abstractmethod
    def parse_webhook(self, *, raw_body, headers):
        """Return event_id, external_reference, transaction_reference and event type."""

    @abstractmethod
    def verify_transaction(self, *, external_reference):
        """Return authoritative server-to-server status, reference, amount and currency."""

    def refund(self, *, payment, amount, idempotency_key):
        raise NotImplementedError("Ce fournisseur ne prend pas en charge les remboursements.")

    @property
    def supports_recurring(self):
        return False

    def create_recurring(self, *, subscription, idempotency_key):
        raise NotImplementedError("Ce fournisseur ne prend pas en charge les paiements récurrents.")