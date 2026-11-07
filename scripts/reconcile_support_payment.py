"""Reconcile a refund/dispute already verified in Ko-fi or its payment provider."""

import argparse
import asyncio
import json

from app.services.support_billing import rpc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transaction-id", required=True)
    parser.add_argument("--state", required=True, choices=["refunded", "disputed"])
    parser.add_argument("--actor", required=True)
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()
    result = asyncio.run(
        rpc(
            "support_revoke_payment",
            p_transaction_id=args.transaction_id,
            p_state=args.state,
            p_actor=args.actor,
            p_reason=args.reason,
        )
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
