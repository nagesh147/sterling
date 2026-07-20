"""Extend derivative scans to cover the user's actual open option contracts.

The normal derivative pass intentionally scans only the configured moneyness ladder
around the *current* underlying spot.  That is efficient, but it creates a blind
spot: a contract can move away from the current ATM/ITM/OTM ladder after entry and
then never be evaluated again, even though its own 1H He