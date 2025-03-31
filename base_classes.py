from discord_user.client import Client as DiscordClient
from discord_user.types import ClientDevice
from network_tools import NetworkToolsAPI
from network_tools.sql_storage import DictSQL

import secret
from embedding_tools import EmbeddingTools
from event_manager import EventManager

discord_proxies = secret.discord_proxies
discord_proxy = discord_proxies["https"] if discord_proxies else None

network_client = NetworkToolsAPI(secret.network_tools_api)
discord_client = DiscordClient(secret_token=secret.auth_token_discord, device=ClientDevice.android, afk=True, proxy_uri=discord_proxy)
embedding_tools = EmbeddingTools(secret.cohere_api_key, 'dataset', proxies=secret.cohere_proxies)
sql_database = DictSQL('chat_history')
event_manager = EventManager()
