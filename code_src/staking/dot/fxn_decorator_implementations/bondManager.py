import json
import sys
from bip39 import bip39_validate
# TODO: can you confirm the below github for the substrateinterface library?
from substrateinterface import Keypair # github: https://github.com/polkascan/py-substrate-interface
from substrateinterface.exceptions import SubstrateRequestException
from config import activeConfig
from Logger import myLogger

def validateAccountDataBeforeBonding(ss58_address, tokenNumber, logger):
    # before we bond any coins we need to check account balance for two main things :
    #   1 - minimum dot staking amount witch is by time of writing (21/11/2021) is 120 DOT.
    #   2 - active address (Existential Deposit) witch is 1 DOT :
    #       - NB : !! If an account drops below the Existential Deposit, the account is reaped (“deactivated”)
    #           and any remaining funds are destroyed. !!
    # https://support.polkadot.network/support/solutions/articles/65000168651-what-is-the-existential-deposit-
    # so to protect user that use the script and don't know some basics we need to force check value.
    printTmp("I'm in validateAccountDataBeforeBonding A")

    # check the number of tokens to bond is above protocol min
    validateBondSize(logger, tokenNumber)
    
    # if the bonding qty is above the protocol min,
    # check that the account balance is sufficient to bond the tokenNumber
    # will sys.exit if balance is insufficient
    validateAcctBalanceForBonding(ss58_address, tokenNumber, logger)

    # TODO: check that controller address matches mnc

    # check decimal writing
    lenNumberAfterDecimalPoint = len(str(tokenNumber).split(".")[1])
    if lenNumberAfterDecimalPoint > activeConfig.coinDecimalPlacesLength:
        logger.warning(
            f"wrong token value token take max {activeConfig.coinDecimalPlacesLength} number after decimal point")
        sys.exit(0)


def validateBondSize(logger, tokenNumber):
    # TODO: the minimum to stake and the minimum to bond are not the same I assume, which should we be using?
    # TODO: confirm that the decimals of tokenNumber and stakeMin are directly comparable?
    if(tokenNumber < activeConfig.stakeMinimumAmount):
        logger.warning(f"You are trying to bond {tokenNumber}, but the minimum required for bonding is {activeConfig.stakeMinimumAmount} {activeConfig.coinName}\n")
        sys.exit(0)

def validateAcctBalanceForBonding(ss58_address, tokenNumber, logger):

    # we need to calculate account balance vs minimum needed

    # check requirements
    totalAccountBalance = AccountBalanceForBonding.getAccountBalance(ss58_address)
    printTmp(totalAccountBalance)

    # we need always to reserve existentialDeposit

    if totalAccountBalance < (tokenNumber + activeConfig.existentialDeposit):    
        logger.warning(
            f"Low balance\n"
            f"Actual balance is : {totalAccountBalance} {activeConfig.coinName}\n"
            f"Requested amount : {tokenNumber} {activeConfig.coinName}\n"
            f"Your account needs to have a minimum of {activeConfig.existentialDeposit} "
            f"{activeConfig.coinName} plus the requested amount and it does not.\nYou need at least: "
            f"{activeConfig.existentialDeposit} + {tokenNumber} = {activeConfig.existentialDeposit + tokenNumber}, "
            f"but the account balance is only {totalAccountBalance}")
        sys.exit(0)

# TODO:
# * rename AccountBalance class; better inheretence/abstraction
# * use accountManager
class AccountBalanceForBonding:
    def __init__(self):
        #self.ss58_address = ss58_address
        return

    @staticmethod
    def getAccountBalance(ss58_address):
        # query balance info for an account
        accountBalanceInfo = activeConfig.activeSubstrate.query('System', 'Account',
                                                                params=[ss58_address]).value

        # we only need free and reserved information from the balance info
        # free and reserved explained: https://wiki.polkadot.network/docs/learn-accounts#balance-types
        # TODO: decide what the account balance calculation "should" be, i.e. free + reserved or only free?
        free,reserved = accountBalanceInfo['data']['free'], accountBalanceInfo['data']['reserved']
        printTmp(free)

        # free and reserved are given as uint quantity; convert to float
        totalAccountBalance = free / activeConfig.coinDecimalPlaces + reserved / activeConfig.coinDecimalPlaces

        return totalAccountBalance

"""
Generic function for executing calls to DOT network
The following calls are made to this class:
* All calls in bounderArgParser.py (bond, unbond, rebond, bondextra, withdrawunbounded)
* Some calls in nominatorArgParser.py (nominate, unnominate)
* 1 call in stakerArgParser (staker)

"""
class DotSubstrateCall:
    def __init__(self, cli_name, call_module, call_params, seed):
        self.call_module = call_module
        self.call_params = call_params
        self.seed = seed
        self.logger = myLogger(cli_name)
        self.logger.info("Start %s Program." % cli_name)

    def __call__(self, func):
        self.logger.info("execute %s function." % func.__name__)
        print(self.call_module, self.call_params, self.seed)

        printTmp("I'm in DotSubstrateCall __call__ with the function: %s" %func.__name__)
        if func.__name__ == "bond":
            validateAccountDataBeforeBonding(ss58_address=self.call_params['controller'], tokenNumber=self.call_params['value'],
                         logger=self.logger)

        try:
            self.call_params['value'] = self.call_params['value'] * activeConfig.coinDecimalPlaces
        except KeyError:
            pass

        call = activeConfig.activeSubstrate.compose_call(
            call_module=f"{self.call_module}",
            call_function=f"{func.__name__}",
            call_params=self.call_params
        )

        """
        :param active_substrate: dot substrate to connect to
        :param seed: mnemonic phrase to sign the transaction
        :param call: transition parameters
        :return:
        """

        this_keypair = dotCreateKeyPair(logger=self.logger, mnemonic=self.seed)
        extrinsic = activeConfig.activeSubstrate.create_signed_extrinsic(call=call, keypair=this_keypair)
        """None
        {'substrate': < substrateinterface.base.SubstrateInterfaceobject at 0x000001F7C2F73F70 >, 
        'extrinsic_hash': '0xa9719ca1430e4a9f0305b03e4b6bdd582458525bcc44b01db3caa7fa7d933867', 
        'block_hash': '0xdd088c78eaee25ad99bc7d12c6d5cc5f4d81c6e301951d11501c77254c960505', 
        'block_number': None, 
        'finalized': False, 
        '_ExtrinsicReceipt__extrinsic_idx': None, 
        '_ExtrinsicReceipt__extrinsic': None, 
        '_ExtrinsicReceipt__triggered_events': None, 
        '_ExtrinsicReceipt__is_success': None, 
        '_ExtrinsicReceipt__error_message': None, 
        '_ExtrinsicReceipt__weight': None, 
        '_ExtrinsicReceipt__total_fee_amount': None
        }"""
        try:
            receipt = activeConfig.activeSubstrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)

            print(receipt.finalized)
            self.logger.info(
                "Extrinsic '{}' sent and included in block '{}'".format(receipt.extrinsic_hash, receipt.block_hash))

            self.__exit__()

        except SubstrateRequestException as e:
            arg = e.args[0]
            try:
                self.logger.error("%s : %s" % (arg['message'], arg['data']))
                self.__exit__()
            except KeyError:
                self.logger.error("%s" % (arg['message']))
                self.__exit__()

    def __exit__(self):
        # close connection with remote socket
        activeConfig.activeSubstrate.close()
        # exit system
        sys.exit(0)


# helper print method for checking the code, can delete function and all references anytime
def printTmp(printMe):
    print("\n\n****************\n %s \n****************\n\n" % printMe)