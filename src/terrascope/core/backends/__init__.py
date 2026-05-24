"""Alternative compute backends — Phase 5 surface.

The Phase 0–4 path computes everything locally via odc-stac + dask.  Some
users would rather push compute to a federated cloud (openEO) or to a
Sentinel Hub Process API session.  This package defines the abstract
interface and ships the openEO stub.
"""

from __future__ import annotations

from .protocol import ComputeBackend

__all__ = ["ComputeBackend"]
