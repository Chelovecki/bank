class PaymentError(Exception):
    pass


class OrderNotFoundError(PaymentError):
    pass


class PaymentNotFoundError(PaymentError):
    pass


class AmountExceedsOrderError(PaymentError):
    pass


class InvalidPaymentStateError(PaymentError):
    pass


class InvalidPaymentTypeError(PaymentError):
    pass


class BankDataMismatchError(PaymentError):
    pass
