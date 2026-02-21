from digestify_api import infrastructure
from digestify_api.identity import queries

migrations = infrastructure.migrations + [queries.create_tables]
