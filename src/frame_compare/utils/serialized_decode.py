"""Failures raised while decoding untrusted serialized input."""

from typing import Final

# JSONDecodeError, TOMLDecodeError, UnicodeDecodeError, and the integer digit
# limit error inherit ValueError. Deeply nested input can raise RecursionError.
# Owners catch these only at decoding boundaries and retain their own policy.
SERIALIZED_DECODE_FAILURES: Final = (RecursionError, ValueError)
