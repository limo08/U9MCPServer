"""Submit + audit the already-saved draft quotation XSBJD0003 (Id 100010)."""
import asyncio
import json
import u9_mcp.server as srv

BILL_ID = 100010


async def main():
    print(f"=== Submit bill id={BILL_ID} ===")
    sub = await srv._post_raw("submit", "SAL_Quotation", {"Ids": BILL_ID})
    print("SUBMIT:", json.dumps(srv._result_status(sub, "submit"), ensure_ascii=False))

    print(f"=== Audit bill id={BILL_ID} ===")
    aud = await srv._post_raw("audit", "SAL_Quotation", {"Ids": BILL_ID})
    print("AUDIT:", json.dumps(srv._result_status(aud, "audit"), ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
