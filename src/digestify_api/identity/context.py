from digestify_api.identity.token_manager import TokenManager
from digestify_api.infrastructure import Database, MessageBroker, OutboxRelay


class Context:
    def __init__(
        self,
        database: Database,
        message_broker: MessageBroker,
        outbox_relay: OutboxRelay,
        token_manager: TokenManager,
    ) -> None:
        self._database = database
        self._message_broker = message_broker
        self._outbox_relay = outbox_relay
        self._token_manager = token_manager

    @property
    def database(self) -> Database:
        return self._database

    @property
    def token_manager(self) -> TokenManager:
        return self._token_manager
