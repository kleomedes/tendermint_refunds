# tendermint_refund

The purpose of this script is to create a json file to refund users from a slash event.

Usage:
```
git clone https://github.com/LavenderFive/refund.git
cd tendermint_refund
python3 src/refund.py --denom {denom} --daemon {denom} --c {chain_id} -e {rpc_endpoint} -vc {valcons_address} -v {valoper_address} -s {send_address}

# example:
python3 src/refund.py --denom uatom --daemon gaiad --c cosmoshub-4 -e http://65.21.132.124:10657 -vc cosmosvalcons1c5e86exd7jsyhcfqdejltdsagjfrvv8xv22368 -v cosmosvaloper140l6y2gp3gxvay6qtn70re7z2s0gn57zfd832j -s cosmos15s9vggt9d0xumzqeq89scy4lku4k6qlzvvv2lz -m "With 💜 from Lavender.Five Nodes 🐝"
```

This will output two different kinds of files

* `/tmp/dist_<denom>_<batch #>.json` which is the unsigned JSON representation of a batch transaction
* `~/dist_<denom>_<batch #>_signed.json` which represents the signed, but not yet broadcast batch transaaction

In addition to the original Lavender.Five nodes version of this script, there are two new command
line options, `--dry_run` and `-f`/`--refund_file`. Details below:

```bash
$ python3 src/refund.py --help
usage: refund.py [-h] --denom DENOM --daemon DAEMON -c CHAIN_ID -e ENDPOINT -vc VALCONS_ADDRESS -v VALOPER_ADDRESS -s SEND_ADDRESS [-m MEMO] -k KEYNAME [--dry_run [DRY_RUN]] [-f REFUND_FILE]

Create json file for refunding slashing to delegators

optional arguments:
  -h, --help            show this help message and exit
  --denom DENOM         denom for refunds (ex. uatom)
  --daemon DAEMON       daemon for refunds (ex. gaiad)
  -c CHAIN_ID, --chain_id CHAIN_ID
                        Chain ID (ex. cosmoshub-4)
  -e ENDPOINT, --endpoint ENDPOINT
                        RPC endpoint to node for gathering data
  -vc VALCONS_ADDRESS, --valcons_address VALCONS_ADDRESS
                        Valcons address of validator (ex. cosmosvalcons1c5e86exd7jsyhcfqdejltdsagjfrvv8xv22368),
                        you can get this by doing {daemon} tendermint show-address
  -v VALOPER_ADDRESS, --valoper_address VALOPER_ADDRESS
                        Valoper address of validator (ex. cosmosvaloper140l6y2gp3gxvay6qtn70re7z2s0gn57zfd832j),
                        you can get this by doing {daemon} keys show --bech=val -a {keyname}
  -s SEND_ADDRESS, --send_address SEND_ADDRESS
                        Address to send funds from
  -m MEMO, --memo MEMO  Optional. Memo to send in each tx (ex. With 💜 from Lavender.Five Nodes 🐝)
  -k KEYNAME, --keyname KEYNAME
                        Wallet to issue refunds from
  -f REFUND_FILE, --refund_file REFUND_FILE
                        CSV file that encodes the delegator addresses and refund amounts. Note: delegator address is expected to be in the first column and the refund amount in [DENOM] is expected to be in the fourth column.
  --dry_run             Indicates whether this should actually broadcast transactions or not
  --no_broadcast        Similar to dry run, but in this case the tx JSON is output and signed, but not broadcast. This is useful for testing.

```



### Previous Attempts

You may be tempted to believe the best way forward is to query against a node for addresses using block height, a la:
```
{daemon} q staking delegations-to {valoper_address} --height {block_height} --page {page} --output json --limit {page_limit} --node {endpoint} --chain-id {chain_id}
```

And with under 1500 delegators, you would be correct. Anything above that, and 10 load-balanced nodes was insufficient.
