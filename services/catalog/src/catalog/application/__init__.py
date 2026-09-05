"""Application layer — use cases and the ports they depend on.

Depends on `domain/` and on ports declared as `typing.Protocol`. Never on an
adapter: the direction of that dependency is the whole point of the hexagon.
"""
