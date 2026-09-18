import uuid


class WalletServiceError(Exception):
    """Base class for domain errors of the wallet service."""


class WalletNotFoundError(WalletServiceError):
    def __init__(self, wallet_id: uuid.UUID) -> None:
        super().__init__(f"Wallet {wallet_id} not found")
        self.wallet_id = wallet_id


class InsufficientFundsError(WalletServiceError):
    def __init__(self, wallet_id: uuid.UUID) -> None:
        super().__init__(f"Insufficient funds in wallet {wallet_id}")
        self.wallet_id = wallet_id


class BalanceLimitExceededError(WalletServiceError):
    def __init__(self, wallet_id: uuid.UUID) -> None:
        super().__init__(f"Balance limit exceeded for wallet {wallet_id}")
        self.wallet_id = wallet_id
