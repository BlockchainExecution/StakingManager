import json
import sys
from bip39 import bip39_validate
# TODO: can you confirm the below github for the substrateinterface library?
from substrateinterface import Keypair # github: https://github.com/polkascan/py-substrate-interface
from substrateinterface.exceptions import SubstrateRequestException
from config import activeConfig
from Logger import myLogger


# TODO: Should we keep this fxn outside DotAccountCall, why?
