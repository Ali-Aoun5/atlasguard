"""Quick terminal demo:  python -m atlasguard.cli   (needs ANTHROPIC_API_KEY)

    python -m atlasguard.cli --reset     # wipe and re-create the practice bank first
"""
import sys

from dotenv import load_dotenv

from .agents.agent import AtlasGuardAgent
from .sandbox.db import init_db
from .tools import transfers


def main():
    load_dotenv()
    init_db(reset="--reset" in sys.argv)
    agent = AtlasGuardAgent()
    print("AtlasGuard (sandbox). Type 'quit' to exit.\n")
    while True:
        text = input("you> ").strip()
        if text.lower() in {"quit", "exit"}:
            break
        print("\n" + agent.ask(text) + "\n")
        # Human-in-the-loop confirmation for any pending drafts from this turn.
        for t in agent.trace:
            if t.get("name") == "draft_transfer" and \
                    t["output"].get("status") == "pending_human_confirmation":
                pid = t["output"]["pending_id"]
                if transfers.get_pending(pid)["status"] != "pending":
                    continue
                tok = transfers.get_confirmation_token(pid)
                print(f"[HUMAN CONFIRMATION] {pid}: send {t['output']['send_amount']:,.2f} "
                      f"to {t['input']['beneficiary_id']}. Type token {tok} to confirm, "
                      f"or press Enter to cancel.")
                ans = input("token> ").strip()
                if ans:
                    print(transfers.confirm_transfer(pid, ans))
        agent.trace.clear()


if __name__ == "__main__":
    main()
