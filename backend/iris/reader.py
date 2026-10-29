"""Explicit reader routing; a Baseten failure never silently changes models."""
import os
from .meta import Meta


class Baseten(Meta):
    provider = 'Baseten'
    model = 'meta-models/muse-spark-open-1026'
    endpoint = 'https://inference.baseten.co/v1/chat/completions'
    spend_table = 'baseten_spend'
    key_variable = 'BASETEN_API_KEY'
    limit_variable = 'IRIS_BASETEN_SPEND_LIMIT_USD'
    default_limit = 10.0
    maximum_limit = 100.0

    async def transcribe(self, audio):
        raise ValueError('Voice uses Meta Voice Transcribe, not the blind reader.')


def create_reader(store):
    provider = os.getenv('IRIS_READER_PROVIDER', 'baseten').strip().lower()
    if provider == 'baseten':
        return Baseten(store)
    if provider == 'meta':
        return Meta(store)
    raise ValueError('IRIS_READER_PROVIDER must be baseten or meta.')
