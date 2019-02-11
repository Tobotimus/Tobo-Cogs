import asyncio
import contextlib

import pytest

import docref


@pytest.fixture(scope="module")
def docref_cog():
    cog = docref.DocRef()
    yield cog
    getattr(cog, "_SphinxRef__unload")()


def test_already_up_to_date(docref_cog):
    async def test():
        with contextlib.suppress(docref.AlreadyUpToDate):
            await docref_cog.download_inv_file(
                "http://red-discordbot.readthedocs.io/en/v3-develop"
            )
        with pytest.raises(docref.AlreadyUpToDate):
            await docref_cog.download_inv_file(
                "http://red-discordbot.readthedocs.io/en/v3-develop"
            )
        return True

    loop = asyncio.get_event_loop()
    assert loop.run_until_complete(test())


def test_ref_regex_pattern():
    pat = docref.NodeRef.REF_PATTERN
    match = pat.match("doc:refname")
    print(match.groups())
