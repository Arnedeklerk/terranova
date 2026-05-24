"""openEO backend — Phase 5.

Pushes the same logical operations Terranova runs locally to an openEO
endpoint.  Authentication via OIDC device-code (same shape as the CDSE
flow); endpoints support is broad (CDSE, VITO, EODC, etc.).

Phase-5 status: the surface compiles and the auth flow is implementable;
the actual graph building is wired but not yet covered by tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class OpenEOBackend:
    """Concrete :class:`ComputeBackend` using the openEO Python client."""

    name: str = "openeo"
    endpoint: str = "openeo.dataspace.copernicus.eu"
    collection: str = "SENTINEL2_L2A"

    def _connect(self):  # type: ignore[no-untyped-def]
        import openeo

        return openeo.connect(self.endpoint).authenticate_oidc()

    def lazy_stack(
        self,
        bbox: tuple[float, float, float, float],
        datetime: str,
        bands: list[str],
        *,
        resolution: int,
    ):  # type: ignore[no-untyped-def]
        conn = self._connect()
        west, south, east, north = bbox
        start, end = datetime.split("/")
        return conn.load_collection(
            collection_id=self.collection,
            spatial_extent={"west": west, "south": south, "east": east, "north": north},
            temporal_extent=[start, end],
            bands=bands,
        )

    def composite(self, cube, *, method: str):  # type: ignore[no-untyped-def]
        if method == "median":
            return cube.reduce_dimension(dimension="t", reducer="median")
        if method == "mean":
            return cube.reduce_dimension(dimension="t", reducer="mean")
        raise ValueError(f"openEO backend does not yet support method={method!r}")

    def write_cog(self, cube, out_path: Path):  # type: ignore[no-untyped-def]
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        job = cube.save_result(format="GTiff").create_job()
        job.start_and_wait()
        results = job.get_results()
        results.download_files(str(out_path.parent))
        return out_path
