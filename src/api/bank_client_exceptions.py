class BankApiError(Exception):
    pass


class BankTemporaryError(BankApiError):
    pass


class BankPermanentError(BankApiError):
    pass


class BankPaymentNotFoundError(BankApiError):
    pass
