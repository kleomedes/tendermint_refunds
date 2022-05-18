import argparse
import csv
import json
import logging
from decimal import Decimal
from subprocess import run
from time import sleep

# import requests

DENOM_EXPONENTS = {
    'ATOM': 0,
    'uatom': 6,
    'OSMO': 0,
    'uosmo': 6,
}
BIN_DIR = ""  # if this isn't empty, make sure it ends with a slash
logger = logging.getLogger(__name__)
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.DEBUG)
logger.addHandler(stream_handler)
logger.setLevel(logging.DEBUG)



# def getResponse(end_point, query_field=None, query_msg=None):
#     response = None
#
#     try:
#         if query_msg is not None and query_field is not None:
#             response = requests.get(end_point, params={query_field: query_msg})
#         else:
#             response = requests.get(end_point, params={})
#     except Exception as e:
#         logger.exception(e)
#
#     if response is not None and response.status_code == 200:
#         return json.loads(response.text)
#     else:
#         if response is not None:
#             logger.error('\n\t'.join((
#                 "Response Error",
#                 str(response.status_code),
#                 str(response.text),
#             )))
#         else:
#             logger.error("Response is None")
#
#         return None


# def getSlashBlock(url: str, val_address: str) -> int:
#     endpoint = url + "/block_search?query=%22slash.address=%27" + val_address + "%27%22"
#     data = getResponse(endpoint)
#     latest_slash = len(data["result"]["blocks"]) - 1
#     return data["result"]["blocks"][latest_slash]["block"]["header"]["height"]


# def getDelegationAmounts(
#     daemon: str, endpoint: str, chain_id: str, block_height: int, valoper_address: str
# ):
#     endpoints = [endpoint]
#     delegations = {}
#     page = 1
#     page_limit = 200
#     more_pages = True

#     while more_pages:
#         endpoint_choice = (page % len(endpoints)) - 1
#         result = run(
#             f"{BIN_DIR}{daemon} q staking delegations-to {valoper_address} --height {block_height} --page {page} --output json --limit {page_limit} --node {endpoints[endpoint_choice]} --chain-id {chain_id}",
#             shell=True,
#             capture_output=True,
#             text=True,
#         )
#         if result.returncode == 1:
#             logger.info(endpoints[endpoint_choice])
#             continue
#         response = json.loads(result.stdout)

#         for delegation in response["delegation_responses"]:
#             delegator_address = delegation["delegation"]["delegator_address"]
#             delegation_amount = delegation["balance"]["amount"]
#             if delegator_address not in delegations:
#                 delegations[delegator_address] = delegation_amount
#             else:
#                 logger.info(delegator_address)
#         page += 1
#         sleep(2)
#         if len(response["delegation_responses"]) < page_limit < 20:
#             more_pages = False

#     return delegations


# def calculateRefundAmounts(
#     daemon: str, endpoint: str, chain_id: str, slash_block: int, valoper_address: str
# ):
#     pre_slack_block = int(slash_block) - 5
#     refund_amounts = {}
#     pre_slash_delegations = getDelegationAmounts(
#         daemon, endpoint, chain_id, pre_slack_block, valoper_address
#     )

#     post_slash_delegations = getDelegationAmounts(
#         daemon, endpoint, chain_id, slash_block, valoper_address
#     )

#     if len(pre_slash_delegations) != len(post_slash_delegations):
#         raise ("Something went awry on delegation calcs")
#     for delegation_address in pre_slash_delegations:
#         refund_amount = int(pre_slash_delegations[delegation_address]) - int(
#             post_slash_delegations[delegation_address]
#         )
#         if refund_amount > 100:
#             refund_amounts[delegation_address] = refund_amount

#     return refund_amounts


def buildRefundJSON(
    refund_amounts: dict, send_address: str, denom: str, memo: str
) -> dict:
    data = {
        "body": {
            "messages": [],
            "memo": memo,
            "timeout_height": "0",
            "extension_options": [],
            "non_critical_extension_options": [],
        },
        "auth_info": {
            "signer_infos": [],
            "fee": {
                "amount": [{"denom": denom, "amount": "50000"}],
                "gas_limit": "1500000",
                "payer": "",
                "granter": "",
            },
        },
        "signatures": [],
    }
    message_list = []
    for refund_address in refund_amounts:

        refund_amount = refund_amounts[refund_address]
        if denom in ('uatom', 'uosmo'):
            refund_amount = int(refund_amount)

        message = {
            "@type": "/cosmos.bank.v1beta1.MsgSend",
            "from_address": send_address,
            "to_address": refund_address,
            "amount": [
                {
                    "denom": denom,
                    "amount": str(refund_amount)
                }
            ],
        }
        message_list.append(message)
    data["body"]["messages"] = message_list
    return data


def buildRefundScript(
    refund_amounts: dict, send_address: str, denom: str, memo: str
) -> int:
    batch_size = 75
    batch = 0
    batches = []
    batched = {}
    while batch < len(refund_amounts):
        batched_refund_amounts = {}
        for x in list(refund_amounts)[batch : batch + batch_size]:
            batched_refund_amounts[x] = refund_amounts[x]
        batches.append(batched_refund_amounts)
        batch += batch_size

    batch = 0
    for batch_refund in batches:
        refundJson = buildRefundJSON(batch_refund, send_address, denom, memo)
        with open(f"/tmp/dist_{denom}_{batch}.json", "w+") as f:
            f.write(json.dumps(refundJson))
        for address in batch_refund:
            batched[address] = batch_refund[address]
        batch += 1
    return batch


def issue_refunds(
    batch_count: int, daemon: str, chain_id: str, keyname: str, node: str,
    denom: str, should_broadcast: bool = True, dry_run: bool = False,
):
    i = 0
    while i < batch_count:
        sign_cmd = (
            f"{BIN_DIR}{daemon} tx sign /tmp/dist_{denom}_{i}.json --from {keyname} -ojson "
            f"--output-document ~/dist_{denom}_{i}_signed.json --node {node} --chain-id {chain_id} "
            f"--keyring-backend test"
        )
        broadcast_cmd = (
            f"{BIN_DIR}{daemon} tx broadcast ~/dist_{denom}_{i}_signed.json --node {node} "
            f"--chain-id {chain_id}"
        )

        i += 1
        if dry_run:
            logger.debug(f"sign cmd: {sign_cmd}")
            logger.debug(f"broadcast cmd: {broadcast_cmd}")
        else:
            # sign
            if should_broadcast:
                result = run(sign_cmd, shell=True, capture_output=True, text=True)
                logger.info(f'subprocess.run() result: {result}')
            else:
                logger.debug('--no_broadcast was passed, not running broadcast command')
            sleep(1)

            # broadcast
            result = run(broadcast_cmd, shell=True, capture_output=True, text=True)
            logger.info(f'subprocess.run() result: {result}')

            # if this is not the last batch, sleep
            if i < batch_count:
                sleep(16)



def parseArgs():
    parser = argparse.ArgumentParser(
        description="Create json file for refunding slashing to delegators"
    )
    parser.add_argument(
        "--denom",
        dest="denom",
        required=True,
        default="uatom",
        help="denom for refunds (ex. uatom)",
    )
    parser.add_argument(
        "--daemon",
        dest="daemon",
        required=True,
        default="gaiad",
        help="daemon for refunds (ex. gaiad)",
    )
    parser.add_argument(
        "-c",
        "--chain_id",
        dest="chain_id",
        required=True,
        default="cosmoshub-4",
        help="Chain ID (ex. cosmoshub-4)",
    )
    parser.add_argument(
        "-e",
        "--endpoint",
        dest="endpoint",
        required=True,
        help="RPC endpoint to node for gathering data",
    )
    parser.add_argument(
        "-vc",
        "--valcons_address",
        dest="valcons_address",
        required=False,
        help="Valcons address of validator (ex. cosmosvalcons1c5e86exd7jsyhcfqdejltdsagjfrvv8xv22368), you can get this by doing {daemon} tendermint show-address",
    )
    parser.add_argument(
        "-v",
        "--valoper_address",
        dest="valoper_address",
        required=False,
        help="Valoper address of validator (ex. cosmosvaloper140l6y2gp3gxvay6qtn70re7z2s0gn57zfd832j), you can get this by doing {daemon} keys show --bech=val -a {keyname}",
    )
    parser.add_argument(
        "-s",
        "--send_address",
        dest="send_address",
        required=True,
        help="Address to send funds from",
    )
    parser.add_argument(
        "-m",
        "--memo",
        dest="memo",
        help="Optional. Memo to send in each tx (ex. With 💜 from Lavender.Five Nodes 🐝)",
    )
    parser.add_argument(
        "-k",
        "--keyname",
        dest="keyname",
        required=True,
        help="Wallet to issue refunds from",
    )
    parser.add_argument(
        "-f",
        "--refund_file",
        dest="refund_file",
        required=False,
        default=None,
        type=open,
        help=(
            "CSV file that encodes the delegator addresses and refund amounts. Note: delegator "
            "address is expected to be in the first column and the refund amount in [DENOM] is "
            "expected to be in the fourth column."
        )
    )
    parser.add_argument(
        "--dry_run",
        dest="dry_run",
        action='store_const',
        required=False,
        default=False,
        const=True,
        help="Indicates whether this should actually broadcast transactions or not",
    )
    parser.add_argument(
        "--no_broadcast",
        dest="no_broadcast",
        action='store_const',
        required=False,
        default=False,
        const=True,
        help=(
            "Similar to dry run, but in this case the tx JSON is output and signed, but not "
            "broadcast. This is useful for testing."
        ),
    )
    return parser.parse_args()


def getRefundAmountsFromFile(file_obj, denom):
    refund_amounts = {}
    refund_reader = csv.reader(file_obj, delimiter=',', quotechar='|')
    denom_multiplier = 10 ** DENOM_EXPONENTS.get(denom, 1)
    for row in refund_reader:
        if 'address' in row[0]:
            continue
        delegation_addr = row[0]
        refund_amt = Decimal(row[3]) * denom_multiplier
        refund_amounts[delegation_addr] = refund_amt

    return refund_amounts


def main():
    args = parseArgs()
    denom = args.denom
    daemon = args.daemon
    chain_id = args.chain_id
    endpoint = args.endpoint
    valcons_address = args.valcons_address
    valoper_address = args.valoper_address
    send_address = args.send_address
    memo = args.memo
    keyname = args.keyname
    refund_file = args.refund_file
    dry_run = args.dry_run
    should_broadcast = not args.no_broadcast
    logger.debug(f'DEBUG: args: {args}')

    # The next two calls are for calculating slash related refunds.
    # slash_block = getSlashBlock(endpoint, valcons_address)
    # refund_amounts = calculateRefundAmounts(
    #     daemon, endpoint, chain_id, slash_block, valoper_address
    # )

    # This one is for other kinds of refunds (e.g. never made it to the active set)
    refund_amounts = getRefundAmountsFromFile(refund_file, denom)

    batch_count = buildRefundScript(refund_amounts, send_address, denom, memo)
    issue_refunds(batch_count, daemon, chain_id, keyname, endpoint, denom, should_broadcast, dry_run)


if __name__ == "__main__":
    main()
