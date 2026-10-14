"""Shared connector interface (placeholder).

All job source connectors (Remotive, Arbeitnow, Remote OK, Greenhouse, ...) should
implement the protocol defined here so the discovery pipeline can treat them
uniformly.
"""


class ConnectorResult:
    pass


class BaseConnector:
    """Abstract base for a job source connector."""

    name: str = ""

    async def fetch(self, *args, **kwargs) -> list:
        raise NotImplementedError