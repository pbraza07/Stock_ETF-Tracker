__all__ = ["YahooFinanceProvider"]


def __getattr__(name):
    if name == "YahooFinanceProvider":
        from .yahoo import YahooFinanceProvider
        return YahooFinanceProvider
    raise AttributeError(name)
