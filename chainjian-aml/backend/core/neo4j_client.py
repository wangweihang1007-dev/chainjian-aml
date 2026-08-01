"""Safe Neo4j connectivity for transaction graph reads and writes.

Credentials are supplied only through environment variables. Never read
``labels.csv`` when building or querying the graph.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from neo4j import Driver, GraphDatabase

from .config import NEO4J_DATABASE, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USERNAME


@lru_cache(maxsize=1)
def get_neo4j_driver() -> Driver:
    """Return a verified driver for the configured AML graph database."""
    if not NEO4J_PASSWORD:
        raise RuntimeError("NEO4J_PASSWORD is required to connect to Neo4j.")
    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
    )
    driver.verify_connectivity()
    return driver


def run_read(cypher: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Run a parameterized read query against the configured database."""
    with get_neo4j_driver().session(database=NEO4J_DATABASE) as session:
        return [record.data() for record in session.run(cypher, parameters or {})]


def close_neo4j_driver() -> None:
    """Close and clear the shared Neo4j driver."""
    driver = get_neo4j_driver()
    driver.close()
    get_neo4j_driver.cache_clear()
